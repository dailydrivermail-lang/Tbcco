"""Serve the portal.

    # real data (ops PC): binds to localhost only
    PORTAL_CLIENTS_ROOT="~/OneDrive - Firm/Compliance Ops/01_Clients" python -m portal.run

    # fictional demo data with demo logins
    python -m portal.run --demo

Waitress is a production-grade WSGI server that works on Windows. Clients can't reach a
localhost app: for client access, deploy to Azure App Service (Australia East) behind HTTPS
with PORTAL_SECURE_COOKIES=1 (see docs/05-client-portal.md).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEMO_USERS = [  # fictional, demo data only
    ("pat@example.com", "Pat Owner", "client", "C000", "demo-client-password"),
    ("staff@example.com", "Demo Staff", "staff", None, "demo-staff-password"),
]


def setup_demo() -> dict:
    sys.path.insert(0, str(ROOT))
    import examples.make_demo as md
    from portal import auth
    md.main([])
    data = md.OUT / "_portal"
    for email, name, role, cid, pw in DEMO_USERS:
        auth.upsert_user(data, email, name=name, role=role, client_id=cid, password=pw)
    return {"CLIENTS_ROOT": str(md.OUT), "DATA_DIR": str(data), "TODAY": md.DEMO_TODAY}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--demo", action="store_true", help="rebuild the fictional demo client and serve it")
    a = ap.parse_args(argv)
    from portal import create_app
    overrides = setup_demo() if a.demo else None
    app = create_app(overrides)
    if a.host not in ("127.0.0.1", "localhost") and not os.environ.get("PORTAL_SECURE_COOKIES"):
        print("WARNING: serving beyond localhost without HTTPS. Put it behind TLS and set PORTAL_SECURE_COOKIES=1.")
    if a.demo:
        print("Demo logins:")
        for email, _, role, _, pw in DEMO_USERS:
            print(f"  {role:6} {email} / {pw}")
    print(f"Portal on http://{a.host}:{a.port}")
    from waitress import serve
    serve(app, host=a.host, port=a.port)


if __name__ == "__main__":
    main()
