"""SWMS generator CLI.

  Draft (writes 04_Jobs/<JobID>_*/Drafts/<JobID>_SWMS_v<n>_DRAFT.pdf + .json, sets SWMS status 'In review'):
    python -m swms draft --client-dir PATH --job J0002 [--master Master_Client_List.xlsx]

  Issue after human review (refuses while blockers remain unless --override "reason"):
    python -m swms issue --client-dir PATH --job J0002 --reviewer "Ivana" [--master ...] [--override "reason"]

Issuing writes 04_Jobs/<JobID>_*/Issued/<JobID>_SWMS_v<n>.pdf (no watermark, no checklist page) and sets the
register to Issued with the reviewer and time, which is what makes it downloadable in the client portal.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from openpyxl import load_workbook

from engine import expiry_engine as ee
from swms import model, render


class SwmsError(Exception):
    """A SWMS can't be drafted or issued; the message says why (shown to staff)."""


def _update_job(cdir: Path, job_id: str, values: dict):
    reg = ee.find_register(cdir)
    wb = load_workbook(reg)
    ws = wb["Jobs"]
    hdr = [c.value for c in ws[1]]
    for r in range(2, ws.max_row + 1):
        if str(ws.cell(row=r, column=1).value) == job_id:
            for k, v in values.items():
                ws.cell(row=r, column=hdr.index(k) + 1, value=v)
            try:
                wb.save(reg)
            except PermissionError as exc:
                raise SwmsError("The register is locked (open in desktop Excel?). Close it and retry.") from exc
            return
    raise KeyError(job_id)


def _audit(master: Path | None, client_id: str, ref: str, path: Path, status: str, reviewer: str = "", note: str = ""):
    if not master:
        return
    wb = load_workbook(master)
    ws = wb["Audit Log"]
    r = 2
    while ws.cell(row=r, column=1).value not in (None, ""):
        r += 1
    now = dt.datetime.now().replace(microsecond=0)
    vals = [now, client_id, "SWMS", ref, "swms generator", str(path), status, reviewer, now if reviewer else None, None, note]
    for c, v in enumerate(vals, start=1):
        ws.cell(row=r, column=c, value=v)
    wb.save(master)


def draft(cdir: Path, job_id: str, master: Path | None = None, today: dt.date | None = None) -> tuple[model.SwmsDoc, Path]:
    doc = model.build(cdir, job_id, today)
    folder = model.job_folder(cdir, doc.job) / "Drafts"
    pdf = render.render(doc, folder / f"{job_id}_SWMS_v{doc.version}_DRAFT.pdf")
    pdf.with_suffix(".json").write_text(json.dumps(doc.to_json(), indent=2, default=str), encoding="utf-8")
    _update_job(cdir, job_id, {"SWMS status": "In review", "SWMS file": str(pdf)})
    _audit(master, doc.client_id, f"{doc.swms_no} v{doc.version}", pdf, "Draft - awaiting review",
           note=f"{len(doc.blockers)} blockers, {len(doc.flags) - len(doc.blockers)} checks")
    return doc, pdf


def issue(cdir: Path, job_id: str, reviewer: str, master: Path | None = None, override: str = "",
          today: dt.date | None = None) -> tuple[model.SwmsDoc, Path]:
    if not reviewer.strip():
        raise SwmsError("A reviewer name is required to issue a SWMS.")
    wb_job = model.build(cdir, job_id, today).job  # locate the job folder
    drafts = sorted((model.job_folder(cdir, wb_job) / "Drafts").glob(f"{job_id}_SWMS_v*_DRAFT.json"),
                    key=lambda p: int(p.stem.split("_v")[1].split("_")[0]))
    if not drafts:
        raise SwmsError("No draft found. Run 'draft' first and review it.")
    # Issue exactly what the reviewer reviewed: the latest draft (its JSON may have been tailored by the reviewer).
    doc = model.SwmsDoc.from_json(json.loads(drafts[-1].read_text(encoding="utf-8")))
    if doc.blockers and not override:
        msg = "\n  - ".join(f.text for f in doc.blockers)
        raise SwmsError(f"Not issued: the latest draft (v{doc.version}) has {len(doc.blockers)} blocker(s):\n  - {msg}\n"
                         "Fix the register and re-draft, or pass --override \"reason\" (logged).")
    doc.status, doc.reviewed_by = "ISSUED", reviewer
    now = dt.datetime.now().replace(microsecond=0, second=0)
    doc.issued_at = now.isoformat()
    doc.review_note = override
    out = model.job_folder(cdir, wb_job) / "Issued" / f"{job_id}_SWMS_v{doc.version}.pdf"
    render.render(doc, out)
    out.with_suffix(".json").write_text(json.dumps(doc.to_json(), indent=2, default=str), encoding="utf-8")
    _update_job(cdir, job_id, {"SWMS status": "Issued", "SWMS issued at": now, "Reviewed by": reviewer, "SWMS file": str(out)})
    _audit(master, doc.client_id, f"{doc.swms_no} v{doc.version}", out, "Issued", reviewer,
           note=f"Override: {override}" if override else "")
    return doc, out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("draft", "issue"):
        s = sub.add_parser(name)
        s.add_argument("--client-dir", type=Path, required=True)
        s.add_argument("--job", required=True)
        s.add_argument("--master", type=Path)
        if name == "issue":
            s.add_argument("--reviewer", required=True)
            s.add_argument("--override", default="")
    a = ap.parse_args(argv)
    try:
        run(a)
    except (SwmsError, KeyError) as exc:
        raise SystemExit(str(exc)) from None


def run(a):
    if a.cmd == "draft":
        doc, pdf = draft(a.client_dir, a.job, a.master)
        print(f"Draft v{doc.version}: {pdf}")
        for f in doc.flags:
            print(f"  [{f.severity.upper()}] {f.text}")
    else:
        doc, pdf = issue(a.client_dir, a.job, a.reviewer, a.master, a.override)
        print(f"Issued v{doc.version}: {pdf}")


if __name__ == "__main__":
    main()
