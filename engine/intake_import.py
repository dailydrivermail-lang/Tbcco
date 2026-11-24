"""Load intake data into a client register.

Two sources:

  1. The client's filled-in People_and_Licences_Intake.xlsx (onboarding):
       python -m engine.intake_import sheet --client-dir PATH --file Filled_Intake.xlsx

  2. Claude's structured extraction of uploaded documents (licence photos, certificates of currency),
     produced with intake/claude/extract_document_prompt.md and saved as JSON:
       python -m engine.intake_import extraction --client-dir PATH --file extractions.json

Every imported row is marked Verification = 'Unverified'. A human must check it against the document
or the public register before it counts as verified. Nothing is overwritten: rows are appended.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from openpyxl import load_workbook

from engine import schema
from engine.expiry_engine import find_register
from engine.register_io import append_rows, next_id, parse_date, read_sheet

VALID_CREDS = {c[0] for c in schema.CREDENTIAL_TYPES}
VALID_INS = {c[0] for c in schema.INSURANCE_TYPES}


def _norm(s) -> str:
    return " ".join(str(s or "").lower().split())


def _licence_code(kind: str, state: str) -> tuple[str, str]:
    """Map an intake licence column group plus its state to a credential code.
    For NSW we can't tell trade/QS/contractor from the intake sheet, so a note asks the reviewer to confirm."""
    st = (state or "").upper()
    if "NSW" in st:
        return "NSW_TRADE_PDG", "NSW: confirm certificate type (tradesperson / qualified supervisor / contractor) from the card."
    return {"plumb": "ACT_PLUMBER", "drain": "ACT_DRAINER", "gas": "ACT_GASFITTER"}[kind], ""


