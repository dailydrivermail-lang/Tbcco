import csv
import datetime as dt
import shutil
from pathlib import Path

import pytest
from openpyxl import load_workbook

from engine import expiry_engine as ee
from engine import intake_import, new_client, schema
from engine.register_io import add_months, load_rules, parse_date

ROOT = Path(__file__).resolve().parent.parent
TODAY = dt.date(2026, 11, 24)


@pytest.mark.parametrize("days,expected", [(-1, "EXPIRED"), (0, "DUE 7"), (7, "DUE 7"), (8, "DUE 30"),
                                           (30, "DUE 30"), (31, "DUE 60"), (60, "DUE 60"), (61, "CURRENT")])
def test_bucket_boundaries(days, expected):
    assert ee.bucket(TODAY + dt.timedelta(days=days), TODAY)[0] == expected


def test_bucket_special():
    assert ee.bucket(None, TODAY)[0] == "MISSING DATE"
    assert ee.bucket(None, TODAY, no_expiry=True)[0] == "NO EXPIRY"


def test_parse_date_formats():
    assert parse_date("05/03/2027") == dt.date(2027, 3, 5)  # Australian day-first
    assert parse_date("2027-03-05") == dt.date(2027, 3, 5)
    assert parse_date(dt.datetime(2027, 3, 5, 9)) == dt.date(2027, 3, 5)
    assert parse_date("not a date") is None
    assert add_months(dt.date(2026, 1, 31), 1) == dt.date(2026, 2, 28)


def _item(status, days, key="Credentials:L0001:x"):
    it = ee.Item("Credentials", "L0001", "P001", "X", "WHITE_CARD", "x", "1", TODAY, status, days)
    return it


def test_alerts_only_on_escalation_and_weekly_for_expired():
    state = {}
    it = _item("DUE 60", 50)
    ee.decide_alerts([it], state, TODAY)
    assert it.alert
    again = _item("DUE 60", 49)
    ee.decide_alerts([again], state, TODAY + dt.timedelta(days=1))
    assert not again.alert                       # same stage: no repeat
    worse = _item("DUE 30", 29)
    ee.decide_alerts([worse], state, TODAY + dt.timedelta(days=21))
    assert worse.alert                           # escalated
    exp = _item("EXPIRED", -1)
    ee.decide_alerts([exp], state, TODAY + dt.timedelta(days=51))
    assert exp.alert
    exp2 = _item("EXPIRED", -3)
    ee.decide_alerts([exp2], state, TODAY + dt.timedelta(days=53))
    assert not exp2.alert                        # within re-chase window
    exp3 = _item("EXPIRED", -8)
    ee.decide_alerts([exp3], state, TODAY + dt.timedelta(days=58))
    assert exp3.alert                            # weekly re-chase


def test_conditions():
    assert ee.eval_condition("") is True
    assert ee.eval_condition("flag:Designated first aider=Y", person={"Designated first aider": "y"}) is True
    assert ee.eval_condition("flag:Designated first aider=Y", person={}) is False
    assert ee.eval_condition("biz:Employees (FTE)>0", business={"Employees (FTE)": 3}) is True
    assert ee.eval_condition("biz:Employees (FTE)>0", business={}) is False
    assert ee.eval_condition("Operates a forklift") is None


def test_rules_library_integrity():
    rules = load_rules(ROOT / "rules" / "rules_library.csv")
    ids = [r["rule_id"] for r in rules]
    assert len(ids) == len(set(ids)), "duplicate rule ids"
    valid = {c[0] for c in schema.CREDENTIAL_TYPES} | {c[0] for c in schema.INSURANCE_TYPES}
    roles = {r.lower() for r in schema.ROLES}
    for r in rules:
        assert r["jurisdiction"] in ("ACT", "NSW", "ALL"), r["rule_id"]
        assert r["applies_to"] in ("Person", "Business", "Subcontractor", "Job"), r["rule_id"]
        assert r["confidence"][:1] in "ABC", r["rule_id"]
        assert r["source_instrument"], f"{r['rule_id']} has no source"
        for code in filter(None, r["evidence_code"].split("|")):
            assert code.startswith("DOC:") or code in valid, f"{r['rule_id']}: unknown code {code}"
        for role in filter(None, r["trigger_roles"].split(";")):
            assert role.strip().lower() in roles, f"{r['rule_id']}: unknown role {role}"


