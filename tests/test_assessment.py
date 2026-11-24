import itertools
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from swms import assessment, model

ROOT = Path(__file__).resolve().parent.parent
SPEC = assessment.load_spec()


def ev(**a):
    return assessment.evaluate(a)


def test_spec_is_well_formed():
    hz, tk = model.load_library()
    step_ids = {s["id"] for m in hz.values() for s in m["steps"]}
    templates = {t["id"] for t in tk["templates"]}
    ids = [q["id"] for q in SPEC["questions"]]
    assert len(ids) == len(set(ids))
    sections = {s for j in SPEC["job_types"] for s in j["sections"]}
    codes = {c[0] for c in __import__("engine.schema", fromlist=["x"]).CREDENTIAL_TYPES}

    def refs(c):
        if not c:
            return []
        for k in ("all", "any"):
            if k in c:
                return [r for x in c[k] for r in refs(x)]
        if "not" in c:
            return refs(c["not"])
        return [(c["q"], c["in"])]

    opts = {q["id"]: {o["v"] for o in q["options"]} for q in SPEC["questions"]}
    opts.update(job_type={j["id"] for j in SPEC["job_types"]}, state={"ACT", "NSW"},
                building_age={b["v"] for b in SPEC["building_ages"]})
    for j in SPEC["job_types"]:
        assert j["template"] in templates
        assert all(s in SPEC["section_titles"] for s in j["sections"])
    for q in SPEC["questions"]:
        assert q["priority"] in assessment.PRIORITIES, q["id"]
        assert q["short"] and q["ask"], q["id"]
        if q["priority"] == "key":
            assert q.get("why"), f"{q['id']}: key questions must explain why"
        if q["priority"] != "quick":
            assert q["section"] in sections, q["id"]
        for qid, values in refs(q.get("when")) + [r for e in q["effects"] for r in refs(e.get("when"))]:
            assert qid in opts, f"{q['id']}: unknown reference {qid}"
            assert set(map(str, values)) <= opts[qid], f"{q['id']}: bad values for {qid}"
        for e in q["effects"]:
            assert set(map(str, e["if"])) <= opts[q["id"]], q["id"]
            if "hazard" in e:
                assert e["hazard"] in hz, q["id"]
            if "control" in e:
                assert e["control"]["step"] in step_ids and e["control"]["h"] in model.HIERARCHY, q["id"]
            if "need" in e:
                assert e["need"]["code"] in codes and e["need"]["who"] in ("any", "all"), q["id"]
            if "licence" in e:
                assert e["licence"] in tk["licences"], q["id"]
            for i in e.get("hrcw", []):
                assert 0 <= i < len(model.HRCW_ALL)
        # "not sure" on a key question must never pass silently
        if q["priority"] == "key":
            for o in q["options"]:
                if o["v"] in ("unsure", "unknown", "undecided"):
                    hit = [e for e in q["effects"] if o["v"] in map(str, e["if"])]
                    assert any(("blocker" in e or "check" in e or "hazard" in e or "control" in e) for e in hit) or \
                        any(o["v"] in map(str, vals) for other in SPEC["questions"] for _, vals in refs(other.get("when"))
                            if _ == q["id"]), f"{q['id']}: '{o['v']}' has no consequence"


def test_cascade_only_asks_relevant_questions():
    r = ev(job_type="drainage", state="ACT", building_age="post2003")
    assert r["visible"][0] == "exc_depth"
    assert "exc_support" not in r["visible"] and "asb_disturb" not in r["visible"]   # nothing asked until triggered
    assert not any(v.startswith(("hw_", "gas_", "roof_", "ht_")) for v in r["visible"])
    r = ev(job_type="drainage", state="ACT", building_age="post2003", exc_depth="none")
    assert not any(v in r["visible"] for v in ("exc_support", "exc_byda", "exc_services", "exc_method", "q_ladder"))
    r = ev(job_type="drainage", state="ACT", building_age="post2003", exc_depth="gt15")
    assert {"exc_support", "exc_ground", "exc_byda", "exc_services", "q_ladder"} <= set(r["visible"])
    assert "trench" in r["hazards"]
    # hot water: electric unit never asks about refrigerant or roof falls
    r = ev(job_type="hot_water", state="NSW", building_age="post2003", hw_new="electric", hw_old="electric", hw_location="ground")
    assert "hw_refrig" not in r["visible"] and "ht_fall" not in r["visible"] and "hw_elec" in r["visible"]
    r = ev(job_type="hot_water", state="NSW", building_age="post2003", hw_new="heatpump", hw_location="roof")
    assert "hw_refrig" in r["visible"] and "ht_fall" in r["visible"]


def test_answers_to_hidden_questions_are_ignored():
    r = ev(job_type="drainage", state="ACT", building_age="post2003", exc_depth="none", exc_support="undecided", hw_new="gas_cf")
    assert not r["blockers"] and "gas" not in r["hazards"] and "exc_support" not in r["clean"]


