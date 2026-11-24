"""Read-side view models for the portal, built from each client's register workbook
using the same engine functions as the expiry engine (one set of rules, one set of statuses).

The register stays the source of truth. The portal never edits credentials or insurances.
It only appends SWMS requests to Jobs (staff action) and drops uploads into 01_Intake_Inbox.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from engine import expiry_engine as ee
from swms import assessment, model
from engine import schema
from engine.register_io import append_rows, load_rules, next_id, read_sheet

CLIENT_DIR_RE = re.compile(r"^(C\d{3,})_")
_cache: dict[Path, tuple[float, float, "ClientView"]] = {}

STATUS_ORDER = ["EXPIRED", "DUE 7", "DUE 30", "DUE 60", "MISSING DATE", "CURRENT", "NO EXPIRY"]
STATUS_TEXT = {
    "EXPIRED": "Expired", "DUE 7": "Due within 7 days", "DUE 30": "Due within 30 days", "DUE 60": "Due within 60 days",
    "CURRENT": "Current", "NO EXPIRY": "No expiry", "MISSING DATE": "Expiry date needed",
}
HAZARDS = [  # (form field, Jobs column, label)
    ("hz_height", "Hazard: height over 2m", "Work at height over 2 m"),
    ("hz_trench", "Hazard: trench over 1.5m", "Trench deeper than 1.5 m"),
    ("hz_confined", "Hazard: confined space", "Confined space (pit, tank, sewer structure)"),
    ("hz_electrical", "Hazard: live electrical", "Near live electrical / disconnect-reconnect"),
    ("hz_asbestos", "Hazard: asbestos", "Possible asbestos (pre-2004 building)"),
    ("hz_silica", "Hazard: silica", "Cutting, chasing or core-drilling concrete, masonry or tiles"),
    ("hz_hotworks", "Hazard: hot works", "Hot works (brazing, flame soldering)"),
    ("hz_gas", "Hazard: gas lines", "Gas mains or pressurised gas lines"),
    ("hz_traffic", "Hazard: traffic / mobile plant", "Traffic or mobile plant nearby"),
]


def find_clients(root: Path) -> dict[str, Path]:
    out = {}
    for p in sorted(Path(root).iterdir()):
        m = CLIENT_DIR_RE.match(p.name)
        if p.is_dir() and m and (p / "00_Register").is_dir():
            out[m.group(1)] = p
    return out


def client_dir(root: Path, client_id: str) -> Path | None:
    return find_clients(root).get(client_id)


@dataclass
class PersonView:
    person: dict
    credentials: list = field(default_factory=list)

    @property
    def attention(self) -> bool:
        return not self.credentials or self.worst in ("EXPIRED", "DUE 7", "DUE 30", "MISSING DATE")

    @property
    def worst(self) -> str:
        s = [c.status for c in self.credentials] or ["CURRENT"]
        return min(s, key=lambda x: STATUS_ORDER.index(x) if x in STATUS_ORDER else 99)


@dataclass
class ClientView:
    client_id: str
    business: dict
    people: list[PersonView]
    subbies: list[dict]
    items: list
    gaps: list
    gaps_hidden: int
    jobs: list[dict]
    rag: str
    register_mtime: dt.datetime
    today: dt.date
    verification: dict  # item_id -> Verification text

    @property
    def name(self) -> str:
        return self.business.get("Trading name") or self.business.get("Legal name") or self.client_id

    @property
    def tracked(self) -> int:
        return sum(1 for i in self.items if i.sheet in ("Credentials", "Insurances"))

    @property
    def score(self) -> int:
        """Percent of tracked licences, tickets and insurances that are current (not expired, date known)."""
        n = self.tracked
        return round(100 * (n - self.count("EXPIRED", "MISSING DATE")) / n) if n else 100

    @property
    def upcoming_groups(self) -> list:
        up = self.upcoming
        return [("Next 7 days", [i for i in up if i.status == "DUE 7"]), ("8 to 30 days", [i for i in up if i.status == "DUE 30"]),
                ("31 to 60 days", [i for i in up if i.status == "DUE 60"])]

    def count(self, *statuses, sheets=("Credentials", "Insurances")) -> int:
        return sum(1 for i in self.items if i.status in statuses and i.sheet in sheets)

    @property
    def needs(self) -> list:
        """What we need from the client: expired, missing dates, then rule gaps."""
        cr = [i for i in self.items if i.sheet in ("Credentials", "Insurances")]
        out = [("expired", i) for i in sorted(cr, key=lambda x: x.days or 0) if i.status == "EXPIRED"]
        out += [("nodate", i) for i in cr if i.status == "MISSING DATE"]
        seen = set()
        for gp in self.gaps:
            if (gp.holder_id, gp.evidence) not in seen:
                seen.add((gp.holder_id, gp.evidence))
                out.append(("missing", gp))
        return out

    @property
    def upcoming(self) -> list:
        return sorted([i for i in self.items if i.status in ("DUE 7", "DUE 30", "DUE 60")], key=lambda x: x.days)

    def insurances(self, holder_type: str) -> list:
        own = self.client_id
        return [i for i in self.items if i.sheet == "Insurances" and ((i.holder_id == own) == (holder_type == "Client"))]


def build_view(cdir: Path, today: dt.date, rules: list[dict], include_unreviewed: bool) -> ClientView:
    reg = ee.find_register(cdir)
    mtime = reg.stat().st_mtime
    key = (cdir, include_unreviewed, today)
    hit = _cache.get(key)
    if hit and hit[0] == mtime:
        return hit[2]
    wb = load_workbook(reg)
    bl = read_sheet(wb, "Business")
    business = bl[0] if bl else {}
    people, subbies = read_sheet(wb, "People"), read_sheet(wb, "Subcontractors")
    creds, ins = read_sheet(wb, "Credentials"), read_sheet(wb, "Insurances")
    plant, docs, jobs = read_sheet(wb, "Plant"), read_sheet(wb, "Documents"), read_sheet(wb, "Jobs")
    cid = str(business.get("Client ID") or CLIENT_DIR_RE.match(cdir.name).group(1))
    items = ee.collect_items(today, people, creds, ins, plant, docs, subbies, business)
    gaps, _ = ee.check_gaps(rules, business, people, subbies, creds, ins, cid)
    shown = gaps if include_unreviewed else [x for x in gaps if x.ivana_status.startswith("Verified")]
    res = ee.ClientResult(cid, business.get("Legal name", ""), items=items, gaps=shown)
    verification = {str(r.get("Credential ID")): r.get("Verification") or "Unverified" for r in creds}
    verification.update({str(r.get("Insurance ID")): r.get("Verification") or "Unverified" for r in ins})
    pv = []
    for p in people:
        if str(p.get("Active", "Y")).upper() == "N":
            continue
        pid = str(p.get("Person ID"))
        pv.append(PersonView(p, sorted([i for i in items if i.sheet == "Credentials" and i.holder_id == pid],
                                       key=lambda i: STATUS_ORDER.index(i.status))))
    view = ClientView(cid, business, pv, subbies, items, shown, len(gaps) - len(shown), jobs, ee.rag_for(res),
                      dt.datetime.fromtimestamp(mtime), today, verification)
    _cache[key] = (mtime, 0.0, view)
    return view


# ---------------------------------------------------------------------------
# Files: reports, issued SWMS, uploads
# ---------------------------------------------------------------------------

def safe_child(base: Path, rel: str) -> Path | None:
    """Resolve rel inside base; None if it escapes base or isn't a file."""
    base = base.resolve()
    p = (base / rel).resolve()
    try:
        p.relative_to(base)
    except ValueError:
        return None
    return p if p.is_file() else None


