"""Manage portal users.

    python -m portal.manage add --email pat@abcplumbing.com.au --client C001 --name "Pat Owner"
    python -m portal.manage add --email steve@ourfirm.com.au --role staff --name Steve
    python -m portal.manage reset --email pat@abcplumbing.com.au
    python -m portal.manage disable --email pat@abcplumbing.com.au
    python -m portal.manage list

Uses PORTAL_DATA_DIR (or PORTAL_CLIENTS_ROOT/../04_Ops/portal). New and reset accounts get a
random temporary password, printed once. Send it to the person by a different channel from
the login link (e.g. SMS the password, email the link).
"""
from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path

from portal import auth


def data_dir() -> Path:
    d = os.environ.get("PORTAL_DATA_DIR")
    if d:
        return Path(d).expanduser()
    root = os.environ.get("PORTAL_CLIENTS_ROOT")
    if not root:
        raise SystemExit("Set PORTAL_DATA_DIR or PORTAL_CLIENTS_ROOT")
    p = Path(root).expanduser().parent / "04_Ops" / "portal"
    p.mkdir(parents=True, exist_ok=True)
    return p


def temp_password() -> str:
    return "-".join(secrets.token_urlsafe(4) for _ in range(4))  # ~22 chars, readable over the phone


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--email", required=True)
    a.add_argument("--name", default="")
    a.add_argument("--role", choices=["client", "staff"], default="client")
    a.add_argument("--client")
    for c in ("reset", "disable", "enable"):
        sub.add_parser(c).add_argument("--email", required=True)
    sub.add_parser("list")
    args = ap.parse_args(argv)
    d = data_dir()
    if args.cmd == "add":
        pw = temp_password()
        u = auth.upsert_user(d, args.email, name=args.name, role=args.role, client_id=args.client, password=pw)
        print(f"Created {u['email']} ({u['role']}{' ' + u['client_id'] if u.get('client_id') else ''})")
        print(f"Temporary password: {pw}")
    elif args.cmd in ("reset", "disable", "enable"):
        u = auth.find_user(d, args.email)
        if not u:
            raise SystemExit("No such user")
        pw = temp_password() if args.cmd == "reset" else None
        auth.upsert_user(d, u["email"], name=u.get("name", ""), role=u["role"], client_id=u.get("client_id"),
                         password=pw, active=args.cmd != "disable")
        print(f"{args.cmd}: {u['email']}" + (f"\nTemporary password: {pw}" if pw else ""))
    else:
        for u in auth.load_users(d):
            print(f"{u['email']:40} {u['role']:7} {u.get('client_id') or '':6} {'active' if u.get('active') else 'DISABLED'}")


if __name__ == "__main__":
    main()