def test_unsure_takes_the_higher_risk_path_and_blocks():
    r = ev(job_type="drainage", state="ACT", building_age="post2003", exc_depth="unsure")
    assert "trench" in r["hazards"] and any("depth not known" in b for b in r["blockers"])
    r = ev(job_type="roof", state="NSW", building_age="post2003", ht_fall="yes", ht_control="ladder")
    assert any("ladder only" in b for b in r["blockers"])


def test_asbestos_path_and_stop():
    base = dict(job_type="general", state="ACT", building_age="pre1990", gen_where=["wet"], asb_disturb="yes")
    r = ev(**base, asb_known="assume", asb_amount="small")
    assert "asbestos" in r["hazards"] and not r["stops"] and any("ACT" in c for c in r["checks"])
    r = ev(**{**base, "state": "NSW"}, asb_known="assume", asb_amount="small")
    assert not any("ACT" in c for c in r["checks"])
    r = ev(**base, asb_known="present", asb_amount="friable")
    assert r["stops"] and "licensed asbestos removalist" in r["stops"][0]
    r = ev(**{**base, "building_age": "post2003"})
    assert "asb_disturb" not in r["visible"]


def test_needs_licences_controls_and_quick_checks():
    r = ev(job_type="hot_water", state="NSW", building_age="post2003", hw_new="heatpump", hw_old="gas", hw_elec="restricted",
           hw_refrig="split", hw_location="ground", hw_move="trolley", hot_any="yes", hot_combust="yes", hot_permit="no",
           q_ext="no", q_ppe="yes")
    assert {"code": "ARCTICK_RHL", "who": "any"} in r["needs"] and {"code": "ELEC_RESTRICTED", "who": "any"} in r["needs"]
    assert "gas" in r["licences"] and {"gas", "electrical", "hotworks"} <= set(r["hazards"])
    assert any(c["step"] == "hotwork" for c in r["controls"])
    assert [q["id"] for q in r["quick_no"]] == ["q_ext"] and any("extinguisher" in c for c in r["checks"])
    assert 9 in r["hrcw"]


def test_client_spec_hides_reviewer_wording():
    pub = json.dumps(assessment.client_spec())
    assert "pending legal review" not in pub and "no_flag" not in pub
    assert "pending legal review" in json.dumps(assessment.client_spec(include_checks=True))


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_javascript_engine_matches_python(tmp_path):
    rnd = random.Random(7)
    cases = []
    for jt, state, age in itertools.product([j["id"] for j in SPEC["job_types"]], ["ACT", "NSW"],
                                            [b["v"] for b in SPEC["building_ages"]]):
        for _ in range(12):
            a = {"job_type": jt, "state": state, "building_age": age}
            for q in SPEC["questions"]:
                if rnd.random() < 0.8:
                    vs = [o["v"] for o in q["options"]]
                    a[q["id"]] = rnd.sample(vs, rnd.randint(1, min(3, len(vs)))) if q["type"] == "multi" else rnd.choice(vs)
            cases.append(a)
    (tmp_path / "in.json").write_text(json.dumps({"spec": SPEC, "cases": cases}))
    script = ("const E=require(process.argv[1]);const d=JSON.parse(require('fs').readFileSync(process.argv[2]));"
              "process.stdout.write(JSON.stringify(d.cases.map(c=>E.evaluate(c,d.spec))))")
    out = subprocess.run(["node", "-e", script, str(ROOT / "portal/static/js/assessment-engine.js"), str(tmp_path / "in.json")],
                         capture_output=True, text=True, check=True).stdout
    js = json.loads(out)
    assert len(js) == len(cases) == 480
    for case, got in zip(cases, js):
        assert got == assessment.evaluate(case), case


def test_triage_is_well_formed():
    t = SPEC["triage"]
    opts = {q["id"]: {o["v"] for o in q["options"]} for q in SPEC["questions"]}
    vals = [o["v"] for o in t["options"]]
    assert "none" in vals and "unsure" in vals and len(vals) == len(set(vals))
    for o in t["options"]:
        if "hrcw" in o:
            assert 0 <= o["hrcw"] < len(model.HRCW_ALL)
        for qid, v in (o.get("sets") or {}).items():
            assert v in opts[qid], (o["v"], qid, v)
    # every pre-filled answer must switch on a hazard or open the follow-up that does
    r = assessment.evaluate({"job_type": "general", "state": "ACT", "building_age": "pre1990", "gen_where": ["roof", "outside"],
                             "ht_fall": "yes", "exc_depth": "gt15", "sew_entry": "yes", "gen_gas": "yes"})
    assert {"height", "trench", "confined", "gas"} <= set(r["hazards"])
