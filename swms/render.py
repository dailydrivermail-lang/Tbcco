"""Render a SwmsDoc to PDF (A4 landscape) with reportlab."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from swms.model import HIERARCHY, RISK, SwmsDoc

NAVY = colors.HexColor("#1F3A5F")
LINE = colors.HexColor("#C9D1DC")
SHADE = colors.HexColor("#EEF2F7")
RISK_COL = {"X": colors.HexColor("#C0392B"), "H": colors.HexColor("#E67E22"), "M": colors.HexColor("#F1C40F"), "L": colors.HexColor("#27AE60")}
STATUS_COL = {"OK": "#1d6b38", "NO EXPIRY": "#1d6b38", "MISSING": "#a3221c", "EXPIRED": "#a3221c", "EXPIRES DURING JOB": "#7a5300"}

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=16, textColor=NAVY, spaceAfter=4)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11.5, textColor=NAVY, spaceBefore=8, spaceAfter=4)
P = ParagraphStyle("p", parent=ss["BodyText"], fontSize=8.5, leading=10.5, alignment=TA_LEFT)
PS = ParagraphStyle("ps", parent=P, fontSize=7.5, leading=9.2)
PB = ParagraphStyle("pb", parent=P, fontName="Helvetica-Bold")
PW = ParagraphStyle("pw", parent=P, textColor=colors.white, fontName="Helvetica-Bold")


def e(x) -> str:
    return escape(str(x if x is not None else ""))


def _fmt(v) -> str:
    if isinstance(v, dt.datetime):
        return v.strftime("%d/%m/%Y") if (v.hour, v.minute) == (0, 0) else v.strftime("%d/%m/%Y %H:%M")
    if isinstance(v, dt.date):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, str) and len(v) >= 10 and v[4] == "-" and v[7] == "-":
        try:
            return dt.date.fromisoformat(v[:10]).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return "" if v is None else str(v)


def grid(data, widths, header=True, extra=None):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
    t.setStyle(TableStyle(style + (extra or [])))
    return t


def risk_cell(code: str):
    col = "#1c2430" if code == "M" else "white"
    return Paragraph(f'<font color="{col}"><b>{e(RISK.get(code, code))}</b></font>', P)


def build_story(doc: SwmsDoc) -> list:
    b, j = doc.business, doc.job
    W = landscape(A4)[0] - 24 * mm
    story = [Paragraph("Safe Work Method Statement (SWMS)", H1),
             Paragraph(f"High-risk construction work · {e(doc.template)} · {e(doc.state)}", P), Spacer(1, 6)]

    info = [
        ["PCBU (employer)", f"{b.get('Legal name', '')}  ·  ABN {b.get('ABN', '')}", "SWMS number / version", f"{doc.swms_no} · v{doc.version}"],
        ["Contact", f"{b.get('Primary contact', '')}  {b.get('Primary contact mobile', '')}", "Status", doc.status],
        ["Principal contractor", j.get("Principal / head contractor") or "—", "Prepared", _fmt(doc.prepared_at)],
        ["Site address", j.get("Site address", ""), "Reviewed by / date", f"{doc.reviewed_by or '—'} {_fmt(doc.issued_at) if doc.issued_at else ''}"],
        ["Job / client ref", f"{j.get('Job ID', '')} {('/ ' + str(j.get('Client job ref'))) if j.get('Client job ref') else ''}", "Start / end",
         f"{_fmt(j.get('Start date'))} – {_fmt(j.get('End date')) or 'TBC'}"],
        ["Scope of work", j.get("Scope of work", ""), "Plant and equipment", doc.plant or "—"],
    ]
    rows = [[Paragraph(f"<b>{e(a)}</b>", PS), Paragraph(e(bv), P), Paragraph(f"<b>{e(c)}</b>", PS), Paragraph(e(dv), P)] for a, bv, c, dv in info]
    story.append(grid(rows, [34 * mm, W / 2 - 34 * mm, 36 * mm, W / 2 - 36 * mm], header=False,
                      extra=[("BACKGROUND", (0, 0), (0, -1), SHADE), ("BACKGROUND", (2, 0), (2, -1), SHADE)]))

    story.append(Paragraph("1. High-risk construction work covered by this SWMS (WHS Regulation r 291)", H2))
    half = (len(doc.hrcw) + 1) // 2
    cells = []
    for i in range(half):
        row = []
        for c in (doc.hrcw[i], doc.hrcw[i + half] if i + half < len(doc.hrcw) else None):
            if c:
                mark = "<b>[X]</b>" if c[1] else "[&nbsp;&nbsp;]"
                row.append(Paragraph(f"{mark} {e(c[0])}", PS if not c[1] else ParagraphStyle('t', parent=PS, fontName='Helvetica-Bold')))
            else:
                row.append("")
        cells.append(row)
    story.append(grid(cells, [W / 2, W / 2], header=False))

    story.append(Paragraph("2. People, licences and competencies", H2))
    data = [[Paragraph(x, PW) for x in ("Worker", "Licence / ticket / training", "Status", "Detail")]]
    for c in doc.competencies:
        col = STATUS_COL.get(c.status, "#333333")
        data.append([Paragraph(e(c.name), P), Paragraph(e(c.label), P),
                     Paragraph(f'<font color="{col}"><b>{e(c.status)}</b></font>', P), Paragraph(e(c.detail), PS)])
    if len(data) == 1:
        data.append([Paragraph("No workers assigned", P), "", "", ""])
    story.append(grid(data, [50 * mm, 110 * mm, 40 * mm, W - 200 * mm]))
    fa = ", ".join(doc.emergency.get("first_aiders") or []) or "To be confirmed"
    story.append(Spacer(1, 3))
    story.append(Paragraph(f"<b>Designated first aider(s):</b> {e(fa)}", P))

    story.append(Paragraph("3. Personal protective equipment (minimum)", H2))
    story.append(Paragraph(" · ".join(e(p) for p in doc.ppe), P))

    story.append(Paragraph("4. Work steps, hazards and controls", H2))
    story.append(Paragraph("Controls are listed in order of the hierarchy of control: eliminate, substitute, isolate, engineering, "
                           "administrative, then PPE. Risk = likelihood x consequence before and after controls.", PS))
    story.append(Spacer(1, 3))
    data = [[Paragraph(x, PW) for x in ("#", "Work step", "Hazards", "Risk", "Control measures", "Residual", "Responsible")]]
    extra = []
    for s in doc.steps:
        ctl = "<br/>".join(f"<b>{e(HIERARCHY[c[0]])}:</b> {e(c[1])}" for c in s.controls)
        data.append([Paragraph(str(s.n), P), Paragraph(e(s.step), PB), Paragraph("<br/>".join("• " + e(h) for h in s.hazards), PS),
                     risk_cell(s.risk), Paragraph(ctl, PS), risk_cell(s.residual), Paragraph(e(s.responsible), PS)])
        r = len(data) - 1
        extra += [("BACKGROUND", (3, r), (3, r), RISK_COL.get(s.risk, colors.grey)),
                  ("BACKGROUND", (5, r), (5, r), RISK_COL.get(s.residual, colors.grey))]
    story.append(grid(data, [8 * mm, 46 * mm, 52 * mm, 17 * mm, W - 8 * mm - 46 * mm - 52 * mm - 34 * mm - 36 * mm, 17 * mm, 36 * mm], extra=extra))

    story.append(Paragraph("5. Emergency and incident arrangements", H2))
    em = doc.emergency
    rows = [[Paragraph("<b>Emergency</b>", P), Paragraph(e(em.get("call")), P)],
            [Paragraph("<b>Notifiable incidents</b>", P), Paragraph(
                "Deaths, serious injuries or illnesses and dangerous incidents must be reported to the regulator <b>immediately</b>. "
                "Preserve the site. " + e(em.get("regulator")), P)]]
    rows += [[Paragraph(f"<b>{e(f)}</b>", P), Paragraph("_______________________________________________ (complete on site)", P)]
             for f in em.get("site_fields", [])]
    story.append(grid(rows, [55 * mm, W - 55 * mm], header=False, extra=[("BACKGROUND", (0, 0), (0, -1), SHADE)]))

    story.append(Paragraph("6. Review", H2))
    story.append(Paragraph(
        "This SWMS must be kept on site and available for inspection while the work is carried out. Stop work and review it "
        "if the work, the site or the controls change, if a control doesn't work, or after any incident (r 300-302). "
        "Workers must be consulted on changes.", P))
    story.append(Paragraph("7. References", H2))
    story.append(Paragraph("<br/>".join("• " + e(r) for r in doc.references), PS))

    story.append(PageBreak())
    story.append(Paragraph("8. Worker sign-on: I have read (or had explained to me) and understand this SWMS, and will follow it", H2))
    data = [[Paragraph(x, PW) for x in ("Name", "Company", "Licence / ticket no.", "Signature", "Date")]]
    names = [w["name"] for w in doc.workers]
    for i in range(max(12, len(names) + 4)):
        data.append([Paragraph(e(names[i]) if i < len(names) else "", P), "", "", "", ""])
    story.append(grid(data, [60 * mm, 55 * mm, 45 * mm, 65 * mm, W - 225 * mm],
                      extra=[("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SHADE]), ("TOPPADDING", (0, 1), (-1, -1), 7),
                             ("BOTTOMPADDING", (0, 1), (-1, -1), 7)]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Person in charge on site</b> (name, signature, date): ____________________________________________", P))

    if doc.status == "DRAFT":
        story.append(PageBreak())
        story.append(Paragraph("Reviewer checklist (internal: removed when issued)", H1))
        story.append(Paragraph("Resolve every <b>BLOCKER</b> before issue. Confirm or tailor each <b>CHECK</b>. Then tailor the steps and controls "
                               "to the actual site. The library is generic and has not yet been legally reviewed.", P))
        data = [[Paragraph(x, PW) for x in ("Severity", "Item", "Done")]]
        for f in sorted(doc.flags, key=lambda f: f.severity != "blocker"):
            col = "#a3221c" if f.severity == "blocker" else "#7a5300"
            data.append([Paragraph(f'<font color="{col}"><b>{f.severity.upper()}</b></font>', P), Paragraph(e(f.text), P), "[  ]"])
        story.append(grid(data, [24 * mm, W - 44 * mm, 20 * mm]))
    return story


def render(doc: SwmsDoc, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    footer = (f"{doc.swms_no} v{doc.version} · {doc.status} · {doc.business.get('Legal name', '')} · "
              "Prepared from information supplied by the PCBU. Check controls against site conditions before work starts.")

    def on_page(c, d):
        w, h = landscape(A4)
        c.saveState()
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#5d6878"))
        c.drawString(12 * mm, 7 * mm, footer[:190])
        c.drawRightString(w - 12 * mm, 7 * mm, f"Page {d.page}")
        if doc.status == "DRAFT":
            c.setFont("Helvetica-Bold", 70)
            c.setFillColor(colors.Color(0.85, 0.2, 0.2, alpha=0.10))
            c.translate(w / 2, h / 2)
            c.rotate(30)
            c.drawCentredString(0, 0, "DRAFT - NOT FOR USE")
        c.restoreState()

    pdf = SimpleDocTemplate(str(out), pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=11 * mm, bottomMargin=13 * mm, title=f"SWMS {doc.swms_no} v{doc.version}",
                            author=str(doc.business.get("Legal name", "")))
    pdf.build(build_story(doc), onFirstPage=on_page, onLaterPages=on_page)
    return out
