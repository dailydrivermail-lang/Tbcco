"""Build the Excel templates and the data-model doc from engine/schema.py.

    python -m engine.build_templates

Writes:
  templates/Client_Register_TEMPLATE.xlsx   one per client, copied by new_client.py
  templates/Master_Client_List.xlsx         ops workbook: clients, time log, audit log
  intake/People_and_Licences_Intake.xlsx    client-facing bulk intake sheet
  rules/Rules_Library_REVIEW.xlsx           Ivana's review copy of rules_library.csv
  docs/02-data-model.md                     generated field reference
"""
from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from engine import schema

ROOT = Path(__file__).resolve().parent.parent
NAVY = "1F3A5F"
HEADER_FILL = PatternFill("solid", fgColor=NAVY)
HEADER_FONT = Font(bold=True, color="FFFFFF")
REQ_FILL = PatternFill("solid", fgColor="C0504D")  # required columns get a red header
FORMULA_FILL = PatternFill("solid", fgColor="EEF2F7")
WRAP = Alignment(wrap_text=True, vertical="top")

STATUS_COLOURS = {
    "EXPIRED": "F4B6B6",
    "DUE 7": "F8CBAD",
    "DUE 30": "FFE699",
    "DUE 60": "FFF2CC",
    "CURRENT": "C6EFCE",
    "MISSING DATE": "D9D2E9",
}
DATE_FMT = "dd/mm/yyyy"
DATETIME_FMT = "dd/mm/yyyy hh:mm"

PREFILL_ROWS = {"Credentials": 600, "People": 200, "Insurances": 300}
DEFAULT_PREFILL = 200


def _header(ws, columns, row=1):
    for i, col in enumerate(columns, start=1):
        c = ws.cell(row=row, column=i, value=col["name"])
        c.font = HEADER_FONT
        c.fill = REQ_FILL if col.get("req") else HEADER_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
        if col.get("desc"):
            c.comment = Comment(col["desc"], "TBCCO")
        ws.column_dimensions[get_column_letter(i)].width = col.get("width", max(12, min(len(col["name"]) + 2, 22)))
    ws.row_dimensions[row].height = 32
    ws.freeze_panes = ws.cell(row=row + 1, column=3 if len(columns) > 3 else 1)
    ws.auto_filter.ref = f"A{row}:{get_column_letter(len(columns))}{row}"


def _wrap_formula(formula: str, r: int) -> str:
    inner = formula.format(r=r).lstrip("=")
    return f'=IF($A{r}="","",{inner})'


def _add_lookups(wb):
    ws = wb.create_sheet("Lookups")
    ranges = {}
    col = 1
    for name, values in schema.LOOKUPS.items():
        ws.cell(row=1, column=col, value=name).font = Font(bold=True)
        for i, v in enumerate(values, start=2):
            ws.cell(row=i, column=col, value=v)
        L = get_column_letter(col)
        ranges[name] = f"Lookups!${L}$2:${L}${len(values) + 1}"
        ws.column_dimensions[L].width = max(14, max(len(str(v)) for v in values) + 2)
        col += 1
    # Credential and insurance reference tables
    col += 1
    ws.cell(row=1, column=col, value="Credential code").font = Font(bold=True)
    ws.cell(row=1, column=col + 1, value="Credential name").font = Font(bold=True)
    ws.cell(row=1, column=col + 2, value="Issuer").font = Font(bold=True)
    ws.cell(row=1, column=col + 3, value="Typical validity (yrs)").font = Font(bold=True)
    for i, row in enumerate(schema.CREDENTIAL_TYPES, start=2):
        for j, v in enumerate(row):
            ws.cell(row=i, column=col + j, value=v)
    for j, w in enumerate([20, 60, 40, 12]):
        ws.column_dimensions[get_column_letter(col + j)].width = w
    col += 5
    ws.cell(row=1, column=col, value="Insurance code").font = Font(bold=True)
    ws.cell(row=1, column=col + 1, value="Insurance name").font = Font(bold=True)
    for i, row in enumerate(schema.INSURANCE_TYPES, start=2):
        ws.cell(row=i, column=col, value=row[0])
        ws.cell(row=i, column=col + 1, value=row[1])
    ws.column_dimensions[get_column_letter(col)].width = 18
    ws.column_dimensions[get_column_letter(col + 1)].width = 50
    ws.sheet_state = "visible"
    return ranges


def _status_formatting(ws, col_letter, last_row):
    rng = f"{col_letter}2:{col_letter}{last_row}"
    for text, colour in STATUS_COLOURS.items():
        ws.conditional_formatting.add(
            rng,
            FormulaRule(formula=[f'{col_letter}2="{text}"'], fill=PatternFill("solid", fgColor=colour)),
        )