def import_sheet(client_dir: Path, file: Path) -> dict:
    reg_path = find_register(client_dir)
    wb = load_workbook(reg_path)
    src = load_workbook(file, data_only=True)
    people_existing = read_sheet(wb, "People")
    subs_existing = read_sheet(wb, "Subcontractors")
    cred_ids = [r.get("Credential ID") for r in read_sheet(wb, "Credentials")]
    ins_ids = [r.get("Insurance ID") for r in read_sheet(wb, "Insurances")]
    pids = [r.get("Person ID") for r in people_existing]
    sids = [r.get("Subcontractor ID") for r in subs_existing]
    known_people = {_norm(r.get("Full name")): r.get("Person ID") for r in people_existing}
    known_subs = {_norm(r.get("Business name")): r.get("Subcontractor ID") for r in subs_existing}
    new_people, new_creds, new_subs, new_ins, new_chems, new_plant = [], [], [], [], [], []
    base = {"Verification": "Unverified", "Intake source": "Onboarding form", "Extracted by": "Human"}

    def cred(pid, code, number, expiry=None, cls=None, juris=None, no_exp=False, note=""):
        cid = next_id(cred_ids, "L")
        cred_ids.append(cid)
        new_creds.append({**base, "Credential ID": cid, "Person ID": pid, "Credential type": code,
                          "Licence / card number": number, "Class / categories": cls, "Jurisdiction": juris,
                          "Expiry date": parse_date(expiry), "No expiry": "Y" if no_exp else None, "Notes": note or None})

    # Subcontractors first so people can link to them
    for r in read_sheet(src, "Subcontractors"):
        name = r.get("Business name")
        if not name:
            continue
        sid = known_subs.get(_norm(name))
        if not sid:
            sid = next_id(sids, "S", 3)
            sids.append(sid)
            known_subs[_norm(name)] = sid
            new_subs.append({"Subcontractor ID": sid, "Business name": name, "ABN": r.get("ABN"), "Trade": r.get("Trade"),
                             "Contact name": r.get("Contact name"), "Contact email": r.get("Contact email"),
                             "Contact mobile": r.get("Contact mobile"), "Active": "Y"})
        for code, ins_name, pol, exp, lim in (("PL", "Public liability insurer", "PL policy no.", "PL expiry", "PL limit ($)"),
                                              (None, "Workers' comp insurer", "WC policy no.", "WC expiry", None)):
            if r.get(pol) or r.get(exp):
                iid = next_id(ins_ids, "I", 3)
                ins_ids.append(iid)
                new_ins.append({"Insurance ID": iid, "Holder type": "Subcontractor", "Holder ID": sid, "Holder name": name,
                                "Policy type": code or "WC_ACT", "Insurer": r.get(ins_name), "Policy number": r.get(pol),
                                "Sum insured / limit": r.get(lim) if lim else None, "Expiry date": parse_date(r.get(exp)),
                                "Verification": "Unverified",
                                "Notes": None if code else "WC state assumed ACT: confirm from the certificate."})

    for r in read_sheet(src, "People"):
        name = r.get("Full name")
        if not name:
            continue
        pid = known_people.get(_norm(name))
        if not pid:
            pid = next_id(pids, "P", 3)
            pids.append(pid)
            known_people[_norm(name)] = pid
            ptype = r.get("Employee / apprentice / subcontractor")
            new_people.append({"Person ID": pid, "Full name": name, "Person type": ptype,
                               "Subcontractor ID": known_subs.get(_norm(r.get("Subcontractor business name"))),
                               "Roles": r.get("Role(s)"), "States worked": r.get("Works in (ACT / NSW / both)"),
                               "Mobile": r.get("Mobile"), "Email": r.get("Email"),
                               "Alert channel": ("Email+SMS" if r.get("Email") and r.get("Mobile") else "SMS" if r.get("Mobile")
                                                 else "Email" if r.get("Email") else "Client only"),
                               "Active": "Y", "Designated first aider": r.get("Designated first aider? (Y/N)")})
        for kind, no, st, cls, exp in (("plumb", "Plumbing licence no.", "Plumbing licence state", "Plumbing licence class", "Plumbing licence expiry"),
                                       ("drain", "Drainer licence no.", "Drainer licence state", None, "Drainer licence expiry"),
                                       ("gas", "Gasfitter licence no.", "Gasfitter licence state", "Gasfitter class (general/advanced/LPG)", "Gasfitter licence expiry")):
            if r.get(no):
                code, note = _licence_code(kind, r.get(st))
                cred(pid, code, r.get(no), r.get(exp), r.get(cls) if cls else None, r.get(st), note=note)
        if r.get("White Card no."):
            cred(pid, "WHITE_CARD", r.get("White Card no."), juris=r.get("White Card state"), no_exp=True)
        if r.get("Asbestos awareness (11084NAT) date"):
            cred(pid, "ACT_ASB_AWARE", "SoA", no_exp=True, note=f"Completed {r.get('Asbestos awareness (11084NAT) date')}. Confirm the RTO is approved.")
        if r.get("Silica (10830NAT) date"):
            cred(pid, "ACT_SILICA", "SoA", no_exp=True, note=f"Completed {r.get('Silica (10830NAT) date')}")
        if r.get("First aid (HLTAID011) expiry"):
            cred(pid, "FIRST_AID", "SoA", r.get("First aid (HLTAID011) expiry"))
        if r.get("CPR (HLTAID009) expiry"):
            cred(pid, "CPR", "SoA", r.get("CPR (HLTAID009) expiry"))
        if r.get("High risk work licence no."):
            classes = str(r.get("HRWL classes") or "").upper().replace(",", " ").split()
            for c in classes or ["OTHER"]:
                code = f"HRWL_{c}" if f"HRWL_{c}" in VALID_CREDS else "HRWL_OTHER"
                cred(pid, code, r.get("High risk work licence no."), r.get("HRWL expiry"), cls=c)
        if r.get("ARCtick licence no."):
            cred(pid, "ARCTICK_RHL", r.get("ARCtick licence no."), r.get("ARCtick expiry"))
        if r.get("Other tickets (name, number, expiry)"):
            cred(pid, "OTHER", "see notes", note=str(r.get("Other tickets (name, number, expiry)")) + " (split into separate rows)")

    ch_ids = [r.get("Chemical ID") for r in read_sheet(wb, "Chemicals")]
    for r in read_sheet(src, "Chemicals"):
        if r.get("Product name"):
            i = next_id(ch_ids, "CH", 3)
            ch_ids.append(i)
            new_chems.append({"Chemical ID": i, "Product name": r.get("Product name"), "Manufacturer / supplier": r.get("Manufacturer"),
                              "Used for": r.get("Used for"), "Where stored / max quantity": r.get("Where stored")})
    pl_ids = [r.get("Plant ID") for r in read_sheet(wb, "Plant")]
    for r in read_sheet(src, "Plant"):
        if r.get("Item"):
            i = next_id(pl_ids, "PL", 3)
            pl_ids.append(i)
            new_plant.append({"Plant ID": i, "Description": r.get("Item"), "Make / model": r.get("Make / model"),
                              "Serial / rego": r.get("Serial / rego"), "Last inspection / test": parse_date(r.get("Last service / test-and-tag date"))})

    for sheet, rows in (("People", new_people), ("Subcontractors", new_subs), ("Credentials", new_creds),
                        ("Insurances", new_ins), ("Chemicals", new_chems), ("Plant", new_plant)):
        if rows:
            append_rows(wb[sheet], rows)
    wb.save(reg_path)
    return {"people": len(new_people), "subcontractors": len(new_subs), "credentials": len(new_creds),
            "insurances": len(new_ins), "chemicals": len(new_chems), "plant": len(new_plant)}


