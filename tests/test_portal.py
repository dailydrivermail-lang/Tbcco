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
                       ("/c/C000/upload", "Send us documents"), ("/c/C000/swms-request", "Request a SWMS")]:
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


def test_swms_request_flow(app, demo_root):
    root, _ = demo_root
    c = app.test_client()
    login(c, "pat@example.com", "client-password-1")
    tok = _csrf(c, "/c/C000/swms-request")
    r = c.post("/c/C000/swms-request", data={"csrf_token": tok, "site_address": "1 Test St", "state": "ACT",
                                             "start_date": "2026-12-01", "scope": "Trench for stormwater",
                                             "hz_trench": "on"}, follow_redirects=True)
    assert "24-hour clock has started" in r.get_data(as_text=True)
    assert c.post("/c/C000/swms-request", data={"csrf_token": tok, "state": "ACT"}).status_code == 400
    # staff accepts into the Jobs register
    s = app.test_client()
    login(s, "staff@example.com", "staff-password-1")
    inbox = s.get("/staff/inbox").get_data(as_text=True)
    action = re.search(r'action="(/staff/c/C000/swms-request/[^"]+/accept)"', inbox).group(1)
    tok = re.search(r'name="csrf_token" value="([^"]+)"', inbox).group(1)
    r = s.post(action, data={"csrf_token": tok}, follow_redirects=True)
    assert "Added to C000" in r.get_data(as_text=True)
    wb = load_workbook(next((root / "C000_Demo-Plumbing-Pty-Ltd" / "00_Register").glob("*.xlsx")))
    jobs = [row for row in wb["Jobs"].iter_rows(min_row=2, values_only=True) if row[0]]
    new = [j for j in jobs if j[2] == "1 Test St"][0]
    hdr = [c.value for c in wb["Jobs"][1]]
    assert new[hdr.index("Hazard: trench over 1.5m")] == "Y" and new[hdr.index("SWMS status")] == "Requested"
    # can't accept twice
    r = s.post(action, data={"csrf_token": tok}, follow_redirects=True)
    assert "already processed" in r.get_data(as_text=True)


def test_staff_overview_and_unreviewed_gaps(app):
    s = app.test_client()
    login(s, "staff@example.com", "staff-password-1")
    html = s.get("/staff").get_data(as_text=True)
    assert "Demo Plumbing" in html and "Example Gas" in html
    assert html.index("Demo Plumbing") < html.index("Example Gas")  # RED sorted first
    dash = s.get("/c/C000/").get_data(as_text=True)
    assert "rule pending review" in dash and "Staff view" in dash


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
