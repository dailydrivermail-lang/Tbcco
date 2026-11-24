"""Read and write register workbooks by header name (not column letter)."""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from openpyxl import load_workbook

DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y")


def parse_date(v) -> dt.date | None:
    if v is None or v == "":
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)):  # Excel serial
        return (dt.datetime(1899, 12, 30) + dt.timedelta(days=float(v))).date()
    s = str(v).strip()
    for f in DATE_FORMATS:
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def add_months(d: dt.date, months: int) -> dt.date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    import calendar
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def read_sheet(wb, sheet: str) -> list[dict]:
    """Rows as dicts keyed by header. Skips rows with an empty first column.
    Formula columns come back as formula strings and are ignored by the engine."""
    if sheet not in wb.sheetnames:
        return []
    ws = wb[sheet]
    headers = [c.value for c in ws[1]]
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] in (None, ""):
            continue
        out.append({h: v for h, v in zip(headers, row) if h})
    return out


def load_register(path: Path):
    return load_workbook(path)


def next_empty_row(ws) -> int:
    r = 2
    while ws.cell(row=r, column=1).value not in (None, ""):
        r += 1
    return r


def append_rows(ws, rows: list[dict]):
    """Write dicts into the first empty rows, matching on header names.
    Formula cells are left alone (they're pre-filled in the template)."""
    headers = [c.value for c in ws[1]]
    r = next_empty_row(ws)
    for row in rows:
        for i, h in enumerate(headers, start=1):
            if h in row and row[h] not in (None, ""):
                cell = ws.cell(row=r, column=i)
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    continue
                cell.value = row[h]
        r += 1


def next_id(existing: list[str], prefix: str, width: int = 4) -> str:
    n = 0
    for e in existing:
        if e and str(e).startswith(prefix):
            try:
                n = max(n, int(str(e)[len(prefix):]))
            except ValueError:
                pass
    return f"{prefix}{n + 1:0{width}d}"


def load_rules(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