def build_register(path: Path):
    wb = Workbook()
    readme = wb.active
    readme.title = "README"
    lines = [
        ("Client compliance register", True),
        ("One workbook per client. Tabs: Business, People, Subcontractors, Credentials, Insurances, Jobs, Chemicals, Incidents, Plant, Documents.", False),
        ("Red headers are required at intake. Grey-blue columns are formulas: don't type in them.", False),
        ("Status buckets: EXPIRED, DUE 7, DUE 30, DUE 60, CURRENT, NO EXPIRY, MISSING DATE. Days are counted from today.", False),
        ("Credential type and Policy type codes must come from the dropdowns. They link to the rules library.", False),
        ("Nothing here goes to the client until a human has reviewed it. Draft alerts are written to the client's _outbox folder by the expiry engine.", False),
        ("Generated by engine/build_templates.py. To change a field, edit engine/schema.py and rebuild; don't edit the template by hand.", False),
    ]
    for i, (text, bold) in enumerate(lines, start=1):
        c = readme.cell(row=i, column=1, value=text)
        c.font = Font(bold=bold, size=14 if bold else 11)
    readme.column_dimensions["A"].width = 130

    sheets = {}
    for reg in schema.REGISTERS:
        ws = wb.create_sheet(reg["sheet"])
        sheets[reg["sheet"]] = ws
    ranges = _add_lookups(wb)

    for reg in schema.REGISTERS:
        ws = sheets[reg["sheet"]]
        cols = reg["columns"]
        _header(ws, cols)
        n = 1 if reg["sheet"] == "Business" else PREFILL_ROWS.get(reg["sheet"], DEFAULT_PREFILL)
        last = n + 1
        for i, col in enumerate(cols, start=1):
            L = get_column_letter(i)
            t = col["type"]
            if t == "list":
                dv = DataValidation(type="list", formula1=f"={ranges[col['list']]}", allow_blank=True)
                dv.error = "Pick a value from the list (see the Lookups tab)."
                dv.showErrorMessage = col["list"] not in ("state",)  # allow free text for 'Other' states
                ws.add_data_validation(dv)
                dv.add(f"{L}2:{L}{last}")
            if t in ("date", "datetime"):
                dv = DataValidation(type="date", operator="greaterThan", formula1="1")
                dv.error = "Enter a date (dd/mm/yyyy)."
                ws.add_data_validation(dv)
                dv.add(f"{L}2:{L}{last}")
                for r in range(2, last + 1):
                    ws.cell(row=r, column=i).number_format = DATETIME_FMT if t == "datetime" else DATE_FMT
            if t == "money":
                for r in range(2, last + 1):
                    ws.cell(row=r, column=i).number_format = '"$"#,##0'
            if t == "formula":
                for r in range(2, last + 1):
                    c = ws.cell(row=r, column=i, value=_wrap_formula(col["formula"], r))
                    c.fill = FORMULA_FILL
                    if col["name"] in ("Next due", "Next review", "SDS review due"):
                        c.number_format = DATE_FMT
            if col["name"] == "Status" and t == "formula":
                _status_formatting(ws, L, last)
    wb.save(path)


def build_master(path: Path):
    wb = Workbook()
    first = True
    for sheet, headers in schema.MASTER_SHEETS.items():
        ws = wb.active if first else wb.create_sheet(sheet)
        ws.title = sheet
        first = False
        _header(ws, [{"name": h} for h in headers])
        for i, h in enumerate(headers, start=1):
            if h in ("Date", "Start date", "Last engine run", "Timestamp", "Reviewed at", "Sent at"):
                for r in range(2, 2001):
                    ws.cell(row=r, column=i).number_format = DATE_FMT if h in ("Date", "Start date") else DATETIME_FMT
    lk = wb.create_sheet("Lists")
    for i, a in enumerate(schema.TIME_ACTIVITIES, start=2):
        lk.cell(row=i, column=1, value=a)
    lk.cell(row=1, column=1, value="Activities").font = Font(bold=True)
    tl = wb["Time Log"]
    dv = DataValidation(type="list", formula1=f"=Lists!$A$2:$A${len(schema.TIME_ACTIVITIES) + 1}")
    tl.add_data_validation(dv)
    dv.add("D2:D5000")
    # Minutes this month per client (column R of Clients)
    cl = wb["Clients"]
    mcol = schema.MASTER_SHEETS["Clients"].index("Human minutes (month to date)") + 1
    for r in range(2, 202):
        cl.cell(row=r, column=mcol, value=(
            f'=IF($A{r}="","",SUMIFS(\'Time Log\'!$E:$E,\'Time Log\'!$B:$B,$A{r},'
            f'\'Time Log\'!$A:$A,">="&DATE(YEAR(TODAY()),MONTH(TODAY()),1)))'))
        cl.cell(row=r, column=mcol).fill = FORMULA_FILL
    rag = schema.MASTER_SHEETS["Clients"].index("RAG (latest)") + 1
    L = get_column_letter(rag)
    for text, colour in (("RED", "F4B6B6"), ("AMBER", "FFE699"), ("GREEN", "C6EFCE")):
        cl.conditional_formatting.add(f"{L}2:{L}201", FormulaRule(formula=[f'{L}2="{text}"'], fill=PatternFill("solid", fgColor=colour)))
    wb.save(path)


