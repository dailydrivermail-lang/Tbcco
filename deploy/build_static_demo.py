"""Export the client portal demo as a static site for Cloudflare Pages (or any static host).

    python deploy/build_static_demo.py                              # deploy/site/, served from /  (Cloudflare Pages)
    python deploy/build_static_demo.py --base /Tbcco/ --out _site   # GitHub Pages project site

How it works: rebuild the fictional demo clients, run the real Flask app in-process, log in as the
demo client and as staff, crawl every page, and write HTML/PDF files. Client pages go under
/client/, staff pages under /staff-view/. Forms point to a "demo: not saved" page.

FICTIONAL DATA ONLY. Never point this at real client folders: the output is public.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import sys
import tempfile
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import examples.make_demo as md  # noqa: E402
from portal import auth, create_app, data  # noqa: E402

OUT = ROOT / "deploy" / "site"
BASE = "/"  # URL prefix the site is served under, e.g. "/Tbcco/" on GitHub Pages
VIEWS = {  # prefix -> (login email, password, start paths)
    "client": ("pat@example.com", "demo-client-password", ["/c/C000/"]),
    "staff-view": ("staff@example.com", "demo-staff-password", ["/staff", "/staff/inbox"]),
}
SKIP = ("/logout", "/login", "/static/", "/healthz")
BANNER = ('<div class="demobar">Demo site · fictional data · forms are not saved · '
          '<a href="/">switch view</a></div>')


def seed_inbox(clients_root: Path):
    """Give the staff inbox something to show."""
    cdir = data.client_dir(clients_root, "C000")
    rec, errors = data.clean_assessment({
        "job_type": "drainage",
        "site": {"site_address": "7 Demo Cres, Gungahlin ACT", "state": "ACT", "start_date": "2026-12-02",
                 "scope": "Stormwater relocation along the boundary", "building_age": "post2003"},
        "answers": {"exc_depth": "gt15", "exc_support": "undecided", "exc_ground": "loose", "exc_adjacent": "yes", "exc_byda": "lodged",
                    "exc_services": ["gas"], "exc_method": "machine", "exc_operator": "own", "sew_live": "no", "sew_entry": "no",
                    "sur_road": "public", "sur_tgs": "none", "sur_occupied": "no", "sil_cut": "yes", "sil_method": "wet", "hot_any": "no",
                    **{q: "yes" for q in ("q_induct", "q_toolbox", "q_ppe", "q_firstaid", "q_tag", "q_rcd", "q_sds", "q_rpe",
                                          "q_ladder", "q_prestart")}},
        "crew": ["P001"], "plant_other": "", "notes": ""}, {"P001", "P002", "P003"})
    assert not errors, errors
    rec["submitted_by"] = "pat@example.com"
    data.save_swms_request(cdir, rec)
    (data.upload_dir(cdir) / "2026-11-24_101500_abc123_white_card_jo.jpg").write_bytes(b"\xff\xd8\xff demo")
    data.record_upload(cdir, {"at": "2026-11-24T10:15:00", "by": "pat@example.com", "original": "white card jo.jpg",
                              "stored_as": "2026-11-24_101500_abc123_white_card_jo.jpg", "doc_type": "White Card",
                              "about": "Jo Placeholder", "ref": ""})


def login(client, email, pw):
    html = client.get("/login").get_data(as_text=True)
    tok = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    r = client.post("/login", data={"email": email, "password": pw, "csrf_token": tok})
    assert r.status_code == 302, f"demo login failed for {email}"


def crawl(app, prefix, email, pw, starts):
    c = app.test_client()
    login(c, email, pw)
    pages, binaries = {}, {}
    q, seen = deque(starts), set(starts)
    while q:
        path = q.popleft()
        r = c.get(path, follow_redirects=True)
        if r.status_code != 200:
            print(f"  skip {path} ({r.status_code})")
            continue
        if r.mimetype == "text/html":
            html = r.get_data(as_text=True)
            pages[path] = html
            for href in re.findall(r'href="([^"]+)"', html):
                p = urlsplit(href).path
                if p.startswith("/") and not p.startswith(SKIP) and p not in seen:
                    seen.add(p)
                    q.append(p)
        else:
            binaries[path] = (r.data, r.mimetype)
    return pages, binaries


def out_path(prefix: str, path: str, binary_ext: str | None = None) -> str:
    """Site URL for an app path."""
    p = path.rstrip("/")
    if binary_ext:
        return f"/{prefix}{p}" if Path(p).suffix else f"/{prefix}{p}{binary_ext}"
    return f"/{prefix}{p}/"


def rewrite(html: str, prefix: str, mapping: dict[str, str]) -> str:
    def fix_href(m):
        attr, url = m.group(1), m.group(2)
        p = urlsplit(url).path
        if not p.startswith("/") or p.startswith("/static/"):
            return m.group(0)
        if p in ("/", "/login", "/logout"):
            return f'{attr}="/"'
        return f'{attr}="{mapping.get(p, out_path(prefix, p))}"'

    html = re.sub(r'(href)="([^"]+)"', fix_href, html)
    # Forms: no backend on a static host
    html = re.sub(r'<form method="post" action="[^"]*/logout"[^>]*>.*?</form>',
                  '<a href="/" class="link-out">Switch view</a>', html, flags=re.S)
    html = re.sub(r'<form([^>]*?)method="post"([^>]*)>', r'<form\1method="get"\2 action="/demo-not-saved/">', html)
    html = re.sub(r'<form([^>]*?) action="[^"]*"([^>]*?) action="/demo-not-saved/">', r'<form\1\2 action="/demo-not-saved/">', html)
    html = re.sub(r'<input type="hidden" name="csrf_token" value="[^"]*">', "", html)
    html = html.replace(' enctype="multipart/form-data"', "")
    html = html.replace("<head>", '<head>\n<meta name="robots" content="noindex, nofollow">', 1)
    html = re.sub(r"(<body[^>]*>)", r"\1\n" + BANNER, html, count=1)
    return html


def write(rel_url: str, content: bytes | str):
    rel = rel_url.lstrip("/")
    target = OUT / rel / "index.html" if rel_url.endswith("/") else OUT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str) and target.suffix == ".html" and BASE != "/":
        content = re.sub(r'(href|action|src)="/(?!/)', lambda m: f'{m.group(1)}="{BASE}', content)
    target.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)


def page_shell(app, title: str, body: str) -> str:
    sprite = (ROOT / "portal" / "templates" / "_icons.html").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="en-AU"><head><meta name="robots" content="noindex, nofollow"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<link rel="stylesheet" href="/static/portal.css"></head>
<body>{BANNER}{sprite}
<div class="auth">
  <section class="auth-brand">
    <span class="brand"><span class="brand-mark"><svg class="icon"><use href="#i-shield-check"/></svg></span><span>Compliance Portal</span></span>
    <h1>Audit-ready, without the paperwork.</h1>
    <p>A working preview of the portal our clients use, filled with a made-up plumbing business.</p>
    <p class="auth-foot">All names, licence numbers and companies on this site are made up.</p>
  </section>
  <section class="auth-form"><div class="inner">{body}</div></section>
</div>
</body></html>"""


