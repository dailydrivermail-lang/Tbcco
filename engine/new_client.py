"""Create a new client folder from the template.

    python -m engine.new_client --root "/path/to/SharePoint/01_Clients" --id C001 --name "ABC Plumbing Pty Ltd" \
        --tier Standard --states "ACT;NSW" [--master /path/to/Master_Client_List.xlsx]

The folder layout is documented in docs/01-folder-structure.md. Change both together.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "Client_Register_TEMPLATE.xlsx"

CLIENT_FOLDERS = [
    "00_Register",
    "01_Intake_Inbox",            # client upload link (OneDrive 'Request files') and email attachments land here
    "01_Intake_Inbox/_processed",
    "02_People_Credentials",      # one subfolder per person: P001_John-Smith
    "03_Insurance/Client",
    "03_Insurance/Subcontractors",
    "04_Jobs",                    # one subfolder per job: J0001_12-Smith-St-Kambah
    "05_Chemicals_SDS",
    "06_Incidents",
    "07_Plant",
    "08_Policies_Procedures/Current",
    "08_Policies_Procedures/Superseded",
    "09_Client_Reports/Monthly",  # shared read-only with the client
    "09_Client_Reports/Quarterly",
    "09_Client_Reports/Registers",
    "10_Correspondence",
    "_outbox",                    # engine drafts awaiting human review (internal only)
    "_system",                    # alert state, engine run log (internal only)
    "99_Archive",
]

TIER_FEES = {"Essentials": 560, "Standard": 800, "Plus": 1040}


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:40]


def create(root: Path, cid: str, name: str, tier: str, states: str, master: Path | None = None) -> Path:
    if not re.fullmatch(r"C\d{3,}", cid):
        raise ValueError("Client ID must look like C001")
    d = root / f"{cid}_{slug(name)}"
    if d.exists():
        raise FileExistsError(d)
    for f in CLIENT_FOLDERS:
        (d / f).mkdir(parents=True, exist_ok=True)
    reg = d / "00_Register" / f"{cid}_Register.xlsx"
    shutil.copy(TEMPLATE, reg)
    wb = load_workbook(reg)
    ws = wb["Business"]
    hdr = [c.value for c in ws[1]]
    for k, v in {"Client ID": cid, "Legal name": name, "Service tier": tier, "States operated": states,
                 "Service start date": dt.date.today()}.items():
        ws.cell(row=2, column=hdr.index(k) + 1, value=v)
    wb.save(reg)
    if master:
        mw = load_workbook(master)
        ms = mw["Clients"]
        mh = [c.value for c in ms[1]]
        r = 2
        while ms.cell(row=r, column=1).value not in (None, ""):
            r += 1
        for k, v in {"Client ID": cid, "Legal name": name, "Tier": tier, "Monthly fee ($)": TIER_FEES.get(tier),
                     "States": states, "Trades": "Plumbing", "Status": "Onboarding", "Start date": dt.date.today(),
                     "Folder link": str(d), "Register file": str(reg)}.items():
            ms.cell(row=r, column=mh.index(k) + 1, value=v)
        mw.save(master)
    return d


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--tier", default="Standard", choices=list(TIER_FEES))
    ap.add_argument("--states", default="ACT")
    ap.add_argument("--master", type=Path)
    a = ap.parse_args(argv)
    print(create(a.root, a.id, a.name, a.tier, a.states, a.master))


if __name__ == "__main__":
    main()