def list_reports(cdir: Path) -> list[dict]:
    base = cdir / "09_Client_Reports"
    out = []
    for p in sorted(base.rglob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file() and not p.name.startswith(("~$", ".")):
            out.append({"rel": p.relative_to(base).as_posix(), "name": p.name, "folder": p.parent.name,
                        "modified": dt.datetime.fromtimestamp(p.stat().st_mtime), "size_kb": max(1, p.stat().st_size // 1024)})
    return out


def issued_swms(cdir: Path, job: dict) -> Path | None:
    """An issued SWMS is only downloadable if the register says Issued AND a reviewer is recorded.
    The PDF lives in 04_Jobs/<JobID>_*/Issued/."""
    if job.get("SWMS status") != "Issued" or not job.get("Reviewed by"):
        return None
    for d in (cdir / "04_Jobs").glob(f"{job.get('Job ID')}_*/Issued"):
        pdfs = sorted(d.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True)
        if pdfs:
            return pdfs[0]
    return None


def latest_draft(cdir: Path, job: dict) -> Path | None:
    drafts = sorted((cdir / "04_Jobs").glob(f"{job.get('Job ID')}_*/Drafts/*_SWMS_v*_DRAFT.pdf"),
                    key=lambda p: int(p.stem.split("_v")[1].split("_")[0]))
    return drafts[-1] if drafts else None


def upload_dir(cdir: Path) -> Path:
    d = cdir / "01_Intake_Inbox" / "portal"
    d.mkdir(parents=True, exist_ok=True)
    return d


def record_upload(cdir: Path, entry: dict):
    with open(upload_dir(cdir) / "_uploads.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def list_uploads(cdir: Path, limit: int = 50) -> list[dict]:
    p = upload_dir(cdir) / "_uploads.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    for r in rows:
        r["processed"] = not (upload_dir(cdir) / r["stored_as"]).exists()
    return list(reversed(rows))[:limit]


# ---------------------------------------------------------------------------
# SWMS requests
# ---------------------------------------------------------------------------

def requests_dir(cdir: Path) -> Path:
    d = cdir / "01_Intake_Inbox" / "swms_requests"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_swms_request(cdir: Path, data: dict) -> dict:
    now = dt.datetime.now().replace(microsecond=0)
    rid = f"R{now:%Y%m%d%H%M%S}{secrets.token_hex(2)}"
    rec = {"request_id": rid, "submitted_at": now.isoformat(), "status": "Pending", **data}
    (requests_dir(cdir) / f"{rid}.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def list_swms_requests(cdir: Path, status: str | None = None) -> list[dict]:
    out = []
    for p in sorted(requests_dir(cdir).glob("R*.json"), reverse=True):
        r = json.loads(p.read_text(encoding="utf-8"))
        if status is None or r.get("status") == status:
            out.append(r)
    return out


def accept_swms_request(cdir: Path, request_id: str, staff: str) -> str:
    if not re.fullmatch(r"R\d{14}[0-9a-f]{4}", request_id):
        raise ValueError("bad request id")
    p = requests_dir(cdir) / f"{request_id}.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    if rec.get("status") != "Pending":
        raise ValueError("already processed")
    reg = ee.find_register(cdir)
    wb = load_workbook(reg)
    job_id = next_id([r.get("Job ID") for r in read_sheet(wb, "Jobs")], "J")
    if rec.get("kind") == "assessment":
        row = {"Job ID": job_id, **assessment.jobs_row(rec, hazard_columns()), "SWMS status": "Requested",
               "SWMS requested at": dt.datetime.fromisoformat(rec["submitted_at"]),
               "Notes": f"Portal assessment {request_id}. {rec.get('notes', '')}".strip()}
        append_rows(wb["Jobs"], [row])
        wb.save(reg)
        folder = model.job_folder(cdir, row)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "assessment.json").write_text(json.dumps(_assessment_core(rec, request_id), indent=2), encoding="utf-8")
        rec.update({"status": "Accepted", "job_id": job_id, "accepted_by": staff,
                    "accepted_at": dt.datetime.now().isoformat(timespec="seconds")})
        p.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        _cache.clear()
        return job_id
    row = {"Job ID": job_id, "Client job ref": rec.get("client_ref"), "Site address": rec.get("site_address"),
           "State": rec.get("state"), "Principal / head contractor": rec.get("head_contractor"),
           "Scope of work": rec.get("scope"), "Start date": dt.date.fromisoformat(rec["start_date"]) if rec.get("start_date") else None,
           "Est. value ($)": rec.get("est_value") or None, "Plant and equipment": rec.get("plant"),
           "Other hazards": rec.get("other_hazards"), "Workers assigned (Person IDs)": rec.get("workers"),
           "SWMS status": "Requested", "SWMS requested at": dt.datetime.fromisoformat(rec["submitted_at"]),
           "Notes": f"Portal request {request_id}. Building age: {rec.get('building_age', '')}. {rec.get('site_notes', '')}".strip()}
    for f, col, _ in HAZARDS:
        row[col] = "Y" if rec.get(f) else "N"
    append_rows(wb["Jobs"], [row])
    wb.save(reg)
    rec.update({"status": "Accepted", "job_id": job_id, "accepted_by": staff,
                "accepted_at": dt.datetime.now().isoformat(timespec="seconds")})
    p.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return job_id


# ---------------------------------------------------------------------------
# Guided job assessment
# ---------------------------------------------------------------------------

def hazard_columns() -> dict[str, str]:
    hz, _ = model.load_library()
    return {k: m["job_column"] for k, m in hz.items() if m.get("job_column")}


def _assessment_core(rec: dict, request_id: str = "") -> dict:
    return {"job_type": rec.get("job_type"), "site": rec.get("site") or {}, "answers": rec.get("answers") or {},
            "crew": rec.get("crew") or [], "plant_other": rec.get("plant_other", ""), "notes": rec.get("notes", ""),
            "request_id": request_id or rec.get("request_id", ""), "submitted_by": rec.get("submitted_by", ""),
            "submitted_at": rec.get("submitted_at", "")}


def clean_assessment(payload: dict, valid_people: set[str]) -> tuple[dict | None, list[str]]:
    """Validate a browser payload. Returns (record fields, errors). Everything is re-derived server side."""
    errors = []
    if not isinstance(payload, dict):
        return None, ["The form didn't arrive properly. Please try again."]
    spec = assessment.load_spec()
    jt = str(payload.get("job_type") or "")
    if jt not in {j["id"] for j in spec["job_types"]}:
        errors.append("Choose a job type.")
    raw = payload.get("site") if isinstance(payload.get("site"), dict) else {}
    site = {k: str(raw.get(k) or "").strip()[:500] for k in ("site_address", "state", "start_date", "scope", "building_age",
                                                              "head_contractor", "client_ref")}
    if not site["site_address"]:
        errors.append("Add the site address.")
    if site["state"] not in ("ACT", "NSW"):
        errors.append("Choose ACT or NSW.")
    try:
        dt.date.fromisoformat(site["start_date"])
    except ValueError:
        errors.append("Add the start date.")
    if not site["scope"]:
        errors.append("Describe the job in a sentence.")
    if site["building_age"] not in {b["v"] for b in spec["building_ages"]}:
        errors.append("Say when the building was built.")
    answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
    rec = {"kind": "assessment", "job_type": jt, "site": site, "answers": answers,
           "crew": [c for c in (payload.get("crew") or []) if isinstance(c, str) and c in valid_people][:50],
           "plant_other": str(payload.get("plant_other") or "").strip()[:300], "notes": str(payload.get("notes") or "").strip()[:2000]}
    if not errors:
        d = assessment.evaluate_record(rec)
        rec["answers"] = d["clean"]            # drop anything that isn't a visible question with a valid option
        if d["missing"]:
            errors.append(f"{len(d['missing'])} question(s) still need an answer.")
    rec.update({"site_address": site["site_address"], "state": site["state"], "start_date": site["start_date"],
                "scope": site["scope"], "job_title": assessment.job_title(jt)})
    return rec, errors


def load_swms_request(cdir: Path, request_id: str) -> dict | None:
    if not re.fullmatch(r"R\d{14}[0-9a-f]{4}", request_id or ""):
        return None
    p = requests_dir(cdir) / f"{request_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def update_swms_request(cdir: Path, request_id: str, fields: dict):
    rec = load_swms_request(cdir, request_id)
    if not rec or rec.get("status") != "Pending":
        raise ValueError("That request can no longer be edited.")
    rec.update(fields)
    (requests_dir(cdir) / f"{request_id}.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")


def job_assessment(cdir: Path, job: dict) -> dict | None:
    return model.load_job_assessment(cdir, job)


def save_job_assessment(cdir: Path, job: dict, rec: dict, editor: str):
    """Staff edit after the job is on the register: rewrite assessment.json and the Jobs row it drives."""
    from swms.__main__ import _update_job
    core = _assessment_core(rec)
    old = model.load_job_assessment(cdir, job) or {}
    core.update({"request_id": old.get("request_id", ""), "submitted_by": old.get("submitted_by", ""),
                 "submitted_at": old.get("submitted_at", ""), "edited_by": editor,
                 "edited_at": dt.datetime.now().isoformat(timespec="seconds")})
    folder = model.job_folder(cdir, job)          # keep the existing folder even if the address changes
    _update_job(cdir, str(job["Job ID"]), assessment.jobs_row(rec, hazard_columns()))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "assessment.json").write_text(json.dumps(core, indent=2), encoding="utf-8")
    _cache.clear()


def assessment_summary(rec: dict) -> dict | None:
    if rec.get("kind") != "assessment":
        return None
    hz, _ = model.load_library()
    d = assessment.evaluate_record(rec)
    return {"hazards": [hz[h]["title"] for h in d["hazards"]], "stops": len(d["stops"]), "blockers": len(d["blockers"]),
            "checks": len(d["checks"])}


def assessment_boot(view: "ClientView", is_staff: bool, prefill: dict | None, today: dt.date) -> dict:
    hz, tk = model.load_library()
    people = []
    for pv in view.people:
        p = pv.person
        name = str(p.get("Full name") or "")
        people.append({"id": str(p.get("Person ID")), "name": name, "initials": initials(name), "roles": str(p.get("Roles") or ""),
                       "creds": [{"code": c.kind, "expiry": c.expiry.isoformat() if c.expiry else None,
                                  "no_expiry": c.status == "NO EXPIRY"} for c in pv.credentials]})
    codes = {c["code"] for m in hz.values() for c in (m.get("competencies") or [])}
    codes |= {e["need"]["code"] for q in assessment.load_spec()["questions"] for e in q["effects"] if "need" in e}
    states = sorted({x.strip().upper() for x in str(view.business.get("States operated") or "").replace(",", ";").split(";")}
                    & {"ACT", "NSW"})
    return {
        "client_id": view.client_id, "today": today.isoformat(), "is_staff": is_staff, "states": states, "people": people,
        "spec": assessment.client_spec(include_checks=is_staff), "prefill": prefill,
        "req": {"modules": {k: {"title": m["title"], "hrcw": m.get("hrcw"), "competencies": m.get("competencies") or []}
                            for k, m in hz.items()},
                "licences": tk["licences"], "template_licence": {t["id"]: t.get("licence", []) for t in tk["templates"]},
                "hrcw_all": model.HRCW_ALL, "any_one": sorted(model.ANY_ONE), "optional": ["ELEC_RESTRICTED"],
                "cred_names": {c: ee.short_label(c) for c in codes}},
    }


def initials(name: str) -> str:
    parts = [w for w in re.split(r"[^A-Za-z0-9]+", str(name or "")) if w]
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper() if parts else "?"


def load_rules_cached(_cache_box={}):
    if "rules" not in _cache_box:
        _cache_box["rules"] = load_rules(ee.RULES_PATH)
    return _cache_box["rules"]


CRED_NAMES = {c[0]: c[1] for c in schema.CREDENTIAL_TYPES}
INS_NAMES = {c[0]: c[1] for c in schema.INSURANCE_TYPES}
