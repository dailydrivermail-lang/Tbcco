"""Client portal (Flask).

    create_app(overrides) -> Flask app. See portal/config.py for settings, portal/run.py to serve.
"""
from __future__ import annotations

import datetime as dt
import secrets
from pathlib import Path

from flask import (Blueprint, Flask, abort, current_app, flash, redirect, render_template, request, send_file,
                   session, url_for)
from werkzeug.utils import secure_filename

from engine import expiry_engine as ee
from portal import auth, config, data

bp = Blueprint("portal", __name__)

MAGIC = {".pdf": [b"%PDF"], ".png": [b"\x89PNG"], ".jpg": [b"\xff\xd8\xff"], ".jpeg": [b"\xff\xd8\xff"],
         ".docx": [b"PK"], ".xlsx": [b"PK"]}
DOC_TYPES = ["Licence or ticket", "White Card", "Training certificate (e.g. asbestos, silica, first aid)",
             "Insurance certificate of currency", "Subcontractor statement", "Safety data sheet (SDS)",
             "Test and tag / service record", "Incident or near miss", "Policy or procedure", "Other"]


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(config.load(overrides))
    app.register_blueprint(bp)

    @app.before_request
    def _csrf():
        auth.check_csrf()

    @app.after_request
    def _headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = ("default-src 'self'; style-src 'self'; img-src 'self' data:; "
                                                   "script-src 'self'; frame-ancestors 'none'; form-action 'self'")
        if request.endpoint not in ("static",):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.context_processor
    def _ctx():
        return {"csrf_token": auth.csrf_token, "user": auth.current_user(), "STATUS_TEXT": data.STATUS_TEXT,
                "fmt_date": lambda d: d.strftime("%d %b %Y") if d else "", "short_label": _label,
                "evidence_names": lambda codes: " or ".join(ee.short_label(c) for c in codes.split("|") if c)}

    @app.errorhandler(403)
    def _403(e):
        return render_template("error.html", code=403, message="You don't have access to that page."), 403

    @app.errorhandler(404)
    def _404(e):
        return render_template("error.html", code=404, message="We couldn't find that page."), 404

    @app.errorhandler(400)
    def _400(e):
        return render_template("error.html", code=400, message=getattr(e, "description", "Bad request.")), 400

    @app.errorhandler(413)
    def _413(e):
        return render_template("error.html", code=413,
                               message=f"That file is too large. The limit is {config.MAX_UPLOAD_MB} MB."), 413

    return app


def _label(item) -> str:
    if item.sheet == "Credentials":
        return data.CRED_NAMES.get(item.kind, item.kind)
    if item.sheet == "Insurances":
        return data.INS_NAMES.get(item.kind, item.kind)
    return item.label


def _today() -> dt.date:
    return current_app.config.get("TODAY") or dt.date.today()


def _client(client_id: str):
    if not auth.can_view(client_id):
        abort(403)
    cdir = data.client_dir(current_app.config["CLIENTS_ROOT"], client_id)
    if not cdir:
        abort(404)
    staff = auth.current_user()["role"] == "staff"
    view = data.build_view(cdir, _today(), data.load_rules_cached(),
                           include_unreviewed=staff or current_app.config["SHOW_UNREVIEWED_RULE_GAPS"])
    return cdir, view


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if auth.throttled():
            flash("Too many attempts. Wait 15 minutes and try again.", "error")
            return render_template("login.html"), 429
        u = auth.check_login(current_app.config["DATA_DIR"], request.form.get("email", ""), request.form.get("password", ""))
        if not u:
            auth.record_failure()
            auth.audit("login_failed", detail=request.form.get("email", "")[:100])
            flash("That email and password don't match.", "error")
            return render_template("login.html"), 401
        session.clear()
        session.permanent = True
        session["email"] = u["email"]
        auth.audit("login", u.get("client_id") or "")
        nxt = request.args.get("next", "")
        return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("portal.home"))
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    auth.audit("logout")
    session.clear()
    return redirect(url_for("portal.login"))