def main(argv=None):
    global OUT, BASE
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="/", help="URL prefix, e.g. /Tbcco/ for a GitHub Pages project site")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    BASE = "/" + a.base.strip("/") + "/" if a.base.strip("/") else "/"
    OUT = a.out.resolve()
    tmp = Path(tempfile.mkdtemp(prefix="static_demo_"))
    try:
        md.main([])  # rebuild fictional demo clients into examples/demo
        root = tmp / "clients"
        root.mkdir()
        for p in md.OUT.iterdir():
            if p.is_dir() and re.match(r"C\d{3}_", p.name):
                shutil.copytree(p, root / p.name)
        seed_inbox(root)
        pdata = tmp / "portal"
        for _, (email, pw, _) in VIEWS.items():
            role = "staff" if "staff" in email else "client"
            auth.upsert_user(pdata, email, role=role, client_id=None if role == "staff" else "C000", password=pw,
                             name="Demo Staff" if role == "staff" else "Pat Owner")
        app = create_app({"CLIENTS_ROOT": str(root), "DATA_DIR": str(pdata), "TODAY": md.DEMO_TODAY,
                          "SECRET_KEY": "static-export", "TESTING": True})

        if OUT.exists():
            shutil.rmtree(OUT)
        OUT.mkdir(parents=True)
        shutil.copytree(ROOT / "portal" / "static", OUT / "static")
        total = 0
        for prefix, (email, pw, starts) in VIEWS.items():
            pages, binaries = crawl(app, prefix, email, pw, starts)
            mapping = {}
            for path, (body, mime) in binaries.items():
                ext = {"application/pdf": ".pdf"}.get(mime, "")
                url = out_path(prefix, path, ext or ".bin")
                mapping[path] = url
                write(url, body)
            for path, html in pages.items():
                write(out_path(prefix, path), rewrite(html, prefix, mapping))
            total += len(pages) + len(binaries)
            print(f"{prefix}: {len(pages)} pages, {len(binaries)} files")

        arrow = '<svg class="icon"><use href="#i-chevron-right"/></svg>'
        write("/", page_shell(app, "Compliance Portal demo", f"""
<h2>Pick a view</h2>
<p class="muted">Nothing you do here is saved.</p>
<div class="choice-cards">
  <a class="choice-card" href="/client/c/C000/"><span class="wz-type-icon"><svg class="icon"><use href="#i-users"/></svg></span>
    <span><strong>Client view</strong><span>What a trade business owner sees</span></span>{arrow}</a>
  <a class="choice-card" href="/client/c/C000/swms-request/"><span class="wz-type-icon"><svg class="icon"><use href="#i-clipboard"/></svg></span>
    <span><strong>Try the SWMS job assessment</strong><span>Guided questions that adapt to the job</span></span>{arrow}</a>
  <a class="choice-card" href="/staff-view/staff/"><span class="wz-type-icon"><svg class="icon"><use href="#i-building"/></svg></span>
    <span><strong>Staff view</strong><span>Every client by risk, plus the inbox</span></span>{arrow}</a>
</div>"""))
        write("/demo-not-saved/", page_shell(app, "Demo: not saved", """
<h2>Demo mode</h2>
<p class="muted">Nothing was sent or saved. This preview has no back end.</p>
<p class="muted">In the real portal, uploads and job assessments go straight to our team, and a SWMS request starts the 24-hour turnaround.</p>
<div class="choice-cards"><a class="btn btn-primary btn-lg" href="/">Back to the demo</a></div>"""))
        write("/404.html", page_shell(app, "Not found", '<h2>Page not found</h2><div class="choice-cards"><a class="btn btn-primary" href="/">Demo home</a></div>'))
        write("/robots.txt", "User-agent: *\nDisallow: /\n")
        write("/_headers", "/*\n  X-Robots-Tag: noindex, nofollow\n  X-Frame-Options: DENY\n  X-Content-Type-Options: nosniff\n"
                           "  Referrer-Policy: same-origin\n"
                           "  Content-Security-Policy: default-src 'self'; style-src 'self'; img-src 'self' data:; "
                           "script-src 'self'; frame-ancestors 'none'\n")
        (OUT / "build.json").write_text(json.dumps({"built": dt.datetime.now().isoformat(timespec="seconds"),
                                                    "demo_today": md.DEMO_TODAY.isoformat()}, indent=2))
        (OUT / ".nojekyll").write_text("")  # GitHub Pages: serve files as-is
        print(f"Static demo written to {OUT} for base {BASE} ({total} items)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