def test_gap_check():
    rules = load_rules(ROOT / "rules" / "rules_library.csv")
    business = {"States operated": "ACT", "Employees (FTE)": 5, "Legal name": "T"}
    people = [{"Person ID": "P001", "Full name": "A", "Roles": "Licensed plumber", "States worked": "ACT", "Active": "Y"}]
    creds = [{"Person ID": "P001", "Credential type": "ACT_PLUMBER"}, {"Person ID": "P001", "Credential type": "WHITE_CARD"}]
    gaps, confirm = ee.check_gaps(rules, business, people, [], creds, [], "C001")
    codes = {(g.holder_id, g.evidence) for g in gaps}
    assert ("P001", "ACT_PLUMBER") not in codes
    assert ("P001", "ACT_ASB_AWARE") in codes           # ACT mandatory asbestos awareness
    assert ("C001", "WC_ACT") in codes                  # employer without WC policy
    assert ("C001", "PL") in codes
    assert not any(g.evidence.startswith("NSW") for g in gaps)  # ACT-only business
    assert confirm                                       # conditional rules surface for confirmation


def test_end_to_end(tmp_path):
    master = tmp_path / "Master.xlsx"
    shutil.copy(ROOT / "templates" / "Master_Client_List.xlsx", master)
    cdir = new_client.create(tmp_path, "C123", "Test Plumbing", "Essentials", "ACT", master)
    assert (cdir / "00_Register" / "C123_Register.xlsx").exists()
    intake = tmp_path / "intake.xlsx"
    wb = load_workbook(ROOT / "intake" / "People_and_Licences_Intake.xlsx")
    ws = wb["People"]
    hdr = [c.value for c in ws[1]]
    vals = {"Full name": "Kim Test", "Role(s)": "Licensed plumber", "Works in (ACT / NSW / both)": "ACT",
            "Email": "kim@example.com", "Plumbing licence no.": "X1", "Plumbing licence state": "ACT",
            "Plumbing licence expiry": (TODAY + dt.timedelta(days=6)).strftime("%d/%m/%Y")}
    for k, v in vals.items():
        ws.cell(row=2, column=hdr.index(k) + 1, value=v)
    wb.save(intake)
    counts = intake_import.import_sheet(cdir, intake)
    assert counts["people"] == 1 and counts["credentials"] == 1
    res = ee.run_client(cdir, TODAY, master=master)
    lic = [i for i in res.items if i.kind == "ACT_PLUMBER"][0]
    assert lic.status == "DUE 7" and lic.alert
    assert any(p.suffix == ".eml" and "worker" in p.name for p in res.drafts)
    # second run same day: no new alerts
    res2 = ee.run_client(cdir, TODAY, master=master)
    assert not any(i.alert for i in res2.items)
    mw = load_workbook(master)
    assert mw["Clients"]["A2"].value == "C123"
    assert mw["Audit Log"]["A2"].value is not None
    # importing the same sheet twice must not duplicate people
    intake_import.import_sheet(cdir, intake)
    reg = load_workbook(cdir / "00_Register" / "C123_Register.xlsx")
    names = [c.value for c in reg["People"]["B"][1:] if c.value]
    assert names.count("Kim Test") == 1


def test_extraction_import(tmp_path):
    import json
    cdir = new_client.create(tmp_path, "C124", "X", "Standard", "ACT")
    f = tmp_path / "ex.json"
    f.write_text(json.dumps({"records": [
        {"record_type": "credential", "credential_type": "WHITE_CARD", "holder_name": "Nobody", "number": "W1",
         "no_expiry": True, "confidence": "High", "source_file": "a.jpg", "flags_for_reviewer": []},
        {"record_type": "insurance", "policy_type": "PL", "insured_name": "Sub Co", "policy_number": "P1",
         "expiry_date": "2027-06-30", "confidence": "Medium", "source_file": "b.pdf", "flags_for_reviewer": ["blurry"]},
    ]}))
    out = intake_import.import_extraction(cdir, f)
    assert out == {"credentials": 1, "insurances": 1, "skipped": 0, "unmatched_people": 1}
