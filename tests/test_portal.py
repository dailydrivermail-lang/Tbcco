import io
import re
import shutil
from pathlib import Path

import pytest
from openpyxl import load_workbook

from portal import auth, create_app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def demo_root(tmp_path_factory):
    import examples.make_demo as md
    md.main([])
    root = tmp_path_factory.mktemp("clients")
    for p in md.OUT.iterdir():
        if p.is_dir() and p.name.startswith("C"):
            shutil.copytree(p, root / p.name)
    return root, md.DEMO_TODAY


@pytest.fixture()
def app(demo_root, tmp_path):
    root, today = demo_root
    data = tmp_path / "portal"
    auth.upsert_user(data, "pat@example.com", role="client", client_id="C000", password="client-password-1")
    auth.upsert_user(data, "lee@example.com", role="client", client_id="C001", password="client-password-2")
    auth.upsert_user(data, "staff@example.com", role="staff", password="staff-password-1")
    auth.reset_throttle()
    return create_app({"CLIENTS_ROOT": str(root), "DATA_DIR": str(data), "TODAY": today, "TESTING": True,
                       "SECRET_KEY": "test"})


def _csrf(client, url):
    html = client.get(url).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def login(client, email, pw):
    tok = _csrf(client, "/login")
    return client.post("/login", data={"email": email, "password": pw, "csrf_token": tok})