def import_extraction(client_dir: Path, file: Path) -> dict:
    """Append Claude extraction records (see intake/claude/extract_document_prompt.md)."""
    data = json.loads(Path(file).read_text(encoding="utf-8"))
    records = data if isinstance(data, list) else data.get("records", [])
    reg_path = find_register(client_dir)
    wb = load_workbook(reg_path)
    people = read_sheet(wb, "People")
    subs = read_sheet(wb, "Subcontractors")
    by_name = {_norm(p.get("Full name")): p.get("Person ID") for p in people}
    sub_by_name = {_norm(s.get("Business name")): s.get("Subcontractor ID") for s in subs}
    cred_ids = [r.get("Credential ID") for r in read_sheet(wb, "Credentials")]
    ins_ids = [r.get("Insurance ID") for r in read_sheet(wb, "Insurances")]
    creds, ins, skipped = [], [], []
    for rec in records:
        kind = rec.get("record_type")
        flags = "; ".join(rec.get("flags_for_reviewer") or [])
        if kind == "credential":
            code = rec.get("credential_type") if rec.get("credential_type") in VALID_CREDS else "OTHER"
            pid = by_name.get(_norm(rec.get("holder_name")), "UNMATCHED")
            cid = next_id(cred_ids, "L")
            cred_ids.append(cid)
            creds.append({"Credential ID": cid, "Person ID": pid, "Credential type": code,
                          "Jurisdiction": rec.get("jurisdiction"), "Licence / card number": rec.get("number"),
                          "Class / categories": rec.get("class_or_categories"), "Endorsements / conditions": rec.get("endorsements"),
                          "Issuer": rec.get("issuer"), "Issue date": parse_date(rec.get("issue_date")),
                          "Expiry date": parse_date(rec.get("expiry_date")), "No expiry": "Y" if rec.get("no_expiry") else None,
                          "Verification": "Unverified", "Evidence file": rec.get("source_file"), "Intake source": "Upload folder",
                          "Extracted by": "Claude", "Extraction confidence": rec.get("confidence"),
                          "Notes": (f"Holder on document: {rec.get('holder_name')}. " if pid == "UNMATCHED" else "") + flags or None})
        elif kind == "insurance":
            code = rec.get("policy_type") if rec.get("policy_type") in VALID_INS else "OTHER"
            holder = rec.get("insured_name")
            sid = sub_by_name.get(_norm(holder))
            iid = next_id(ins_ids, "I", 3)
            ins_ids.append(iid)
            ins.append({"Insurance ID": iid, "Holder type": "Subcontractor" if sid else "Client",
                        "Holder ID": sid or "CHECK", "Holder name": holder, "Policy type": code, "Insurer": rec.get("insurer"),
                        "Policy number": rec.get("policy_number"), "Sum insured / limit": rec.get("limit_amount"),
                        "Period start": parse_date(rec.get("period_start")), "Expiry date": parse_date(rec.get("expiry_date")),
                        "Certificate on file": "Y", "Evidence file": rec.get("source_file"),
                        "Principal / interested party noted": rec.get("interested_parties"),
                        "Verification": "Unverified", "Notes": flags or None})
        else:
            skipped.append(rec.get("source_file"))
    if creds:
        append_rows(wb["Credentials"], creds)
    if ins:
        append_rows(wb["Insurances"], ins)
    wb.save(reg_path)
    return {"credentials": len(creds), "insurances": len(ins), "skipped": len(skipped),
            "unmatched_people": sum(c["Person ID"] == "UNMATCHED" for c in creds)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", choices=["sheet", "extraction"])
    ap.add_argument("--client-dir", type=Path, required=True)
    ap.add_argument("--file", type=Path, required=True)
    a = ap.parse_args(argv)
    fn = import_sheet if a.source == "sheet" else import_extraction
    print(fn(a.client_dir, a.file))


if __name__ == "__main__":
    main()