@bp.route("/")
@auth.login_required
def home():
    u = auth.current_user()
    if u["role"] == "staff":
        return redirect(url_for("portal.staff_overview"))
    return redirect(url_for("portal.dashboard", client_id=u["client_id"]))


@bp.route("/healthz")
def healthz():
    return {"ok": True}


# ---------------------------------------------------------------------------
# Client pages
# ---------------------------------------------------------------------------

@bp.route("/c/<client_id>/")
@auth.login_required
def dashboard(client_id):
    cdir, v = _client(client_id)
    reports = data.list_reports(cdir)[:3]
    pending = data.list_swms_requests(cdir, "Pending")
    return render_template("dashboard.html", v=v, reports=reports, pending=pending, active="dashboard")


@bp.route("/c/<client_id>/people")
@auth.login_required
def people(client_id):
    cdir, v = _client(client_id)
    return render_template("people.html", v=v, active="people")


@bp.route("/c/<client_id>/insurance")
@auth.login_required
def insurance(client_id):
    cdir, v = _client(client_id)
    subs = {str(s.get("Subcontractor ID")): s for s in v.subbies}
    return render_template("insurance.html", v=v, subs=subs, active="insurance")


@bp.route("/c/<client_id>/jobs")
@auth.login_required
def jobs(client_id):
    cdir, v = _client(client_id)
    rows = []
    for j in sorted(v.jobs, key=lambda j: str(j.get("Job ID")), reverse=True):
        rows.append({"job": j, "pdf": data.issued_swms(cdir, j),
                     "draft": data.latest_draft(cdir, j) if auth.current_user()["role"] == "staff" else None})
    reqs = data.list_swms_requests(cdir, "Pending")
    return render_template("jobs.html", v=v, rows=rows, reqs=reqs, active="jobs")


@bp.route("/c/<client_id>/jobs/<job_id>/swms")
@auth.login_required
def swms_download(client_id, job_id):
    cdir, v = _client(client_id)
    job = next((j for j in v.jobs if str(j.get("Job ID")) == job_id), None)
    pdf = data.issued_swms(cdir, job) if job else None
    if not pdf:
        abort(404)
    auth.audit("download_swms", client_id, f"{job_id} {pdf.name}")
    return send_file(pdf, as_attachment=True, download_name=pdf.name)


@bp.route("/c/<client_id>/swms-request", methods=["GET", "POST"])
@auth.login_required
def swms_request(client_id):
    cdir, v = _client(client_id)
    if request.method == "POST":
        f = request.form
        errors = [label for key, label in (("site_address", "Site address"), ("state", "State"), ("scope", "What's the job"),
                                           ("start_date", "Start date")) if not f.get(key, "").strip()]
        try:
            if f.get("start_date"):
                dt.date.fromisoformat(f["start_date"])
        except ValueError:
            errors.append("Start date (use the date picker)")
        if errors:
            flash("Please fill in: " + ", ".join(errors), "error")
            return render_template("swms_request.html", v=v, hazards=data.HAZARDS, form=f, active="jobs"), 400
        rec = {k: f.get(k, "").strip()[:2000] for k in ("site_address", "state", "head_contractor", "scope", "start_date",
                                                        "est_value", "workers", "plant", "other_hazards", "building_age",
                                                        "site_notes", "client_ref", "hc_template")}
        rec.update({h: bool(f.get(h)) for h, _, _ in data.HAZARDS})
        rec["submitted_by"] = auth.current_user()["email"]
        saved = data.save_swms_request(cdir, rec)
        auth.audit("swms_request", client_id, saved["request_id"])
        flash("Thanks. We've received your SWMS request and the 24-hour clock has started. We'll email you when it's ready.", "ok")
        return redirect(url_for("portal.jobs", client_id=client_id))
    return render_template("swms_request.html", v=v, hazards=data.HAZARDS, form={}, active="jobs")