def test_login_required(app):
    c = app.test_client()
    r = c.get("/c/C000/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_bad_password_and_throttle(app):
    c = app.test_client()
    for _ in range(8):
        assert login(c, "pat@example.com", "wrong").status_code == 401
    assert login(c, "pat@example.com", "client-password-1").status_code == 429


def test_csrf_enforced(app):
    c = app.test_client()
    c.get("/login")
    r = c.post("/login", data={"email": "pat@example.com", "password": "client-password-1"})
    assert r.status_code == 400


def test_client_sees_own_dashboard_only(app):
    c = app.test_client()
    r = login(c, "pat@example.com", "client-password-1")
    assert r.headers["Location"].endswith("/")
    r = c.get("/", follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "Demo Plumbing" in html and "Action needed" in html
    # unreviewed-rule gaps hidden from clients by default
    assert "not on file" not in html
    assert c.get("/c/C001/").status_code == 403
    assert c.get("/c/C001/reports/Monthly/x.pdf").status_code == 403
    assert c.get("/staff").status_code == 403


def test_pages_render(app):
    c = app.test_client()
    login(c, "pat@example.com", "client-password-1")
    for path, text in [("/c/C000/people", "Sam Example"), ("/c/C000/insurance", "Placeholder Drainage"),
                       ("/c/C000/jobs", "J0001"), ("/c/C000/reports", "Monthly_Summary"),
                       ("/c/C000/upload", "Send documents"), ("/c/C000/swms-request", "Request a SWMS")]:
        r = c.get(path)
        assert r.status_code == 200, path
        assert text in r.get_data(as_text=True), path


def test_swms_download_only_when_issued_and_reviewed(app):
    c = app.test_client()
    login(c, "pat@example.com", "client-password-1")
    r = c.get("/c/C000/jobs/J0001/swms")
    assert r.status_code == 200 and r.data.startswith(b"%PDF")
    assert c.get("/c/C000/jobs/J0002/swms").status_code == 404  # In review


def test_report_path_traversal_blocked(app):
    c = app.test_client()
    login(c, "pat@example.com", "client-password-1")
    assert c.get("/c/C000/reports/../00_Register/C000_Register.xlsx").status_code == 404
    assert c.get("/c/C000/reports/..%2F00_Register%2FC000_Register.xlsx").status_code == 404
    ok = c.get("/c/C000/reports").get_data(as_text=True)
    link = re.search(r'href="(/c/C000/reports/Monthly/[^"]+)"', ok).group(1)
    assert c.get(link).data.startswith(b"%PDF")


def test_upload(app, demo_root):
    root, _ = demo_root
    c = app.test_client()
    login(c, "pat@example.com", "client-password-1")
    tok = _csrf(c, "/c/C000/upload")
    r = c.post("/c/C000/upload", content_type="multipart/form-data", data={
        "csrf_token": tok, "doc_type": "White Card", "about": "Jo",
        "files": [(io.BytesIO(b"%PDF-1.4 test"), "white card.pdf"),
                  (io.BytesIO(b"MZ evil"), "evil.exe"),
                  (io.BytesIO(b"not a pdf"), "fake.pdf")]}, follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "Uploaded 1 file" in html and "evil.exe" in html and "fake.pdf" in html
    stored = list((root / "C000_Demo-Plumbing-Pty-Ltd" / "01_Intake_Inbox" / "portal").glob("*white_card.pdf"))
    assert stored


PAYLOAD = {
    "job_type": "drainage",
    "site": {"site_address": "1 Test St", "state": "ACT", "start_date": "2026-12-01", "scope": "Stormwater trench along boundary",
             "building_age": "post2003"},
    "answers": {"exc_depth": "gt15", "exc_support": "shield", "exc_ground": "stable", "exc_adjacent": "no", "exc_byda": "have",
                "exc_services": ["gas"], "exc_method": "machine", "exc_operator": "own", "sew_live": "no", "sew_entry": "no",
                "sur_road": "no", "sur_occupied": "no", "sil_cut": "no", "hot_any": "no",
                "q_induct": "yes", "q_toolbox": "yes", "q_ppe": "yes", "q_firstaid": "yes", "q_tag": "no", "q_rcd": "yes",
                "q_sds": "yes", "q_ladder": "yes", "q_prestart": "yes",
                "hw_new": "gas_cf"},   # not a drainage question: must be dropped
    "crew": ["P001", "P002", "P999"], "plant_other": "Jetter", "notes": "Narrow side access",
}


def test_swms_assessment_flow(app, demo_root):
    import json
    root, today = demo_root
    cdir = root / "C000_Demo-Plumbing-Pty-Ltd"
    c = app.test_client()
    login(c, "pat@example.com", "client-password-1")
    page = c.get("/c/C000/swms-request").get_data(as_text=True)
    assert 'id="assess-data"' in page and "pending legal review" not in page      # reviewer wording hidden from clients
    tok = _csrf(c, "/c/C000/swms-request")
    # incomplete: rejected
    bad = {**PAYLOAD, "answers": {"exc_depth": "gt15"}}
    r = c.post("/c/C000/swms-request", data={"csrf_token": tok, "payload": json.dumps(bad)}, follow_redirects=True)
    assert "still need an answer" in r.get_data(as_text=True)
    r = c.post("/c/C000/swms-request", data={"csrf_token": tok, "payload": "not json"}, follow_redirects=True)
    assert "try again" in r.get_data(as_text=True)
    r = c.post("/c/C000/swms-request", data={"csrf_token": tok, "payload": json.dumps(PAYLOAD)}, follow_redirects=True)
    assert "24-hour clock has started" in r.get_data(as_text=True)
    assert c.get("/c/C000/swms-request?job=J0001").status_code == 403           # clients can't re-open assessments
    # staff: see it in the inbox with its risk summary, then accept
    s = app.test_client()
    login(s, "staff@example.com", "staff-password-1")
    inbox = s.get("/staff/inbox").get_data(as_text=True)
    assert "Excavation and trenching" in inbox and "Edit answers" in inbox
    action = re.search(r'action="(/staff/c/C000/swms-request/[^"]+/accept)"', inbox).group(1)
    tok = re.search(r'name="csrf_token" value="([^"]+)"', inbox).group(1)
    r = s.post(action, data={"csrf_token": tok}, follow_redirects=True)
    assert "Added to C000" in r.get_data(as_text=True)
    wb = load_workbook(next((cdir / "00_Register").glob("*.xlsx")))
    hdr = [x.value for x in wb["Jobs"][1]]
    new = [j for j in wb["Jobs"].iter_rows(min_row=2, values_only=True) if j[0] and j[2] == "1 Test St"][0]
    get = lambda k: new[hdr.index(k)]
    assert get("Hazard: trench over 1.5m") == "Y" and get("Hazard: traffic / mobile plant") == "Y" and get("Hazard: asbestos") == "N"
    assert get("SWMS status") == "Requested" and get("Workers assigned (Person IDs)") == "P001; P002"   # unknown P999 dropped
    assert "Trench shield" in get("Plant and equipment") and "Jetter" in get("Plant and equipment")
    job_id = get("Job ID")
    saved = json.loads(next((cdir / "04_Jobs").glob(f"{job_id}_*/assessment.json")).read_text())
    assert "hw_new" not in saved["answers"] and saved["answers"]["exc_support"] == "shield"
    r = s.post(action, data={"csrf_token": tok}, follow_redirects=True)
    assert "already processed" in r.get_data(as_text=True)
    # the SWMS picks up the answers
    from swms import model
    doc = model.build(cdir, job_id, today)
    assert doc.template.startswith("Sewer")
    excavate = next(st for st in doc.steps if st.step.startswith("Excavate"))
    assert any("Site-specific: trench shield" in ctl[1] for ctl in excavate.controls)
    assert any(d["label"] == "Trench support" and d["priority"] == "key" for d in doc.assessment)
    assert any("pressurised gas" in cat and on for cat, on in doc.hrcw)
    assert any("Test and tag" in f.text for f in doc.flags)
    assert not any(f.text.startswith("[Job assessment]") and f.severity == "blocker" for f in doc.flags)
    # staff re-open the job's assessment and change a key answer: it now blocks
    edit = s.get(f"/c/C000/swms-request?job={job_id}").get_data(as_text=True)
    assert "Edit assessment" in edit and "pending legal review" in edit            # staff see reviewer wording
    tok = re.search(r'name="csrf_token" value="([^"]+)"', edit).group(1)
    changed = {**PAYLOAD, "answers": {**PAYLOAD["answers"], "exc_support": "undecided"}}
    r = s.post(f"/c/C000/swms-request?job={job_id}", data={"csrf_token": tok, "payload": json.dumps(changed)}, follow_redirects=True)
    assert "Re-draft the SWMS" in r.get_data(as_text=True)
    doc = model.build(cdir, job_id, today)
    assert any("Trench support method not decided" in f.text for f in doc.blockers)


def test_staff_overview_and_unreviewed_gaps(app):
    s = app.test_client()
    login(s, "staff@example.com", "staff-password-1")
    html = s.get("/staff").get_data(as_text=True)
    assert "Demo Plumbing" in html and "Example Gas" in html
    assert html.index("Demo Plumbing") < html.index("Example Gas")  # RED sorted first
    dash = s.get("/c/C000/").get_data(as_text=True)
    assert "rule pending review" in dash and 'class="crumbs"' in dash


def test_security_headers(app):
    r = app.test_client().get("/login")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "no-store"


def test_disabled_user_cannot_log_in(app):
    data = app.config["DATA_DIR"]
    auth.upsert_user(data, "lee@example.com", role="client", client_id="C001", active=False)
    c = app.test_client()
    assert login(c, "lee@example.com", "client-password-2").status_code == 401


def test_staff_swms_draft_and_issue_in_portal(app):
    s = app.test_client()
    login(s, "staff@example.com", "staff-password-1")
    page = s.get("/c/C000/jobs").get_data(as_text=True)
    tok = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    r = s.post("/staff/c/C000/jobs/J0002/swms/draft", data={"csrf_token": tok}, follow_redirects=True)
    assert "blocker" in r.get_data(as_text=True)
    assert s.get("/staff/c/C000/jobs/J0002/swms/draft.pdf").data.startswith(b"%PDF")
    r = s.post("/staff/c/C000/jobs/J0002/swms/issue", data={"csrf_token": tok}, follow_redirects=True)
    assert "Tick the box" in r.get_data(as_text=True)
    r = s.post("/staff/c/C000/jobs/J0002/swms/issue", data={"csrf_token": tok, "confirm": "yes"}, follow_redirects=True)
    assert "Not issued" in r.get_data(as_text=True)
    # clients can't reach staff SWMS actions
    c = app.test_client()
    login(c, "pat@example.com", "client-password-1")
    ctok = _csrf(c, "/c/C000/upload")
    assert c.post("/staff/c/C000/jobs/J0002/swms/draft", data={"csrf_token": ctok}).status_code == 403
    assert c.get("/staff/c/C000/jobs/J0002/swms/draft.pdf").status_code == 403
    assert "Generate draft" not in c.get("/c/C000/jobs").get_data(as_text=True)
