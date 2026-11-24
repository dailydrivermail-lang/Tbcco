"""Guided SWMS job assessment: load the question tree and evaluate a set of answers.

The same evaluation logic exists in portal/static/js/assessment-engine.js for the live screen.
tests/test_assessment.py runs both on the same cases so they can't drift apart.
The server always re-evaluates on submit; the browser's result is never trusted.
"""
from __future__ import annotations

import functools
from pathlib import Path

import yaml

LIB = Path(__file__).resolve().parent / "library"
YES_NO = [{"v": "yes", "label": "Yes"}, {"v": "no", "label": "No"}]
UNSURE = {"v": "unsure", "label": "Not sure"}
CONTEXT_KEYS = ("job_type", "state", "building_age")
PRIORITIES = ("key", "standard", "quick")


def _yn(x):
    """YAML reads bare yes/no as booleans; answers are the strings 'yes' and 'no'."""
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, list):
        return [_yn(i) for i in x]
    if isinstance(x, dict):
        return {k: _yn(v) for k, v in x.items()}
    return x


@functools.lru_cache(maxsize=1)
def load_spec() -> dict:
    spec = _yn(yaml.safe_load((LIB / "assessment.yaml").read_text(encoding="utf-8")))
    for q in spec["questions"]:
        if q["priority"] == "quick":
            q.setdefault("type", "choice")
            q["options"] = YES_NO + [UNSURE]
            q["effects"] = [{"if": ["no", "unsure"], "check": q["no_flag"]}]
        elif q["type"] == "yesno":
            q["type"], q["options"] = "choice", list(YES_NO)
        elif q["type"] == "yesno_unsure":
            q["type"], q["options"] = "choice", YES_NO + [UNSURE]
        q.setdefault("effects", [])
    return spec


def _vals(answers: dict, key: str) -> list:
    v = answers.get(key)
    if v is None or v == "" or v == []:
        return []
    return [str(x) for x in v] if isinstance(v, list) else [str(v)]


def cond(c, answers: dict) -> bool:
    if not c:
        return True
    if "all" in c:
        return all(cond(x, answers) for x in c["all"])
    if "any" in c:
        return any(cond(x, answers) for x in c["any"])
    if "not" in c:
        return not cond(c["not"], answers)
    return any(v in [str(x) for x in c["in"]] for v in _vals(answers, c["q"]))


def questions_for(spec: dict, job_type: str) -> list[dict]:
    jt = next((j for j in spec["job_types"] if j["id"] == job_type), None)
    if not jt:
        return []
    out = []
    for sec in jt["sections"]:
        out += [q for q in spec["questions"] if q.get("section") == sec]
    out += [q for q in spec["questions"] if q["priority"] == "quick"]
    return out


def evaluate(answers: dict, spec: dict | None = None) -> dict:
    """answers: {job_type, state, building_age, <question id>: value or [values]}"""
    spec = spec or load_spec()
    jt = next((j for j in spec["job_types"] if j["id"] == answers.get("job_type")), None)
    res = {"job_type": jt["id"] if jt else None, "template": jt["template"] if jt else None, "visible": [], "missing": [],
           "hazards": [], "hrcw": [], "controls": [], "needs": [], "licences": [], "plant": [], "blockers": [], "checks": [],
           "stops": [], "details": [], "quick_no": [], "clean": {}}
    if not jt:
        return res
    live = {k: answers.get(k) for k in CONTEXT_KEYS}
    for q in questions_for(spec, jt["id"]):
        # a question is judged against context + answers to questions that are themselves visible
        if not cond(q.get("when"), live):
            continue
        res["visible"].append(q["id"])
        allowed = [o["v"] for o in q["options"]]
        vals = [v for v in _vals(answers, q["id"]) if v in allowed]
        if q["type"] != "multi":
            vals = vals[:1]
        if not vals:
            res["missing"].append(q["id"])
            continue
        live[q["id"]] = vals if q["type"] == "multi" else vals[0]
        res["clean"][q["id"]] = live[q["id"]]
        labels = [o["label"] for o in q["options"] if o["v"] in vals]
        if q["priority"] == "quick":
            if vals[0] != "yes":
                res["quick_no"].append({"id": q["id"], "label": q["short"], "answer": labels[0]})
        else:
            res["details"].append({"id": q["id"], "label": q["short"], "answer": "; ".join(labels), "priority": q["priority"],
                                   "unsure": any(v in ("unsure", "unknown", "undecided") for v in vals)})
        for e in q["effects"]:
            if not any(v in [str(x) for x in e["if"]] for v in vals) or not cond(e.get("when"), live):
                continue
            if "hazard" in e and e["hazard"] not in res["hazards"]:
                res["hazards"].append(e["hazard"])
            for i in e.get("hrcw", []):
                if i not in res["hrcw"]:
                    res["hrcw"].append(i)
            if "control" in e:
                res["controls"].append(dict(e["control"]))
            if "need" in e and e["need"] not in res["needs"]:
                res["needs"].append(dict(e["need"]))
            if "licence" in e and e["licence"] not in res["licences"]:
                res["licences"].append(e["licence"])
            if "plant" in e and e["plant"] not in res["plant"]:
                res["plant"].append(e["plant"])
            for kind, key in (("blocker", "blockers"), ("check", "checks"), ("stop", "stops")):
                if kind in e and e[kind] not in res[key]:
                    res[key].append(e[kind])
    return res


def client_spec(include_checks: bool = False) -> dict:
    """The spec as sent to the browser. Reviewer-only 'check' wording is stripped for clients
    (the count is kept); staff get it in full."""
    spec = load_spec()
    if include_checks:
        return spec
    import copy
    out = copy.deepcopy(spec)
    n = 0
    for q in out["questions"]:
        q.pop("no_flag", None)
        for e in q["effects"]:
            if "check" in e:
                n += 1
                e["check"] = f"#{n}"
    return out


def job_title(job_type: str) -> str:
    return next((j["title"] for j in load_spec()["job_types"] if j["id"] == job_type), job_type or "")


def evaluate_record(rec: dict) -> dict:
    site = rec.get("site") or {}
    return evaluate({"job_type": rec.get("job_type"), "state": site.get("state"), "building_age": site.get("building_age"),
                     **(rec.get("answers") or {})})


def jobs_row(rec: dict, hazard_columns: dict[str, str]) -> dict:
    """Jobs-sheet columns for an assessment record. hazard_columns: module key -> Jobs column name."""
    import datetime as dt
    site, d = rec.get("site") or {}, evaluate_record(rec)
    plant = d["plant"] + ([rec["plant_other"]] if rec.get("plant_other") else [])
    row = {"Client job ref": site.get("client_ref") or None, "Site address": site.get("site_address"), "State": site.get("state"),
           "Principal / head contractor": site.get("head_contractor") or None,
           "Scope of work": f"{job_title(rec.get('job_type'))}: {site.get('scope', '')}".strip(),
           "Start date": dt.date.fromisoformat(site["start_date"]) if site.get("start_date") else None,
           "Plant and equipment": ", ".join(plant) or None,
           "Workers assigned (Person IDs)": "; ".join(rec.get("crew") or []) or None}
    for module, col in hazard_columns.items():
        row[col] = "Y" if module in d["hazards"] else "N"
    return row
