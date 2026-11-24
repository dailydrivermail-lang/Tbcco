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

    row(**{"Full name": "Sam Example", "Employee / apprentice / subcontractor": "Employee", "Role(s)": "Licensed plumber; Gasfitter; Supervisor / foreman",
           "Works in (ACT / NSW / both)": "ACT;NSW", "Mobile": "0400 000 001", "Email": "sam@example.com", "Designated first aider? (Y/N)": "Y",
           "Plumbing licence no.": "ACT-PL-0001", "Plumbing licence state": "ACT", "Plumbing licence class": "Sanitary plumber", "Plumbing licence expiry": d(today, 25),
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", type=lambda s: dt.date.fromisoformat(s), default=dt.date(2026, 11, 24))
    a = ap.parse_args()
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
    wb.save(reg)

    filled = cdir / "01_Intake_Inbox" / "Filled_People_and_Licences_Intake.xlsx"
    fill_intake(filled, a.today)
    print("import:", intake_import.import_sheet(cdir, filled))
    res = expiry_engine.run_client(cdir, a.today, master=master)
    print(f"engine: RAG={res.rag} items={len(res.items)} alerts={sum(i.alert for i in res.items)} missing={len(res.gaps)}")
    for p in res.drafts:
        print("  draft:", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
