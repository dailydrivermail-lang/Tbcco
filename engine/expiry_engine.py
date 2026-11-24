"""Expiry and gap engine (Phase 1).

For each client register it:
  1. buckets every dated item (credentials, insurances, plant tests, document reviews)
     into EXPIRED / DUE 7 / DUE 30 / DUE 60 / CURRENT / NO EXPIRY / MISSING DATE
  2. checks people, subcontractors and the business against the rules library
     for missing credentials or insurances
  3. drafts alerts only when an item moves into a more urgent stage (expired items
     are re-chased weekly), so clients and workers aren't spammed
  4. writes everything to <client>/_outbox/<date>/ for HUMAN REVIEW. Nothing is sent.
  5. appends to the audit log and refreshes the master client list, if one is given

Usage:
  python -m engine.expiry_engine --client-dir PATH [--master PATH] [--today YYYY-MM-DD]
  python -m engine.expiry_engine --clients-root PATH [--master PATH]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from engine import schema
from engine.register_io import add_months, load_rules, parse_date, read_sheet

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "rules" / "rules_library.csv"

STAGES = ["CURRENT", "DUE 60", "DUE 30", "DUE 7", "EXPIRED"]  # ascending urgency
RECHASE_EXPIRED_DAYS = 7
SENDER = "compliance@yourfirm.com.au"  # set to the shared mailbox address
CRED_NAMES = {c[0]: c[1] for c in schema.CREDENTIAL_TYPES}
INS_NAMES = {c[0]: c[1] for c in schema.INSURANCE_TYPES}
SITE_ROLES_NONE = {"Office (non-site)"}


def bucket(expiry: dt.date | None, today: dt.date, no_expiry: bool = False) -> tuple[str, int | None]:
    if no_expiry:
        return "NO EXPIRY", None
    if expiry is None:
        return "MISSING DATE", None
    d = (expiry - today).days
    if d < 0:
        return "EXPIRED", d
    if d <= 7:
        return "DUE 7", d
    if d <= 30:
        return "DUE 30", d
    if d <= 60:
        return "DUE 60", d
    return "CURRENT", d


@dataclass
class Item:
    sheet: str
    item_id: str
    holder_id: str
    holder_name: str
    kind: str          # credential/insurance code or description
    label: str         # human readable
    number: str
    expiry: dt.date | None
    status: str
    days: int | None
    person: dict | None = None
    alert: bool = False
    alert_reason: str = ""

    @property
    def key(self) -> str:
        return f"{self.sheet}:{self.item_id}:{self.expiry or ''}"


@dataclass
class Gap:
    level: str          # Person / Subcontractor / Business
    holder_id: str
    holder_name: str
    rule_id: str
    requirement: str
    evidence: str
    obligation: str
    confidence: str
    ivana_status: str


@dataclass
class ClientResult:
    client_id: str
    name: str
    items: list[Item] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    confirm: list[dict] = field(default_factory=list)
    rag: str = "GREEN"
    drafts: list[Path] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rules evaluation
# ---------------------------------------------------------------------------

def _states(v) -> set[str]:
    s = str(v or "").replace(",", ";").replace("/", ";")
    return {x.strip().upper() for x in s.split(";") if x.strip()}


def _roles(v) -> set[str]:
    return {x.strip().lower() for x in str(v or "").replace(",", ";").split(";") if x.strip()}


def _rule_applies_juris(rule, states: set[str]) -> bool:
    return rule["jurisdiction"] == "ALL" or rule["jurisdiction"] in states


def eval_condition(cond: str, person: dict | None = None, business: dict | None = None) -> bool | None:
    """True/False for machine-checkable conditions, None if a human must confirm."""
    cond = (cond or "").strip()
    if not cond:
        return True
    if cond.startswith("flag:") and person is not None:
        f, _, val = cond[5:].partition("=")
        return str(person.get(f.strip(), "") or "").strip().upper() == val.strip().upper()
    if cond.startswith("biz:") and business is not None:
        expr = cond[4:]
        for op in (">=", ">", "="):
            if op in expr:
                f, _, val = expr.partition(op)
                try:
                    a, b = float(business.get(f.strip()) or 0), float(val)
                except ValueError:
                    return None
                return a >= b if op == ">=" else a > b if op == ">" else a == b
    return None


def check_gaps(rules, business, people, subbies, creds, insurances, client_id) -> tuple[list[Gap], list[dict]]:
    gaps: list[Gap] = []
    confirm: dict[str, dict] = {}
    biz_states = _states(business.get("States operated"))

    held_creds: dict[str, set[str]] = {}
    for c in creds:
        held_creds.setdefault(str(c.get("Person ID")), set()).add(str(c.get("Credential type")))
    held_ins: dict[str, set[str]] = {}
    for i in insurances:
        held_ins.setdefault(str(i.get("Holder ID")), set()).add(str(i.get("Policy type")))

    def g(level, hid, hname, rule):
        gaps.append(Gap(level, hid, hname, rule["rule_id"], rule["requirement"], rule["evidence_code"],
                        rule["obligation_type"], rule["confidence"], rule["ivana_status"]))

    def note_confirm(rule):
        confirm.setdefault(rule["rule_id"], {"rule_id": rule["rule_id"], "condition": rule["condition"],
                                             "requirement": rule["requirement"], "confidence": rule["confidence"]})

    for rule in rules:
        codes = [c for c in rule["evidence_code"].split("|") if c and not c.startswith("DOC:")]
        level = rule["applies_to"]
        if level == "Person":
            roles = _roles(rule["trigger_roles"])
            for p in people:
                if str(p.get("Active", "Y")).upper() == "N":
                    continue
                p_roles = _roles(p.get("Roles"))
                p_states = _states(p.get("States worked")) or biz_states
                if not (roles & p_roles) or not _rule_applies_juris(rule, p_states):
                    continue
                ok = eval_condition(rule["condition"], person=p)
                if ok is None:
                    note_confirm(rule)
                    continue
                if not ok or not codes:
                    continue
                if not (set(codes) & held_creds.get(str(p.get("Person ID")), set())):
                    g("Person", p.get("Person ID"), p.get("Full name"), rule)
        elif level == "Subcontractor":
            for s in subbies:
                if str(s.get("Active", "Y")).upper() == "N":
                    continue
                s_states = _states(s.get("States worked")) or biz_states
                if not _rule_applies_juris(rule, s_states):
                    continue
                ok = eval_condition(rule["condition"])
                if ok is None:
                    note_confirm(rule)
                    continue
                if codes and not (set(codes) & held_ins.get(str(s.get("Subcontractor ID")), set())):
                    g("Subcontractor", s.get("Subcontractor ID"), s.get("Business name"), rule)
        elif level == "Business":
            if not _rule_applies_juris(rule, biz_states):
                continue
            ok = eval_condition(rule["condition"], business=business)
            if ok is None:
                note_confirm(rule)
                continue
            ins_codes = [c for c in codes if c in INS_NAMES]
            if ok and ins_codes and not (set(ins_codes) & held_ins.get(client_id, set())):
                g("Business", client_id, business.get("Legal name"), rule)
    return gaps, list(confirm.values())


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

def collect_items(today, people, creds, insurances, plant, documents, subbies, business) -> list[Item]:
    pmap = {str(p.get("Person ID")): p for p in people}
    smap = {str(s.get("Subcontractor ID")): s.get("Business name") for s in subbies}
    items: list[Item] = []
    for c in creds:
        person = pmap.get(str(c.get("Person ID")))
        if person and str(person.get("Active", "Y")).upper() == "N":
            continue
        no_exp = str(c.get("No expiry") or "").upper() == "Y"
        exp = parse_date(c.get("Expiry date"))
        st, d = bucket(exp, today, no_exp)
        code = str(c.get("Credential type") or "")
        items.append(Item("Credentials", str(c.get("Credential ID")), str(c.get("Person ID")),
                          (person or {}).get("Full name", "?"), code, CRED_NAMES.get(code, code),
                          str(c.get("Licence / card number") or ""), exp, st, d, person))
    for i in insurances:
        exp = parse_date(i.get("Expiry date"))
        st, d = bucket(exp, today)
        code = str(i.get("Policy type") or "")
        hid = str(i.get("Holder ID"))
        name = i.get("Holder name") or smap.get(hid) or business.get("Legal name")
        items.append(Item("Insurances", str(i.get("Insurance ID")), hid, name, code, INS_NAMES.get(code, code),
                          str(i.get("Policy number") or ""), exp, st, d))
    for p in plant:
        last, interval = parse_date(p.get("Last inspection / test")), p.get("Interval (months)")
        due = add_months(last, int(interval)) if last and interval else None
        st, d = bucket(due, today)
        items.append(Item("Plant", str(p.get("Plant ID")), "", "", "PLANT", f"Inspection / test: {p.get('Description')}",
                          str(p.get("Serial / rego") or ""), due, st, d))
    for doc in documents:
        appr, interval = parse_date(doc.get("Approved date")), doc.get("Review interval (months)")
        due = add_months(appr, int(interval)) if appr and interval else None
        st, d = bucket(due, today)
        items.append(Item("Documents", str(doc.get("Document ID")), "", "", "DOC", f"Review due: {doc.get('Title')}",
                          str(doc.get("Version") or ""), due, st, d))
    return items


# ---------------------------------------------------------------------------
# Alert state (prevents repeat alerts)
# ---------------------------------------------------------------------------

def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["key"]: r for r in csv.DictReader(f)}


def save_state(path: Path, state: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["key", "stage", "last_drafted"])
        w.writeheader()
        for r in state.values():
            w.writerow(r)


def decide_alerts(items: list[Item], state: dict, today: dt.date):
    for it in items:
        if it.status not in STAGES or it.status == "CURRENT":
            continue
        prev = state.get(it.key)
        prev_stage = prev["stage"] if prev else "CURRENT"
        last = parse_date(prev["last_drafted"]) if prev else None
        if STAGES.index(it.status) > STAGES.index(prev_stage):
            it.alert, it.alert_reason = True, f"moved to {it.status}"
        elif it.status == "EXPIRED" and (last is None or (today - last).days >= RECHASE_EXPIRED_DAYS):
            it.alert, it.alert_reason = True, "still expired: weekly re-chase"
        if it.alert:
            state[it.key] = {"key": it.key, "stage": it.status, "last_drafted": today.isoformat()}


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------

def short_label(code: str) -> str:
    name = CRED_NAMES.get(code) or INS_NAMES.get(code) or code
    if code == "WHITE_CARD":
        return "White Card"
    return name.split(" (")[0].split(" - ")[0].replace("Provide ", "") if code in CRED_NAMES else name


def _fmt(d):
    return d.strftime("%d/%m/%Y") if d else "no date on file"


def _when(it: Item) -> str:
    if it.status == "EXPIRED":
        return f"EXPIRED {abs(it.days)} days ago ({_fmt(it.expiry)})"
    return f"expires in {it.days} days ({_fmt(it.expiry)})"


def _eml(to: str, subject: str, body: str, path: Path):
    m = EmailMessage()
    m["To"] = to or ""
    m["From"] = SENDER
    m["Subject"] = subject
    m["X-Unsent"] = "1"  # Outlook opens .eml files with this header as an editable draft
    m.set_content(body, cte="8bit")
    path.write_bytes(bytes(m))


def write_client_email(res: ClientResult, business: dict, outdir: Path, today: dt.date) -> Path | None:
    exp = [i for i in res.items if i.status == "EXPIRED" and i.sheet in ("Credentials", "Insurances")]
    due = [i for i in res.items if i.status in ("DUE 7", "DUE 30", "DUE 60") and i.sheet in ("Credentials", "Insurances")]
    other = [i for i in res.items if i.sheet in ("Plant", "Documents") and i.status in ("EXPIRED", "DUE 7", "DUE 30")]
    nodate = [i for i in res.items if i.status == "MISSING DATE" and i.sheet in ("Credentials", "Insurances")]
    if not (exp or due or res.gaps or other or nodate):
        return None
    first = (business.get("Primary contact") or "there").split(" ")[0]
    L = [f"Hi {first},", "", f"Here's your compliance update for {business.get('Trading name') or business.get('Legal name')} as at {_fmt(today)}.", ""]
    if exp:
        L += ["EXPIRED: action now", "These have lapsed. Workers shouldn't do work that needs a lapsed licence or ticket until it's renewed. Please send us the renewed copy."]
        L += [f"  - {i.holder_name}: {i.label} ({i.number}), {_when(i)}" for i in sorted(exp, key=lambda x: x.days)]
        L.append("")
    if due:
        L += ["COMING UP"]
        L += [f"  - {i.holder_name}: {i.label} ({i.number}), {_when(i)}" for i in sorted(due, key=lambda x: x.days)]
        L.append("")
    if res.gaps:
        L += ["WE DON'T HAVE THESE ON FILE", "If these exist, please upload a copy. If they don't apply, reply and tell us, and we'll update the register."]
        seen = set()
        for g in res.gaps:
            if (g.holder_id, g.evidence) in seen:
                continue
            seen.add((g.holder_id, g.evidence))
            ev = " or ".join(short_label(c) for c in g.evidence.split("|"))
            L.append(f"  - {g.holder_name}: {ev}")
        L.append("")
    if nodate:
        L += ["WE NEED AN EXPIRY DATE FOR"]
        L += [f"  - {i.holder_name}: {i.label} ({i.number})" for i in nodate]
        L.append("")
    if other:
        L += ["EQUIPMENT AND DOCUMENTS"]
        L += [f"  - {i.label}, {_when(i)}" for i in other]
        L.append("")
    L += ["Upload copies to your secure upload link, or reply to this email with photos attached.", "",
          "Kind regards,", "[Reviewer name]", "",
          "This summary is prepared from the records you have given us. It is a compliance administration service, not legal advice."]
    path = outdir / f"{res.client_id}_client_summary_{today.isoformat()}.eml"
    _eml(business.get("Primary contact email", ""), f"[DRAFT - REVIEW] Compliance update: {len(exp)} expired, {len(due)} coming up", "\n".join(L), path)
    return path


def write_worker_drafts(res: ClientResult, business: dict, outdir: Path, today: dt.date) -> list[Path]:
    paths: list[Path] = []
    sms_rows = []
    by_person: dict[str, list[Item]] = {}
    for it in res.items:
        if it.alert and it.sheet == "Credentials" and it.person:
            by_person.setdefault(it.holder_id, []).append(it)
    biz = business.get("Trading name") or business.get("Legal name")
    for pid, its in by_person.items():
        p = its[0].person
        channel = str(p.get("Alert channel") or "Client only")
        first = str(p.get("Full name", "")).split(" ")[0]
        if channel in ("Email", "Email+SMS") and p.get("Email"):
            body = [f"Hi {first},", "", f"We look after compliance records for {biz}. According to our records:", ""]
            body += [f"  - {i.label} ({i.number}), {_when(i)}" for i in its]
            body += ["", "Please renew if needed, then send a photo of the new card or certificate by replying to this email.", "",
                     "Thanks,", "[Reviewer name]", f"on behalf of {biz}"]
            path = outdir / f"{res.client_id}_worker_{pid}_{today.isoformat()}.eml"
            worst = max(its, key=lambda i: STAGES.index(i.status))
            _eml(p.get("Email"), f"[DRAFT - REVIEW] {worst.label}: {'expired' if worst.status == 'EXPIRED' else 'renewal due'}",
                 "\n".join(body), path)
            paths.append(path)
        if channel in ("SMS", "Email+SMS") and p.get("Mobile"):
            worst = max(its, key=lambda i: STAGES.index(i.status))
            more = f" (+{len(its) - 1} more)" if len(its) > 1 else ""
            verb = "EXPIRED" if worst.status == "EXPIRED" else f"expires {_fmt(worst.expiry)}"
            msg = f"{biz}: your {short_label(worst.kind)} {verb}{more}. Pls renew & reply with a photo of the new card. Thanks"
            sms_rows.append({"Person ID": pid, "Name": p.get("Full name"), "Mobile": p.get("Mobile"), "Message": msg,
                             "Chars": len(msg), "Approved (Y/N)": ""})
    if sms_rows:
        path = outdir / f"{res.client_id}_sms_drafts_{today.isoformat()}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(sms_rows[0].keys()))
            w.writeheader()
            w.writerows(sms_rows)
        paths.append(path)
    return paths


def write_review_report(res: ClientResult, outdir: Path, today: dt.date) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Items"
    hdr = ["Status", "Days", "New alert", "Reason", "Register", "Item ID", "Holder", "Item", "Number", "Expiry"]
    ws.append(hdr)
    fills = {"EXPIRED": "F4B6B6", "DUE 7": "F8CBAD", "DUE 30": "FFE699", "DUE 60": "FFF2CC", "MISSING DATE": "D9D2E9"}
    order = {s: i for i, s in enumerate(["EXPIRED", "DUE 7", "DUE 30", "DUE 60", "MISSING DATE", "CURRENT", "NO EXPIRY"])}
    for it in sorted(res.items, key=lambda x: (order.get(x.status, 9), x.days if x.days is not None else 0)):
        ws.append([it.status, it.days, "Y" if it.alert else "", it.alert_reason, it.sheet, it.item_id, it.holder_name,
                   it.label, it.number, it.expiry])
        if it.status in fills:
            ws.cell(row=ws.max_row, column=1).fill = PatternFill("solid", fgColor=fills[it.status])
        ws.cell(row=ws.max_row, column=10).number_format = "dd/mm/yyyy"
    g = wb.create_sheet("Missing (rules)")
    g.append(["Level", "Holder ID", "Holder", "Rule", "Requirement", "Evidence code", "Obligation", "Confidence", "Legal review"])
    for x in res.gaps:
        g.append([x.level, x.holder_id, x.holder_name, x.rule_id, x.requirement, x.evidence, x.obligation, x.confidence,
                  "Verified" if x.ivana_status.startswith("Verified") else "PENDING LEGAL REVIEW"])
    c = wb.create_sheet("Confirm with client")
    c.append(["Rule", "Applies if...", "Requirement", "Confidence"])
    for x in res.confirm:
        c.append([x["rule_id"], x["condition"], x["requirement"], x["confidence"]])
    for s in wb.worksheets:
        for cell in s[1]:
            cell.font = Font(bold=True)
        for col, w in zip("ABCDEFGHIJ", (14, 8, 10, 26, 12, 10, 24, 50, 18, 12)):
            s.column_dimensions[col].width = w
    path = outdir / f"{res.client_id}_REVIEW_{today.isoformat()}.xlsx"
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# Master workbook
# ---------------------------------------------------------------------------

def rag_for(res: ClientResult) -> str:
    cr = [i for i in res.items if i.sheet in ("Credentials", "Insurances")]
    if any(i.status == "EXPIRED" for i in cr) or any(g.obligation == "Statutory" for g in res.gaps):
        return "RED"
    if any(i.status in ("DUE 7", "DUE 30", "MISSING DATE") for i in cr) or res.gaps or \
            any(i.status == "EXPIRED" for i in res.items):
        return "AMBER"
    return "GREEN"


def update_master(master: Path, res: ClientResult, today: dt.date):
    wb = load_workbook(master)
    ws = wb["Clients"]
    hdr = [c.value for c in ws[1]]
    row = None
    for r in range(2, ws.max_row + 1):
        if ws.cell(row=r, column=1).value == res.client_id:
            row = r
            break
    if row is None:
        row = 2
        while ws.cell(row=row, column=1).value not in (None, ""):
            row += 1
        ws.cell(row=row, column=1, value=res.client_id)
        ws.cell(row=row, column=hdr.index("Legal name") + 1, value=res.name)
    cr = [i for i in res.items if i.sheet in ("Credentials", "Insurances")]
    vals = {
        "RAG (latest)": res.rag,
        "Expired items": sum(i.status == "EXPIRED" for i in cr),
        "Due within 30 days": sum(i.status in ("DUE 7", "DUE 30") for i in cr),
        "Missing items": len(res.gaps),
        "Last engine run": dt.datetime.combine(today, dt.datetime.now().time()).replace(microsecond=0),
    }
    for k, v in vals.items():
        ws.cell(row=row, column=hdr.index(k) + 1, value=v)
    al = wb["Audit Log"]
    r = 2
    while al.cell(row=r, column=1).value not in (None, ""):
        r += 1
    now = dt.datetime.now().replace(microsecond=0)
    for p in res.drafts:
        kind = "Review report" if "REVIEW" in p.name else "SMS drafts" if p.suffix == ".csv" else "Alert email draft"
        for c, v in enumerate([now, res.client_id, kind, p.stem, "expiry_engine", str(p),
                               "Internal" if kind == "Review report" else "Draft - awaiting review"], start=1):
            al.cell(row=r, column=c, value=v)
        r += 1
    wb.save(master)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def find_register(client_dir: Path) -> Path:
    regs = sorted((client_dir / "00_Register").glob("*_Register.xlsx"))
    if not regs:
        raise FileNotFoundError(f"No *_Register.xlsx in {client_dir / '00_Register'}")
    return regs[0]


def run_client(client_dir: Path, today: dt.date, rules=None, master: Path | None = None, write=True) -> ClientResult:
    rules = rules if rules is not None else load_rules(RULES_PATH)
    wb = load_workbook(find_register(client_dir))
    bl = read_sheet(wb, "Business")
    business = bl[0] if bl else {}
    people, subbies = read_sheet(wb, "People"), read_sheet(wb, "Subcontractors")
    creds, ins = read_sheet(wb, "Credentials"), read_sheet(wb, "Insurances")
    plant, docs = read_sheet(wb, "Plant"), read_sheet(wb, "Documents")
    cid = str(business.get("Client ID") or client_dir.name.split("_")[0])
    res = ClientResult(cid, business.get("Legal name", ""))
    res.items = collect_items(today, people, creds, ins, plant, docs, subbies, business)
    res.gaps, res.confirm = check_gaps(rules, business, people, subbies, creds, ins, cid)
    res.rag = rag_for(res)
    state_path = client_dir / "_system" / "alert_state.csv"
    state = load_state(state_path)
    decide_alerts(res.items, state, today)
    if write:
        outdir = client_dir / "_outbox" / today.isoformat()
        outdir.mkdir(parents=True, exist_ok=True)
        res.drafts.append(write_review_report(res, outdir, today))
        if any(i.alert for i in res.items) or res.gaps:
            p = write_client_email(res, business, outdir, today)
            if p:
                res.drafts.append(p)
        res.drafts += write_worker_drafts(res, business, outdir, today)
        save_state(state_path, state)
        with open(client_dir / "_system" / "engine_runs.csv", "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([dt.datetime.now().isoformat(timespec="seconds"), today.isoformat(), res.rag,
                                    len(res.items), len(res.gaps), len(res.drafts)])
        if master:
            update_master(master, res, today)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--client-dir", type=Path)
    g.add_argument("--clients-root", type=Path, help="Folder containing one subfolder per client")
    ap.add_argument("--master", type=Path, help="Master_Client_List.xlsx to update")
    ap.add_argument("--today", type=lambda s: dt.date.fromisoformat(s), default=dt.date.today())
    a = ap.parse_args(argv)
    dirs = [a.client_dir] if a.client_dir else sorted(p for p in a.clients_root.iterdir() if (p / "00_Register").is_dir())
    rules = load_rules(RULES_PATH)
    for d in dirs:
        res = run_client(d, a.today, rules, a.master)
        n_alert = sum(i.alert for i in res.items)
        print(f"{res.client_id:6} {res.rag:6} items={len(res.items):3} new_alerts={n_alert:3} "
              f"missing={len(res.gaps):3} drafts={len(res.drafts)} -> {d / '_outbox' / a.today.isoformat()}")


if __name__ == "__main__":
    main()
