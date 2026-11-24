"""Users, login, CSRF and the portal audit log.

Users live in <DATA_DIR>/users.json and are managed with `python -m portal.manage`.
Roles: 'client' (sees only their own client_id) and 'staff' (sees every client).
"""
from __future__ import annotations

import csv
import datetime as dt
import functools
import hmac
import json
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path

from flask import abort, current_app, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

_lock = threading.Lock()
_failures: dict[str, list[float]] = {}
FAIL_WINDOW_S, FAIL_LIMIT = 15 * 60, 8
MIN_PASSWORD_LEN = 12


# ---------------------------------------------------------------------------
# User store
# ---------------------------------------------------------------------------

def users_path(data_dir: Path) -> Path:
    return Path(data_dir) / "users.json"


def load_users(data_dir: Path) -> list[dict]:
    p = users_path(data_dir)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("users", [])


def save_users(data_dir: Path, users: list[dict]):
    p = users_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"users": users}, f, indent=2, default=str)
        os.replace(tmp, p)


def find_user(data_dir: Path, email: str) -> dict | None:
    email = (email or "").strip().lower()
    return next((u for u in load_users(data_dir) if u["email"] == email), None)


def upsert_user(data_dir: Path, email: str, *, name: str = "", role: str = "client", client_id: str | None = None,
                password: str | None = None, active: bool = True) -> dict:
    if role not in ("client", "staff"):
        raise ValueError("role must be client or staff")
    if role == "client" and not client_id:
        raise ValueError("client users need a client_id")
    if password is not None and len(password) < MIN_PASSWORD_LEN:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LEN} characters")
    users = load_users(data_dir)
    email = email.strip().lower()
    u = next((x for x in users if x["email"] == email), None)
    if u is None:
        u = {"email": email, "created": dt.datetime.now().isoformat(timespec="seconds")}
        users.append(u)
    u.update({"name": name or u.get("name", ""), "role": role, "client_id": client_id if role == "client" else None,
              "active": active})
    if password is not None:
        u["password_hash"] = generate_password_hash(password)
    save_users(data_dir, users)
    return u


def check_login(data_dir: Path, email: str, password: str) -> dict | None:
    u = find_user(data_dir, email)
    if not u or not u.get("active") or not u.get("password_hash"):
        # constant-ish time: still run a hash check
        check_password_hash(generate_password_hash("x"), password or "")
        return None
    return u if check_password_hash(u["password_hash"], password or "") else None


# ---------------------------------------------------------------------------
# Throttling
# ---------------------------------------------------------------------------

def _key() -> str:
    return request.remote_addr or "?"


def throttled() -> bool:
    now = time.time()
    hits = [t for t in _failures.get(_key(), []) if now - t < FAIL_WINDOW_S]
    _failures[_key()] = hits
    return len(hits) >= FAIL_LIMIT


def record_failure():
    _failures.setdefault(_key(), []).append(time.time())


def reset_throttle():
    _failures.clear()


# ---------------------------------------------------------------------------
# Session helpers / decorators
# ---------------------------------------------------------------------------

def current_user() -> dict | None:
    if "user" not in g:
        email = session.get("email")
        u = find_user(current_app.config["DATA_DIR"], email) if email else None
        g.user = u if u and u.get("active") else None
    return g.user


def login_required(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            return redirect(url_for("portal.login", next=request.path))
        return fn(*a, **kw)
    return wrapper


def staff_required(fn):
    @functools.wraps(fn)
    @login_required
    def wrapper(*a, **kw):
        if current_user()["role"] != "staff":
            abort(403)
        return fn(*a, **kw)
    return wrapper


def can_view(client_id: str) -> bool:
    u = current_user()
    return bool(u) and (u["role"] == "staff" or u.get("client_id") == client_id)


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        if not sent or not hmac.compare_digest(sent, session.get("csrf", "")):
            abort(400, "Your session expired. Go back, refresh the page and try again.")


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

AUDIT_FIELDS = ["timestamp", "user", "role", "client_id", "action", "detail", "ip"]


def audit(action: str, client_id: str = "", detail: str = ""):
    p = Path(current_app.config["DATA_DIR"]) / "portal_audit.csv"
    u = current_user() or {}
    new = not p.exists()
    with _lock, open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        if new:
            w.writeheader()
        w.writerow({"timestamp": dt.datetime.now().isoformat(timespec="seconds"),
                    "user": u.get("email", session.get("email", "")), "role": u.get("role", ""),
                    "client_id": client_id, "action": action, "detail": detail[:300], "ip": request.remote_addr})