@bp.route("/c/<client_id>/reports")
@auth.login_required
def reports(client_id):
    cdir, v = _client(client_id)
    return render_template("reports.html", v=v, reports=data.list_reports(cdir), active="reports")


@bp.route("/c/<client_id>/reports/<path:rel>")
@auth.login_required
def report_download(client_id, rel):
    cdir, v = _client(client_id)
    p = data.safe_child(cdir / "09_Client_Reports", rel)
    if not p:
        abort(404)
    auth.audit("download_report", client_id, rel)
    return send_file(p, as_attachment=True, download_name=p.name)


@bp.route("/c/<client_id>/upload", methods=["GET", "POST"])
@auth.login_required
def upload(client_id):
    cdir, v = _client(client_id)
    if request.method == "POST":
        files = [f for f in request.files.getlist("files") if f and f.filename]
        if not files:
            flash("Choose at least one file.", "error")
            return redirect(request.url)
        doc_type = request.form.get("doc_type", "")[:80]
        about = request.form.get("about", "").strip()[:200]
        ref = request.form.get("ref", "").strip()[:40]
        saved, rejected = [], []
        for f in files[:20]:
            name = secure_filename(f.filename) or "upload"
            ext = Path(name).suffix.lower()
            head = f.stream.read(8)
            f.stream.seek(0)
            if ext not in config.ALLOWED_UPLOAD_EXT or (ext in MAGIC and not any(head.startswith(m) for m in MAGIC[ext])):
                rejected.append(f.filename)
                continue
            stored = f"{dt.datetime.now():%Y-%m-%d_%H%M%S}_{secrets.token_hex(3)}_{name}"
            f.save(data.upload_dir(cdir) / stored)
            data.record_upload(cdir, {"at": dt.datetime.now().isoformat(timespec="seconds"), "by": auth.current_user()["email"],
                                      "original": f.filename[:200], "stored_as": stored, "doc_type": doc_type,
                                      "about": about, "ref": ref})
            saved.append(f.filename)
            auth.audit("upload", client_id, stored)
        if saved:
            flash(f"Uploaded {len(saved)} file(s). We'll check and add them to your register, usually within 2 business days.", "ok")
        if rejected:
            flash("Not accepted (use PDF, photo, Word or Excel): " + ", ".join(rejected), "error")
        return redirect(url_for("portal.upload", client_id=client_id))
    ref = request.args.get("ref", "")
    about = request.args.get("about", "")
    return render_template("upload.html", v=v, doc_types=DOC_TYPES, uploads=data.list_uploads(cdir, 20),
                           ref=ref, about=about, accept=",".join(sorted(config.ALLOWED_UPLOAD_EXT)), active="upload")


# ---------------------------------------------------------------------------
# Staff
# ---------------------------------------------------------------------------

@bp.route("/staff")
@auth.staff_required
def staff_overview():
    rows = []
    for cid, cdir in data.find_clients(current_app.config["CLIENTS_ROOT"]).items():
        try:
            v = data.build_view(cdir, _today(), data.load_rules_cached(), include_unreviewed=True)
        except Exception as e:  # a broken register shouldn't take the whole page down
            rows.append({"cid": cid, "error": str(e)[:200]})
            continue
        ups = [u for u in data.list_uploads(cdir, 500) if not u["processed"]]
        rows.append({"cid": cid, "v": v, "uploads": len(ups), "requests": len(data.list_swms_requests(cdir, "Pending"))})
    order = {"RED": 0, "AMBER": 1, "GREEN": 2}
    rows.sort(key=lambda r: (order.get(r["v"].rag, 3) if "v" in r else -1, r["cid"]))
    return render_template("staff.html", rows=rows, active="staff")


