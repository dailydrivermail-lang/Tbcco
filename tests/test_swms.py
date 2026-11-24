import datetime as dt
import json
import re
import shutil
from pathlib import Path

import pytest
from openpyxl import load_workbook

from swms import model
from swms.__main__ import SwmsError, draft, issue

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def client(tmp_path):
    import examples.make_demo as md
    if not (md.OUT / "C000_Demo-Plumbing-Pty-Ltd").exists():
        md.main([])
    dst = tmp_path / "C000_Demo-Plumbing-Pty-Ltd"
    shutil.copytree(md.OUT / "C000_Demo-Plumbing-Pty-Ltd", dst)
    shutil.rmtree(dst / "04_Jobs")
    (dst / "04_Jobs").mkdir()
    return dst, md.DEMO_TODAY


def _set_job(cdir, job_id, **vals):
    reg = next((cdir / "00_Register").glob("*.xlsx"))
    wb = load_workbook(reg)
    ws = wb["Jobs"]
    hdr = [c.value for c in ws[1]]
    for r in range(2, ws.max_row + 1):
        if ws.cell(row=r, column=1).value == job_id:
            for k, v in vals.items():
                ws.cell(row=r, column=hdr.index(k) + 1, value=v)
    wb.save(reg)


def test_library_is_well_formed():
    hz, tk = model.load_library()
    codes = {c[0] for c in __import__("engine.schema", fromlist=["x"]).CREDENTIAL_TYPES}
    for key, m in hz.items():
        assert m["steps"], key
        for s in m["steps"]:
            assert s["position"] in ("first", "early", "middle", "late", "any", "last"), key
            assert s["risk"] in model.RISK and s["residual"] in model.RISK, key
            assert all(c[0] in model.HIERARCHY for c in s["controls"]), key
            assert s["responsible"] in ("supervisor", "licensed", "all"), key
        for c in m.get("competencies") or []:
            assert c["code"] in codes, (key, c)
        assert m.get("references"), f"{key} has no references"
    for t in tk["templates"]:
        assert 0 <= t["middle_after"] <= len(t["steps"])
        for tr in t["licence"]:
            assert tr in tk["licences"]


def test_drainage_job_model(client):
    cdir, today = client
    doc = model.build(cdir, "J0001", today)
    assert doc.template.startswith("Sewer")
    assert not doc.blockers, [f.text for f in doc.blockers]
    ticked = [c for c, t in doc.hrcw if t]
    assert any("trench" in c for c in ticked) and any("asbestos" in c for c in ticked)
    assert doc.steps[0].source == "base" and "induction" in doc.steps[0].step
    assert "Clean up" in doc.steps[-1].step
    names = [s.step for s in doc.steps]
    assert names.index("Locate underground services before digging") < names.index("Excavate trench deeper than 1.5 m")
    for s in doc.steps:  # controls in hierarchy order
        idx = [model.HIER_ORDER.index(c[0]) for c in s.controls]
        assert idx == sorted(idx)
    assert any("Sam Example" in s.responsible for s in doc.steps)


def test_nsw_job_blockers_and_categories(client):
    cdir, today = client
    doc = model.build(cdir, "J0002", today)
    texts = " | ".join(f.text for f in doc.blockers)
    assert "White Card" in texts                 # Jo has no White Card
    assert "NSW plumbing licence" in texts       # Jo's NSW cert has no recorded categories; Sam is ACT-only
    assert any("mutual recognition" in f.text for f in doc.flags)
    # record Jo's categories as Draining only: still no plumbing licensee
    reg = next((cdir / "00_Register").glob("*.xlsx"))
    wb = load_workbook(reg)
    ws = wb["Credentials"]
    hdr = [c.value for c in ws[1]]
    for r in range(2, ws.max_row + 1):
        if ws.cell(row=r, column=hdr.index("Credential type") + 1).value == "NSW_TRADE_PDG":
            ws.cell(row=r, column=hdr.index("Class / categories") + 1, value="Draining")
    wb.save(reg)
    doc = model.build(cdir, "J0002", today)
    assert any("NSW plumbing licence" in f.text for f in doc.blockers)
    # ...but Plumbing category clears it
    wb = load_workbook(reg)
    ws = wb["Credentials"]
    for r in range(2, ws.max_row + 1):
        if ws.cell(row=r, column=hdr.index("Credential type") + 1).value == "NSW_TRADE_PDG":
            ws.cell(row=r, column=hdr.index("Class / categories") + 1, value="Water plumbing, Draining")
    wb.save(reg)
    doc = model.build(cdir, "J0002", today)
    assert not any("NSW plumbing licence" in f.text for f in doc.blockers)


def test_unassigned_workers_and_missing_fields_block(client):
    cdir, today = client
    _set_job(cdir, "J0001", **{"Workers assigned (Person IDs)": "Nobody Known"})
    doc = model.build(cdir, "J0001", today)
    assert any("Nobody Known" in f.text for f in doc.blockers)
    assert any("No workers assigned" in f.text for f in doc.blockers)


def test_draft_and_issue_flow(client, tmp_path):
    cdir, today = client
    master = tmp_path / "Master.xlsx"
    shutil.copy(ROOT / "templates" / "Master_Client_List.xlsx", master)
    with pytest.raises(SwmsError, match="No draft"):
        issue(cdir, "J0001", "Ivana", master, today=today)
    doc, pdf = draft(cdir, "J0001", master, today)
    assert pdf.exists() and pdf.name == "J0001_SWMS_v1_DRAFT.pdf"
    assert pdf.with_suffix(".json").exists()
    doc2, pdf2 = draft(cdir, "J0001", master, today)
    assert doc2.version == 2
    with pytest.raises(SwmsError, match="reviewer"):
        issue(cdir, "J0001", "  ", master, today=today)
    # reviewer tailors the draft JSON; the issued SWMS must carry the edit
    j = json.loads(pdf2.with_suffix(".json").read_text())
    j["steps"][0]["controls"].append(["A", "Tailored control added by reviewer"])
    pdf2.with_suffix(".json").write_text(json.dumps(j))
    doc3, issued = issue(cdir, "J0001", "Ivana", master, today=today)
    assert issued.name == "J0001_SWMS_v2.pdf" and issued.exists()
    out = json.loads(issued.with_suffix(".json").read_text())
    assert out["status"] == "ISSUED" and out["reviewed_by"] == "Ivana"
    assert ["A", "Tailored control added by reviewer"] in out["steps"][0]["controls"]
    reg = load_workbook(next((cdir / "00_Register").glob("*.xlsx")))
    ws = reg["Jobs"]
    hdr = [c.value for c in ws[1]]
    row = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[0] == "J0001"][0]
    assert row[hdr.index("SWMS status")] == "Issued" and row[hdr.index("Reviewed by")] == "Ivana"
    audit = [r for r in load_workbook(master)["Audit Log"].iter_rows(min_row=2, values_only=True) if r[0]]
    assert [a[6] for a in audit] == ["Draft - awaiting review", "Draft - awaiting review", "Issued"]


def test_issue_refuses_blockers_unless_override(client):
    cdir, today = client
    draft(cdir, "J0002", None, today)
    with pytest.raises(SwmsError, match="blocker"):
        issue(cdir, "J0002", "Ivana", today=today)
    doc, out = issue(cdir, "J0002", "Ivana", override="Jo removed from job by phone; register to follow", today=today)
    assert json.loads(out.with_suffix(".json").read_text())["review_note"].startswith("Jo removed")
