"""Build a fictional demo client end to end: scaffold, intake, import, engine run.

    python examples/make_demo.py [--today 2026-11-24]

Everything here is made up. Use it for training, the pilot pitch, and regression checks.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import expiry_engine, intake_import, new_client  # noqa: E402

OUT = ROOT / "examples" / "demo"
DEMO_TODAY = dt.date(2026, 11, 24)


def placeholder_pdf(path: Path, title: str, lines: list[str]):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, 780, title)
    c.setFont("Helvetica", 11)
    y = 750
    for ln in ["DEMO DOCUMENT - FICTIONAL DATA - NOT FOR USE"] + lines:
        c.drawString(60, y, ln)
        y -= 18
    c.save()


def set_row(ws, values: dict, row: int | None = None):
    hdr = [c.value for c in ws[1]]
    if row is None:
        row = 2
        while ws.cell(row=row, column=1).value not in (None, ""):
            row += 1
    for k, v in values.items():
        ws.cell(row=row, column=hdr.index(k) + 1, value=v)


def d(today, days):
    return (today + dt.timedelta(days=days)).strftime("%d/%m/%Y")


def fill_intake(path: Path, today: dt.date):
    wb = load_workbook(ROOT / "intake" / "People_and_Licences_Intake.xlsx")
    ppl = wb["People"]
    hdr = [c.value for c in ppl[1]]

    def row(**kv):
        r = ppl.max_row + 1
        for k, v in kv.items():
            ppl.cell(row=r, column=hdr.index(k) + 1, value=v)

    row(**{"Full name": "Sam Example", "Employee / apprentice / subcontractor": "Employee", "Role(s)": "Licensed plumber; Drainer; Gasfitter; Supervisor / foreman",
           "Works in (ACT / NSW / both)": "ACT;NSW", "Mobile": "0400 000 001", "Email": "sam@example.com", "Designated first aider? (Y/N)": "Y",
           "Plumbing licence no.": "ACT-PL-0001", "Plumbing licence state": "ACT", "Plumbing licence class": "Sanitary plumber", "Plumbing licence expiry": d(today, 25),
           "Drainer licence no.": "ACT-DR-0001", "Drainer licence state": "ACT", "Drainer licence expiry": d(today, 300),
           "Gasfitter licence no.": "ACT-GF-0001", "Gasfitter licence state": "ACT", "Gasfitter class (general/advanced/LPG)": "General", "Gasfitter licence expiry": d(today, 400),
           "White Card no.": "WC-111", "White Card state": "ACT", "Asbestos awareness (11084NAT) date": "01/02/2020", "Silica (10830NAT) date": "01/08/2023",
           "First aid (HLTAID011) expiry": d(today, -10), "CPR (HLTAID009) expiry": d(today, 5)})
    row(**{"Full name": "Alex Sample", "Employee / apprentice / subcontractor": "Apprentice", "Role(s)": "Apprentice",
           "Works in (ACT / NSW / both)": "ACT", "Mobile": "0400 000 002",
           "White Card no.": "WC-222", "White Card state": "NSW", "Asbestos awareness (11084NAT) date": "05/03/2025"})
    row(**{"Full name": "Jo Placeholder", "Employee / apprentice / subcontractor": "Subcontractor (individual)", "Subcontractor business name": "Placeholder Drainage",
           "Role(s)": "Drainer; Plant operator", "Works in (ACT / NSW / both)": "NSW", "Email": "jo@example.com",
           "Drainer licence no.": "NSW-123456C", "Drainer licence state": "NSW", "Drainer licence expiry": d(today, 55),
           "High risk work licence no.": "HRW-999", "HRWL classes": "LF", "HRWL expiry": d(today, 900)})
    sub = wb["Subcontractors"]
    sh = [c.value for c in sub[1]]
    for k, v in {"Business name": "Placeholder Drainage", "ABN": "00000000000", "Trade": "Drainage", "Contact name": "Jo Placeholder",
                 "Contact email": "jo@example.com", "Public liability insurer": "Example Insurer", "PL policy no.": "PL-777",
                 "PL limit ($)": 20000000, "PL expiry": d(today, -3)}.items():
        sub.cell(row=2, column=sh.index(k) + 1, value=v)
    ch = wb["Chemicals"]
    ch.append(["PVC solvent cement", "Example Co", "Joining PVC pipe", "Van 1", "N"])
    pl = wb["Plant"]
    pl.append(["Drain jetter", "JetCo 3000", "SN-1", d(today, -100), "Y"])
    wb.save(path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", type=lambda s: dt.date.fromisoformat(s), default=DEMO_TODAY)
    a = ap.parse_args(argv)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    master = OUT / "Master_Client_List.xlsx"
    shutil.copy(ROOT / "templates" / "Master_Client_List.xlsx", master)
    cdir = new_client.create(OUT, "C000", "Demo Plumbing Pty Ltd", "Standard", "ACT;NSW", master)
    # Business details the onboarding form would capture
    reg = next((cdir / "00_Register").glob("*_Register.xlsx"))
    wb = load_workbook(reg)
    ws = wb["Business"]
    hdr = [c.value for c in ws[1]]
    for k, v in {"Trading name": "Demo Plumbing", "ABN": "00000000000", "Trades": "Plumbing; Drainage; Gasfitting",
                 "Employees (FTE)": 12, "Primary contact": "Pat Owner", "Primary contact email": "pat@example.com",
                 "Primary contact mobile": "0400 000 000"}.items():
        ws.cell(row=2, column=hdr.index(k) + 1, value=v)
    ins = wb["Insurances"]
    ih = [c.value for c in ins[1]]
    for k, v in {"Insurance ID": "I001", "Holder type": "Client", "Holder ID": "C000", "Holder name": "Demo Plumbing Pty Ltd",
                 "Policy type": "PL", "Insurer": "Example Insurer", "Policy number": "PL-001", "Sum insured / limit": 20000000,
                 "Expiry date": a.today + dt.timedelta(days=45), "Verification": "Verified - document"}.items():
        ins.cell(row=2, column=ih.index(k) + 1, value=v)
    set_row(wb["Jobs"], {"Job ID": "J0001", "Client job ref": "DP-1042", "Site address": "12 Example St, Kambah ACT", "State": "ACT",
                         "Principal / head contractor": "Example Builders", "Scope of work": "Replace sewer line under driveway, new boundary trap",
                         "Start date": a.today - dt.timedelta(days=3), "Hazard: trench over 1.5m": "Y", "Hazard: asbestos": "Y",
                         "Hazard: traffic / mobile plant": "Y", "SWMS status": "Requested",
                         "Plant and equipment": "1.7 t excavator, trench shield, plate compactor",
                         "Workers assigned (Person IDs)": "P001; P002",
                         "SWMS requested at": dt.datetime.combine(a.today - dt.timedelta(days=6), dt.time(9, 15))})
    set_row(wb["Jobs"], {"Job ID": "J0002", "Site address": "3 Sample Pl, Queanbeyan NSW", "State": "NSW",
                         "Scope of work": "Hot water heat pump install", "Start date": a.today + dt.timedelta(days=4),
                         "Hazard: live electrical": "Y", "SWMS status": "Requested",
                         "Workers assigned (Person IDs)": "Sam Example, Jo",
                         "SWMS requested at": dt.datetime.combine(a.today - dt.timedelta(days=1), dt.time(14, 5))})
    set_row(wb["Documents"], {"Document ID": "D001", "Title": "WHS Policy", "Category": "Policy", "Version": "1.0",
                              "Owner": "Pat Owner", "Approved date": a.today - dt.timedelta(days=340), "Review interval (months)": 12})
    wb.save(reg)
    placeholder_pdf(cdir / "09_Client_Reports" / "Monthly" / f"C000_Monthly_Summary_{a.today:%Y-%m}.pdf",
                    "Monthly compliance summary", ["What we did, what's coming up, what we need from you"])

    # Second fictional client, all green, to exercise the staff view and client isolation
    c2 = new_client.create(OUT, "C001", "Example Gas and Drain Pty Ltd", "Essentials", "ACT", master)
    reg2 = next((c2 / "00_Register").glob("*_Register.xlsx"))
    w2 = load_workbook(reg2)
    set_row(w2["Business"], {"Trading name": "Example Gas & Drain", "Employees (FTE)": 0, "Primary contact": "Lee Sample"}, row=2)
    set_row(w2["People"], {"Person ID": "P001", "Full name": "Lee Sample", "Person type": "Employee", "Roles": "Gasfitter",
                           "States worked": "ACT", "Active": "Y"})
    for i, (code, num, exp) in enumerate([("ACT_GASFITTER", "ACT-GF-9", 500), ("WHITE_CARD", "WC-9", None),
                                          ("ACT_ASB_AWARE", "SoA", None), ("ACT_SILICA", "SoA", None)], start=1):
        set_row(w2["Credentials"], {"Credential ID": f"L{i:04d}", "Person ID": "P001", "Credential type": code,
                                    "Licence / card number": num, "Verification": "Verified - document",
                                    "Expiry date": a.today + dt.timedelta(days=exp) if exp else None,
                                    "No expiry": None if exp else "Y"})
    set_row(w2["Insurances"], {"Insurance ID": "I001", "Holder type": "Client", "Holder ID": "C001", "Policy type": "PL",
                               "Policy number": "PL-9", "Expiry date": a.today + dt.timedelta(days=200),
                               "Verification": "Verified - document"})
    w2.save(reg2)

    filled = cdir / "01_Intake_Inbox" / "Filled_People_and_Licences_Intake.xlsx"
    fill_intake(filled, a.today)
    print("import:", intake_import.import_sheet(cdir, filled))
    # SWMS: J0001 drafted, reviewed and issued; J0002 drafted and still in review (has blockers)
    from swms.__main__ import draft as swms_draft, issue as swms_issue
    import json
    from swms import assessment, model
    rec = {"kind": "assessment", "job_type": "drainage",
           "site": {"site_address": "12 Example St, Kambah ACT", "state": "ACT", "start_date": (a.today - dt.timedelta(days=3)).isoformat(),
                    "scope": "Replace sewer line under driveway, new boundary trap", "building_age": "pre1990",
                    "head_contractor": "Example Builders", "client_ref": "DP-1042"},
           "answers": {"exc_depth": "gt15", "exc_support": "shield", "exc_ground": "stable", "exc_adjacent": "no", "exc_byda": "have",
                       "exc_services": ["none"], "exc_method": "machine", "exc_operator": "own", "sew_live": "yes", "sew_entry": "no",
                       "sur_road": "private", "sur_occupied": "yes", "asb_disturb": "yes", "asb_known": "assume", "asb_amount": "avoid",
                       "sil_cut": "no", "hot_any": "no", **{q: "yes" for q in ("q_induct", "q_toolbox", "q_ppe", "q_firstaid", "q_tag",
                                                                               "q_rcd", "q_sds", "q_rpe", "q_ladder", "q_prestart")}},
           "crew": ["P001", "P002"], "plant_other": "Plate compactor", "notes": "", "submitted_by": "pat@example.com",
           "submitted_at": dt.datetime.combine(a.today - dt.timedelta(days=6), dt.time(9, 15)).isoformat()}
    assert not assessment.evaluate_record(rec)["missing"]
    jf = model.job_folder(cdir, {"Job ID": "J0001", "Site address": "12 Example St, Kambah ACT"})
    jf.mkdir(parents=True, exist_ok=True)
    (jf / "assessment.json").write_text(json.dumps(rec, indent=2))
    swms_draft(cdir, "J0001", master, a.today)
    swms_issue(cdir, "J0001", "I. Reviewer", master, today=a.today)
    swms_draft(cdir, "J0002", master, a.today)
    res = expiry_engine.run_client(cdir, a.today, master=master)
    print(f"engine: RAG={res.rag} items={len(res.items)} alerts={sum(i.alert for i in res.items)} missing={len(res.gaps)}")
    for p in res.drafts:
        print("  draft:", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