INTAKE_PEOPLE = [
    ("Full name", 24, "As it appears on their licence."),
    ("Employee / apprentice / subcontractor", 20, "Employee, Apprentice, Subcontractor (individual), Subcontractor worker, or Labour hire."),
    ("Subcontractor business name", 22, "Only if they are a subbie or work for one."),
    ("Role(s)", 24, "e.g. Licensed plumber; Gasfitter; Apprentice; Labourer; Supervisor."),
    ("Works in (ACT / NSW / both)", 12, ""),
    ("Mobile", 14, "For expiry reminders by SMS."),
    ("Email", 24, ""),
    ("Designated first aider? (Y/N)", 12, ""),
    ("Plumbing licence no.", 16, ""), ("Plumbing licence state", 10, ""), ("Plumbing licence class", 18, ""), ("Plumbing licence expiry", 12, ""),
    ("Drainer licence no.", 16, ""), ("Drainer licence state", 10, ""), ("Drainer licence expiry", 12, ""),
    ("Gasfitter licence no.", 16, ""), ("Gasfitter licence state", 10, ""), ("Gasfitter class (general/advanced/LPG)", 16, ""), ("Gasfitter licence expiry", 12, ""),
    ("White Card no.", 16, "General construction induction card."), ("White Card state", 10, ""),
    ("Asbestos awareness (11084NAT) date", 14, "Mandatory for ACT construction workers."),
    ("Silica (10830NAT) date", 14, "Mandatory for many ACT construction workers."),
    ("First aid (HLTAID011) expiry", 12, ""), ("CPR (HLTAID009) expiry", 12, ""),
    ("High risk work licence no.", 16, "Forklift, EWP 11m+, scaffolding, dogging..."), ("HRWL classes", 12, "e.g. LF, WP, SB"), ("HRWL expiry", 12, ""),
    ("ARCtick licence no.", 14, "Only if they handle refrigerant."), ("ARCtick expiry", 12, ""),
    ("Other tickets (name, number, expiry)", 30, "Confined space, working at heights, restricted electrical, etc."),
    ("Copies uploaded? (Y/N)", 10, "Upload photos/scans to the upload link we sent you."),
]
INTAKE_SUBBIES = [
    ("Business name", 24, ""), ("ABN", 14, ""), ("Trade", 16, ""), ("Contact name", 18, ""),
    ("Contact email", 24, ""), ("Contact mobile", 14, ""),
    ("Public liability insurer", 18, ""), ("PL policy no.", 14, ""), ("PL limit ($)", 12, ""), ("PL expiry", 12, ""),
    ("Workers' comp insurer", 18, ""), ("WC policy no.", 14, ""), ("WC expiry", 12, ""),
    ("NSW subcontractor statement held? (Y/N)", 14, "NSW only (s 175B Workers Compensation Act 1987)."),
    ("Certificates uploaded? (Y/N)", 10, ""),
]
INTAKE_CHEMS = [("Product name", 26, ""), ("Manufacturer", 18, ""), ("Used for", 22, ""), ("Where stored", 18, ""), ("SDS uploaded? (Y/N)", 10, "")]
INTAKE_PLANT = [("Item", 26, "e.g. Jetter, excavator, pipe threader, core drill, gas detector."), ("Make / model", 18, ""), ("Serial / rego", 14, ""),
                ("Last service / test-and-tag date", 14, ""), ("Records uploaded? (Y/N)", 10, "")]