@bp.route("/staff/inbox")
@auth.staff_required
def staff_inbox():
    out = []
    for cid, cdir in data.find_clients(current_app.config["CLIENTS_ROOT"]).items():
        for r in data.list_swms_requests(cdir, "Pending"):
            out.append({"cid": cid, "kind": "swms", "r": r})
        for u in data.list_uploads(cdir, 500):
            if not u["processed"]:
                out.append({"cid": cid, "kind": "upload", "r": u})
    out.sort(key=lambda x: x["r"].get("submitted_at") or x["r"].get("at"), reverse=True)
    return render_template("staff_inbox.html", items=out, active="inbox")


@bp.route("/staff/c/<client_id>/swms-request/<request_id>/accept", methods=["POST"])
@auth.staff_required
def staff_accept_request(client_id, request_id):
    cdir = data.client_dir(current_app.config["CLIENTS_ROOT"], client_id)
    if not cdir:
        abort(404)
    try:
        job_id = data.accept_swms_request(cdir, request_id, auth.current_user()["email"])
    except (ValueError, FileNotFoundError) as e:
        flash(f"Couldn't accept: {e}", "error")
        return redirect(url_for("portal.staff_inbox"))
    except PermissionError:
        flash("The register is locked (open in desktop Excel?). Close it and try again.", "error")
        return redirect(url_for("portal.staff_inbox"))
    auth.audit("swms_request_accepted", client_id, f"{request_id} -> {job_id}")
    flash(f"Added to {client_id}'s Jobs register as {job_id} (SWMS status: Requested).", "ok")
    return redirect(url_for("portal.staff_inbox"))


# ---------------------------------------------------------------------------
# Staff: SWMS generator
# ---------------------------------------------------------------------------

def _staff_client_dir(client_id):
    cdir = data.client_dir(current_app.config["CLIENTS_ROOT"], client_id)
    if not cdir:
        abort(404)
    return cdir


@bp.route("/staff/c/<client_id>/jobs/<job_id>/swms/draft", methods=["POST"])
@auth.staff_required
def staff_swms_draft(client_id, job_id):
    from swms.__main__ import SwmsError, draft
    cdir = _staff_client_dir(client_id)
    try:
        doc, pdf = draft(cdir, job_id, current_app.config.get("MASTER"), _today())
    except (SwmsError, KeyError) as e:
        flash(f"Couldn't draft the SWMS: {e}", "error")
    else:
        auth.audit("swms_draft", client_id, f"{job_id} v{doc.version}")
        flash(f"Draft v{doc.version} created for {job_id}: {len(doc.blockers)} blocker(s), "
              f"{len(doc.flags) - len(doc.blockers)} item(s) to check. Download it and review the checklist on the last page.",
              "error" if doc.blockers else "ok")
    return redirect(url_for("portal.jobs", client_id=client_id))


@bp.route("/staff/c/<client_id>/jobs/<job_id>/swms/issue", methods=["POST"])
@auth.staff_required
def staff_swms_issue(client_id, job_id):
    from swms.__main__ import SwmsError, issue
    cdir = _staff_client_dir(client_id)
    if request.form.get("confirm") != "yes":
        flash("Tick the box to confirm you've reviewed the draft before issuing.", "error")
        return redirect(url_for("portal.jobs", client_id=client_id))
    u = auth.current_user()
    try:
        doc, pdf = issue(cdir, job_id, u.get("name") or u["email"], current_app.config.get("MASTER"), today=_today())
    except (SwmsError, KeyError) as e:
        flash(str(e), "error")
    else:
        auth.audit("swms_issue", client_id, f"{job_id} v{doc.version}")
        flash(f"Issued {job_id} v{doc.version}. The client can now download it.", "ok")
    return redirect(url_for("portal.jobs", client_id=client_id))


@bp.route("/staff/c/<client_id>/jobs/<job_id>/swms/draft.pdf")
@auth.staff_required
def staff_swms_draft_pdf(client_id, job_id):
    cdir = _staff_client_dir(client_id)
    pdf = data.latest_draft(cdir, {"Job ID": job_id})
    if not pdf:
        abort(404)
    return send_file(pdf, as_attachment=True, download_name=pdf.name)
