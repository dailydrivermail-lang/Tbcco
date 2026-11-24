"""Build the tradie-facing SWMS assistant prototype (front end only, fictional crew) as one HTML page.

    python prototype/build_swms_app.py [--out FILE]

It reuses the production question tree (swms/library/assessment.yaml), hazard and task libraries and the
shared evaluation engine, so the prototype asks exactly what the real assessment asks.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from swms import assessment, model  # noqa: E402

PEOPLE = [  # fictional demo crew; expiry offsets in days from today, None = no expiry
    {"id": "P001", "name": "Sam Example", "roles": "Licensed plumber, drainer, gasfitter · Supervisor",
     "creds": {"ACT_PLUMBER": 400, "ACT_DRAINER": 300, "ACT_GASFITTER": 400, "WHITE_CARD": None, "ACT_ASB_AWARE": None,
               "ACT_SILICA": None, "NSW_CONTRACTOR_PDG": 200}},
    {"id": "P002", "name": "Alex Sample", "roles": "Apprentice", "creds": {"WHITE_CARD": None, "ACT_ASB_AWARE": None}},
    {"id": "P003", "name": "Jo Placeholder", "roles": "Drainer · Plant operator",
     "creds": {"NSW_TRADE_PDG": 55, "WHITE_CARD": None, "HRWL_LF": 900, "WORK_AT_HEIGHTS": -20}},
]


def boot() -> dict:
    hz, tk = model.load_library()
    spec = assessment.client_spec()
    codes = {c["code"] for m in hz.values() for c in (m.get("competencies") or [])}
    codes |= {e["need"]["code"] for q in spec["questions"] for e in q["effects"] if "need" in e}
    from engine import expiry_engine as ee
    return {
        "spec": spec, "people": PEOPLE,
        "hz": {k: {"title": m["title"], "hrcw": m.get("hrcw"), "ppe": m.get("ppe") or [], "steps": m["steps"],
                   "competencies": m.get("competencies") or []} for k, m in hz.items()},
        "templates": {t["id"]: {"title": t["title"], "steps": t["steps"], "middle_after": t["middle_after"],
                                "licence": t.get("licence", [])} for t in tk["templates"]},
        "licences": tk["licences"], "hrcw_all": model.HRCW_ALL, "hierarchy": model.HIERARCHY, "risk": model.RISK,
        "any_one": sorted(model.ANY_ONE), "optional": ["ELEC_RESTRICTED"], "cred_names": {c: ee.short_label(c) for c in codes},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "prototype" / "swms-assistant.html")
    a = ap.parse_args()
    tpl = (ROOT / "prototype" / "swms_app.template.html").read_text(encoding="utf-8")
    engine = (ROOT / "portal" / "static" / "js" / "assessment-engine.js").read_text(encoding="utf-8")
    data = json.dumps(boot()).replace("<", "\\u003c")
    out = tpl.replace("/*__ENGINE__*/", engine).replace("__BOOT__", data)
    a.out.write_text(out, encoding="utf-8")
    print(f"{a.out}: {a.out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