def build_intake(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Start here"
    text = [
        ("Compliance onboarding: people, licences and insurances", True),
        ("Thanks for joining. Fill in one row per person on the People tab, and one row per subcontractor business on the Subcontractors tab.", False),
        ("Don't worry about gaps. Leave a cell blank if you don't know, and we'll chase it. Scans or photos of licences and certificates are better than typing.", False),
        ("Upload copies to the secure upload link in our welcome email. Name files with the person's name if you can (e.g. 'John Smith - gas licence.jpg').", False),
        ("Dates: dd/mm/yyyy.", False),
        ("We keep this information in Australian-hosted Microsoft 365 storage, and use it only to deliver your compliance service.", False),
    ]
    for i, (t, b) in enumerate(text, start=1):
        c = ws.cell(row=i, column=1, value=t)
        c.font = Font(bold=b, size=14 if b else 11)
    ws.column_dimensions["A"].width = 140
    for name, cols in (("People", INTAKE_PEOPLE), ("Subcontractors", INTAKE_SUBBIES), ("Chemicals", INTAKE_CHEMS), ("Plant", INTAKE_PLANT)):
        s = wb.create_sheet(name)
        _header(s, [{"name": n, "width": w, "desc": d} for n, w, d in cols])
        s.freeze_panes = "B2"
        for i, (n, _, _) in enumerate(cols, start=1):
            if any(k in n.lower() for k in ("expiry", "date")):
                for r in range(2, 201):
                    s.cell(row=r, column=i).number_format = DATE_FMT
    wb.save(path)


def build_rules_review(csv_path: Path, out: Path):
    rows = list(csv.DictReader(open(csv_path, newline="", encoding="utf-8")))
    wb = Workbook()
    ws = wb.active
    ws.title = "Rules"
    cols = list(rows[0].keys())
    widths = {"requirement": 60, "condition": 36, "source_instrument": 40, "source_provision": 32, "source_url": 40,
              "notes": 44, "ivana_notes": 40, "evidence_description": 36, "trigger_roles": 26, "confidence": 22}
    _header(ws, [{"name": c, "width": widths.get(c, 14)} for c in cols])
    for r, row in enumerate(rows, start=2):
        for i, c in enumerate(cols, start=1):
            cell = ws.cell(row=r, column=i, value=row[c])
            cell.alignment = WRAP
    conf_col = get_column_letter(cols.index("confidence") + 1)
    for prefix, colour in (("A", "C6EFCE"), ("B", "FFF2CC"), ("C", "F4B6B6")):
        ws.conditional_formatting.add(f"{conf_col}2:{conf_col}{len(rows) + 1}",
                                      FormulaRule(formula=[f'LEFT({conf_col}2,1)="{prefix}"'], fill=PatternFill("solid", fgColor=colour)))
    st = get_column_letter(cols.index("ivana_status") + 1)
    dv = DataValidation(type="list", formula1='"Not reviewed,Verified,Verified with changes,Rejected,Needs research"')
    ws.add_data_validation(dv)
    dv.add(f"{st}2:{st}{len(rows) + 1}")
    k = wb.create_sheet("Key")
    for i, t in enumerate([
        "Confidence A: checked against an official regulator or legislation page while building v1.",
        "Confidence B: well-established requirement; section number and current wording still to be confirmed.",
        "Confidence C: uncertain. Do not rely on it in client output until Ivana has researched it.",
        "Every rule stays 'Not reviewed' until Ivana changes ivana_status. The engine labels gaps from unreviewed rules as 'pending legal review'.",
        "Edit rules/rules_library.csv (the source of truth), then run: python -m engine.build_templates",
    ], start=1):
        k.cell(row=i, column=1, value=t)
    k.column_dimensions["A"].width = 130
    wb.save(out)


def build_data_model_doc(out: Path):
    lines = [
        "# Data model (generated)",
        "",
        "Generated from `engine/schema.py` by `python -m engine.build_templates`. Do not edit by hand.",
        "",
        "Each client has one register workbook (`00_Register/<ClientID>_Register.xlsx`) with the sheets below.",
        "**Req** = must be captured at intake. Formula columns are computed in Excel; the engine recomputes them in Python.",
        "",
    ]
    for reg in schema.REGISTERS:
        lines += [f"## {reg['sheet']}", "", reg["purpose"], "", "| Field | Type | Req | Notes |", "|---|---|---|---|"]
        for c in reg["columns"]:
            t = c["type"] + (f" ({c['list']})" if c.get("list") else "")
            lines.append(f"| {c['name']} | {t} | {'Y' if c.get('req') else ''} | {c.get('desc', '').replace('|', '/')} |")
        lines.append("")
    lines += ["## Credential type codes", "", "| Code | Name | Issuer | Typical validity (yrs) |", "|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in schema.CREDENTIAL_TYPES]
    lines += ["", "## Insurance / evidence codes", "", "| Code | Name |", "|---|---|"]
    lines += [f"| {a} | {b} |" for a, b in schema.INSURANCE_TYPES]
    lines += ["", "## Master client list (ops workbook)", ""]
    for s, h in schema.MASTER_SHEETS.items():
        lines.append(f"- **{s}**: " + ", ".join(h))
    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")


def main():
    (ROOT / "templates").mkdir(exist_ok=True)
    build_register(ROOT / "templates" / "Client_Register_TEMPLATE.xlsx")
    build_master(ROOT / "templates" / "Master_Client_List.xlsx")
    build_intake(ROOT / "intake" / "People_and_Licences_Intake.xlsx")
    build_rules_review(ROOT / "rules" / "rules_library.csv", ROOT / "rules" / "Rules_Library_REVIEW.xlsx")
    build_data_model_doc(ROOT / "docs" / "02-data-model.md")
    print("Templates and docs rebuilt.")


if __name__ == "__main__":
    main()
