"""Portal configuration, all from environment variables so the same code runs on the
ops PC now and on Azure (Australia East) later.

  PORTAL_CLIENTS_ROOT   folder holding one subfolder per client (SharePoint 01_Clients, synced)
  PORTAL_DATA_DIR       portal's own data: users.json, audit log, secret key
                        (default: <CLIENTS_ROOT>/../04_Ops/portal)
  PORTAL_SECRET_KEY     session signing key (default: generated once into PORTAL_DATA_DIR/secret_key)
  PORTAL_SECURE_COOKIES 1 when served over HTTPS (always in production)
  PORTAL_SHOW_UNREVIEWED_RULE_GAPS
                        0 (default): clients only see "missing" items from rules Ivana has verified.
                        Staff always see all of them, labelled.
  PORTAL_TODAY          YYYY-MM-DD override for demos and tests
"""
from __future__ import annotations

import datetime as dt
import os
import secrets
from pathlib import Path

ALLOWED_UPLOAD_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".heif", ".docx", ".xlsx", ".doc", ".xls"}
MAX_UPLOAD_MB = 25


def _flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def load(overrides: dict | None = None) -> dict:
    o = overrides or {}
    root = Path(o.get("CLIENTS_ROOT") or os.environ.get("PORTAL_CLIENTS_ROOT", "")).expanduser()
    if not str(root) or not root.is_dir():
        raise SystemExit(f"PORTAL_CLIENTS_ROOT is not a folder: '{root}'")
    data = Path(o.get("DATA_DIR") or os.environ.get("PORTAL_DATA_DIR") or (root.parent / "04_Ops" / "portal")).expanduser()
    data.mkdir(parents=True, exist_ok=True)
    key = o.get("SECRET_KEY") or os.environ.get("PORTAL_SECRET_KEY")
    if not key:
        kf = data / "secret_key"
        if not kf.exists():
            kf.write_text(secrets.token_hex(32))
            try:
                kf.chmod(0o600)
            except OSError:
                pass
        key = kf.read_text().strip()
    today = o.get("TODAY") or os.environ.get("PORTAL_TODAY")
    secure = o.get("SECURE_COOKIES", _flag("PORTAL_SECURE_COOKIES"))
    return {
        "CLIENTS_ROOT": root.resolve(),
        "DATA_DIR": data.resolve(),
        "SECRET_KEY": key,
        "TODAY": dt.date.fromisoformat(today) if isinstance(today, str) else today,
        "SHOW_UNREVIEWED_RULE_GAPS": o.get("SHOW_UNREVIEWED_RULE_GAPS", _flag("PORTAL_SHOW_UNREVIEWED_RULE_GAPS")),
        "MAX_CONTENT_LENGTH": MAX_UPLOAD_MB * 1024 * 1024,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": bool(secure),
        "PERMANENT_SESSION_LIFETIME": dt.timedelta(hours=8),
        "TESTING": o.get("TESTING", False),
    }
