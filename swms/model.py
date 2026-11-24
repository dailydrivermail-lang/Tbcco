"""Build a SWMS document model for one job from the client register and the SWMS library.

The model is plain data (dict-like dataclasses) so it can be saved as JSON next to the PDF,
edited by a reviewer if needed, and re-rendered.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml
from openpyxl import load_workbook

from engine import expiry_engine as ee
from engine import schema
from engine.register_io import parse_date, read_sheet

LIB = Path(__file__).resolve().parent / "library"
HIERARCHY = {"E": "Eliminate", "S": "Substitute", "I": "Isolate", "Eng": "Engineering", "A": "Administrative", "PPE": "PPE"}
HIER_ORDER = list(HIERARCHY)
RISK = {"X": "Extreme", "H": "High", "M": "Medium", "L": "Low"}
CRED_NAMES = {c[0]: c[1] for c in schema.CREDENTIAL_TYPES}
SUPERVISOR_ROLES = {"supervisor / foreman", "site manager", "director (on site)"}
NSW_CATEGORY_WORDS = {"plumbing": ("plumb", "water"), "drainage": ("drain",), "gas": ("gas", "lpg")}
ANY_ONE = {"GAS_TEST_ATMOS", "ELEC_RESTRICTED"}  # one competent person on the crew is enough
CHECK_ONLY = {"ELEC_RESTRICTED", "WORK_AT_HEIGHTS", "ACT_SILICA"}  # not definitive: flag as 'check', don't block


def load_library():
    hz = yaml.safe_load((LIB / "hazards.yaml").read_text(encoding="utf-8"))
    tk = yaml.safe_load((LIB / "tasks.yaml").read_text(encoding="utf-8"))
    return hz, tk


@dataclass
class Flag:
    severity: str  # blocker | check
    text: str


@dataclass
class CompetencyCheck:
    person_id: str
    name: str
    code: str
    label: str
    status: str      # OK | MISSING | EXPIRED | EXPIRES DURING JOB | NO EXPIRY
    detail: str = ""


@dataclass
class Step:
    n: int
    step: str
    hazards: list
    risk: str
    controls: list   # [[code, text], ...] sorted by hierarchy
    residual: str
    responsible: str
    source: str      # module or template id


@dataclass
class SwmsDoc:
    swms_no: str
    version: int
    status: str                      # DRAFT | ISSUED
    client_id: str
    business: dict
    job: dict
    state: str
    template: str
    modules: list
    hrcw: list                       # [[category, ticked bool]]
    workers: list                    # [{person_id, name, roles, first_aider}]
    competencies: list               # CompetencyCheck
    steps: list                      # Step
    ppe: list
    plant: str
    references: list
    emergency: dict
    flags: list                      # Flag
    prepared_at: str
    reviewed_by: str = ""
    issued_at: str = ""
    review_note: str = ""
    assessment: list = field(default_factory=list)   # [{label, answer, priority, unsure}] from the guided job assessment

    def to_json(self) -> dict:
        d = asdict(self)
        d["job"] = {k: (v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v) for k, v in self.job.items()}
        d["business"] = {k: (v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v) for k, v in self.business.items()}
        return d

    @classmethod
    def from_json(cls, d: dict) -> "SwmsDoc":
        d = dict(d)
        d["flags"] = [Flag(**f) for f in d.get("flags", [])]
        d["competencies"] = [CompetencyCheck(**c) for c in d.get("competencies", [])]
        d["steps"] = [Step(**st) for st in d.get("steps", [])]
        return cls(**d)

    @property
    def blockers(self) -> list:
        return [f for f in self.flags if f.severity == "blocker"]


HRCW_ALL = [
    "Work where there is a risk of a person falling more than 2 m",
    "Work on a telecommunication tower",
    "Demolition of an element of a structure that is load-bearing or related to physical integrity",
    "Work likely to involve disturbing asbestos",
    "Structural alterations or repairs that require temporary support",
    "Work in or near a confined space",
    "Work in or near a trench or shaft with an excavated depth greater than 1.5 m, or a tunnel",
    "Work involving the use of explosives",
    "Work on or near pressurised gas distribution mains or piping",
    "Work on or near chemical, fuel or refrigerant lines",
    "Work on or near energised electrical installations or services",
    "Work in an area that may have a contaminated or flammable atmosphere",
    "Work involving tilt-up or precast concrete elements",
    "Work on, in or adjacent to a road, railway, shipping lane or other traffic corridor in use",
    "Work in an area at a workplace in which there is any movement of powered mobile plant",
    "Work in an area in which there are artificial extremes of temperature",
    "Work in or near water or other liquid that involves a risk of drowning",
    "Work involving diving",
]
# module -> r 291 categories it ticks
HRCW_MAP = {
    "height": [0], "asbestos": [3], "confined": [5], "trench": [6], "gas": [8], "electrical": [10], "traffic": [13, 14],
}


def _roles(p) -> set[str]:
    return {r.strip().lower() for r in str(p.get("Roles") or "").split(";") if r.strip()}


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", str(s or "")).strip("-")[:40]


def job_folder(cdir: Path, job: dict) -> Path:
    existing = sorted((cdir / "04_Jobs").glob(f"{job['Job ID']}_*"))
    return existing[0] if existing else cdir / "04_Jobs" / f"{job['Job ID']}_{_slug(job.get('Site address'))}"


def load_job_assessment(cdir: Path, job: dict) -> dict | None:
    p = job_folder(cdir, job) / "assessment.json"
    if not p.exists():
        return None
    import json
    return json.loads(p.read_text(encoding="utf-8"))


def pick_template(scope: str, templates: list) -> dict:
    s = (scope or "").lower()
    for t in templates:
        if any(k in s for k in t["keywords"]):
            return t
    return next(t for t in templates if t["id"] == "general")


def resolve_workers(field_value: str, people: list) -> tuple[list, list]:
    """'P001; P003' or 'Sam Example, Jo' -> people rows; unresolved tokens returned separately."""
    tokens = [t.strip() for t in re.split(r"[;,\n]| and ", str(field_value or "")) if t.strip()]
    by_id = {str(p.get("Person ID")).upper(): p for p in people}
    out, missing = [], []
    for t in tokens:
        p = by_id.get(t.upper())
        if not p:
            hits = [x for x in people if t.lower() in str(x.get("Full name", "")).lower()]
            p = hits[0] if len(hits) == 1 else None
        if p is None:
            missing.append(t)
        elif p not in out:
            out.append(p)
    return out, missing


def _cred_status(creds: list, code: str, start: dt.date | None, end: dt.date | None) -> tuple[str, str]:
    mine = [c for c in creds if c.get("Credential type") == code]
    if not mine:
        return "MISSING", ""
    best = None
    for c in mine:
        if str(c.get("No expiry") or "").upper() == "Y":
            return "NO EXPIRY", str(c.get("Licence / card number") or "")
        exp = parse_date(c.get("Expiry date"))
        if exp and (best is None or exp > best[0]):
            best = (exp, str(c.get("Licence / card number") or ""))
    if best is None:
        return "MISSING", "expiry date not on file"
    exp, num = best
    ref = start or dt.date.today()
    if exp < ref:
        return "EXPIRED", f"{num}, expired {exp:%d/%m/%Y}"
    if end and exp < end:
        return "EXPIRES DURING JOB", f"{num}, expires {exp:%d/%m/%Y}"
    return "OK", f"{num}, to {exp:%d/%m/%Y}"


def build(cdir: Path, job_id: str, today: dt.date | None = None) -> SwmsDoc:
    today = today or dt.date.today()
    hz, tk = load_library()
    wb = load_workbook(ee.find_register(cdir))
    business = (read_sheet(wb, "Business") or [{}])[0]
    people = read_sheet(wb, "People")
    creds = read_sheet(wb, "Credentials")
    jobs = read_sheet(wb, "Jobs")
    job = next((j for j in jobs if str(j.get("Job ID")) == job_id), None)
    if not job:
        raise KeyError(f"Job {job_id} not found in the Jobs sheet")
    flags: list[Flag] = []
    state = str(job.get("State") or "").upper() or "ACT"
    start, end = parse_date(job.get("Start date")), parse_date(job.get("End date"))
    for f, label in (("Site address", "site address"), ("Scope of work", "scope of work"), ("Start date", "start date")):
        if not job.get(f):
            flags.append(Flag("blocker", f"Job has no {label}."))
    if state not in ("ACT", "NSW"):
        flags.append(Flag("blocker", f"State '{state}' isn't covered by the v1 library (ACT, NSW)."))

    # modules
    # guided job assessment, if the request came through the portal
    assess, derived = load_job_assessment(cdir, job), None
    if assess:
        from swms import assessment as _a
        derived = _a.evaluate({"job_type": assess.get("job_type"), "state": state,
                               "building_age": (assess.get("site") or {}).get("building_age"), **(assess.get("answers") or {})})
    ticked_cols = {k for k, m in hz.items() if k != "base" and str(job.get(m.get("job_column"), "")).upper() == "Y"}
    if derived:
        ticked_cols |= set(derived["hazards"])
    modules = ["base"] + [k for k in hz if k in ticked_cols]
    template = pick_template(job.get("Scope of work"), tk["templates"])
    if derived and derived["template"]:
        template = next(t for t in tk["templates"] if t["id"] == derived["template"])
    extra_controls: dict[str, list] = {}
    need_codes: dict[str, str] = {}
    if derived:
        for c in derived["controls"]:
            extra_controls.setdefault(c["step"], []).append([c["h"], c["text"]])
        need_codes = {n["code"]: n["who"] for n in derived["needs"]}
        for t in derived["stops"]:
            flags.append(Flag("blocker", f"[Job assessment] STOP: {t}"))
        for t in derived["blockers"]:
            flags.append(Flag("blocker", f"[Job assessment] {t}"))
        for t in derived["checks"]:
            flags.append(Flag("check", f"[Job assessment] {t}"))
        if derived["missing"]:
            flags.append(Flag("blocker", f"[Job assessment] {len(derived['missing'])} question(s) unanswered. Re-open the assessment and complete it."))
    if template["id"] == "general":
        flags.append(Flag("check", "Scope didn't match a specific task template. General plumbing steps were used; tailor them to the job."))

    # workers
    workers, unresolved = resolve_workers(job.get("Workers assigned (Person IDs)"), people)
    if not workers:
        flags.append(Flag("blocker", "No workers assigned (Jobs > 'Workers assigned'). Competencies can't be checked."))
    for t in unresolved:
        flags.append(Flag("blocker", f"Assigned worker '{t}' isn't on the People sheet."))
    pcreds = {str(p.get("Person ID")): [c for c in creds if str(c.get("Person ID")) == str(p.get("Person ID"))] for p in workers}

    # competencies
    checks: list[CompetencyCheck] = []
    required = []
    for m in modules:
        for c in hz[m].get("competencies", []) or []:
            if c["scope"] in ("ALL", state) and c["code"] not in [r["code"] for r in required]:
                if derived and c["code"] == "ELEC_RESTRICTED" and c["code"] not in need_codes:
                    continue  # the assessment already says who does the electrical work
                required.append(c)
    for code, who in need_codes.items():
        if code not in [r["code"] for r in required]:
            required.append({"code": code, "scope": "ALL", "note": "Required by the job assessment answers"})
    any_one = set(ANY_ONE) | {c for c, who in need_codes.items() if who == "any"}
    for req in required:
        code = req["code"]
        rows = []
        for p in workers:
            stt, det = _cred_status(pcreds[str(p["Person ID"])], code, start, end)
            rows.append(CompetencyCheck(str(p["Person ID"]), p.get("Full name", ""), code, CRED_NAMES.get(code, code), stt, det))
        ok = [r for r in rows if r.status in ("OK", "NO EXPIRY")]
        if code in any_one:
            checks += ok[:1] or rows[:1]
            if not ok and workers:
                flags.append(Flag("blocker" if code in need_codes else "check", f"No assigned worker has {CRED_NAMES.get(code, code)}. {req.get('note', '')}".strip()))
            continue
        checks += rows
        for r in rows:
            if r.status not in ("OK", "NO EXPIRY"):
                sev = "check" if (code in CHECK_ONLY and code not in need_codes) or r.status == "EXPIRES DURING JOB" else "blocker"
                flags.append(Flag(sev, f"{r.name}: {r.label}: {r.status.lower()}{' (' + r.detail + ')' if r.detail else ''}."))

    # trade licences (team level)
    trades = set(template.get("licence", [])) | ({"gas"} if "gas" in modules else set()) | set(derived["licences"] if derived else [])
    licensed_people = []
    for trade in sorted(trades):
        codes = tk["licences"][trade].get(state, [])
        holders = []
        for p in workers:
            for code in codes:
                stt, det = _cred_status(pcreds[str(p["Person ID"])], code, start, end)
                if stt == "MISSING":
                    continue
                if code.startswith("NSW_"):
                    cats = " ".join(str(c.get("Class / categories") or "") for c in pcreds[str(p["Person ID"])]
                                    if c.get("Credential type") == code).lower()
                    if not cats.strip():
                        flags.append(Flag("check", f"{p.get('Full name')}: NSW licence categories aren't recorded. "
                                                   f"Confirm it covers {trade} and record the categories on the Credentials sheet."))
                        continue
                    if not any(k in cats for k in NSW_CATEGORY_WORDS[trade]):
                        continue
                checks.append(CompetencyCheck(str(p["Person ID"]), p.get("Full name", ""), code,
                                              f"{trade.title()} licence: {CRED_NAMES.get(code, code)}", stt, det))
                if stt in ("OK", "NO EXPIRY", "EXPIRES DURING JOB") and p not in holders:
                    holders.append(p)
        if state == "NSW" and not holders:
            act_only = [p for p in workers if any(c.get("Credential type") == tk["licences"][trade]["ACT"][0]
                                                  for c in pcreds[str(p["Person ID"])])]
            for p in act_only:
                flags.append(Flag("check", f"{p.get('Full name')} holds an ACT {trade} licence only. Check whether automatic "
                                           "mutual recognition covers this NSW work (rules P-NSW-01/02/03, pending legal review)."))
        if workers and not holders:
            flags.append(Flag("blocker", f"No assigned worker holds a current {state} {trade} licence ({' / '.join(codes)}). "
                                         "Licensed work must be done or supervised by a licensee."))
        licensed_people += [h for h in holders if h not in licensed_people]

    # plant-triggered licences
    plant = str(job.get("Plant and equipment") or "")
    pl = plant.lower()
    if "forklift" in pl:
        if not any(_cred_status(pcreds[str(p["Person ID"])], "HRWL_LF", start, end)[0] == "OK" for p in workers):
            flags.append(Flag("blocker", "Forklift listed but no assigned worker holds a current HRWL class LF."))
    if any(k in pl for k in ("ewp", "boom", "cherry picker", "knuckle")):
        flags.append(Flag("check", "EWP listed: if it's a boom type with a boom of 11 m or more, the operator needs HRWL class WP."))
    if any(k in pl for k in ("excavator", "backhoe", "skid steer", "bobcat")):
        flags.append(Flag("check", "Earthmoving plant listed: confirm the operator's competency (VOC or ticket) and that the plant pre-start check is done."))

    # responsible persons
    sup = next((p for p in workers if _roles(p) & SUPERVISOR_ROLES), None) or (licensed_people[0] if licensed_people else None)
    if not sup and workers:
        flags.append(Flag("check", "No supervisor identified among assigned workers. Name the person in charge on site."))

    def who(tag):
        if tag == "supervisor":
            return f"{sup['Full name']} (supervisor)" if sup else "Supervisor (to confirm)"
        if tag == "licensed":
            return ", ".join(p["Full name"] for p in licensed_people) + " (licensee)" if licensed_people else "Licensee (to confirm)"
        return "All workers"

    # steps: first -> early -> template steps with middle modules inserted -> late -> any -> last
    buckets = {"first": [], "early": [], "middle": [], "late": [], "any": [], "last": []}
    for m in modules:
        for s in hz[m]["steps"]:
            buckets[s["position"]].append((m, s))
    tsteps = [(template["id"], s) for s in template["steps"]]
    cut = template.get("middle_after", 1)
    ordered = buckets["first"] + buckets["early"] + tsteps[:cut] + buckets["middle"] + tsteps[cut:] + buckets["late"] + buckets["any"] + buckets["last"]
    steps = []
    for i, (src, s) in enumerate(ordered, start=1):
        ctr = sorted(list(s["controls"]) + extra_controls.get(s.get("id"), []), key=lambda c: HIER_ORDER.index(c[0]))
        steps.append(Step(i, s["step"], s["hazards"], s["risk"], ctr, s["residual"], who(s["responsible"]), src))

    # hrcw ticks
    ticked = {i for m in modules for i in HRCW_MAP.get(m, [])} | set(derived["hrcw"] if derived else [])
    hrcw = [[c, i in ticked] for i, c in enumerate(HRCW_ALL)]
    if not ticked:
        flags.append(Flag("check", "No high-risk construction work category is ticked. A SWMS may not be legally required, "
                                   "but the client or head contractor may still want one."))

    ppe = []
    for m in modules:
        for p in hz[m].get("ppe", []):
            if p not in ppe:
                ppe.append(p)
    refs = []
    for m in modules:
        for r in hz[m].get("references", []):
            if r not in refs:
                refs.append(r)
    refs += ["Work Health and Safety Act 2011 and Regulation (ACT: 2011; NSW: 2025). SWMS requirements: r 291 and r 299-303"]
    for m in modules:
        for f in hz[m].get("review_flags", []) or []:
            flags.append(Flag("check", f"[{hz[m]['title']}] {f}"))

    first_aiders = [p["Full name"] for p in workers if str(p.get("Designated first aider") or "").upper() == "Y"]
    if workers and not first_aiders:
        flags.append(Flag("check", "No designated first aider among assigned workers. Confirm first aid arrangements on site."))
    emergency = {
        "call": "Emergency: 000 (ask for ambulance, fire or police)",
        "regulator": tk["emergency"].get(state, {}).get("regulator", ""),
        "first_aiders": first_aiders,
        "site_fields": ["Nearest hospital / medical centre", "Assembly point", "First aid kit location", "Fire extinguisher location"],
    }
    if job.get("Est. value ($)") and float(job.get("Est. value ($)") or 0) >= 250000:
        flags.append(Flag("check", "Job value is $250k or more: the principal contractor needs a WHS management plan (r 309). Confirm who that is."))

    existing = sorted(job_folder(cdir, job).glob("Drafts/*_SWMS_v*_DRAFT.pdf"))
    version = 1 + max([int(re.search(r"_v(\d+)_", p.name).group(1)) for p in existing] or [0])
    return SwmsDoc(
        swms_no=f"{business.get('Client ID', '')}-{job_id}-SWMS", version=version, status="DRAFT",
        client_id=str(business.get("Client ID", "")), business=business, job=job, state=state,
        template=template["title"], modules=[hz[m]["title"] for m in modules], hrcw=hrcw,
        workers=[{"person_id": str(p["Person ID"]), "name": p.get("Full name", ""), "roles": p.get("Roles", ""),
                  "first_aider": str(p.get("Designated first aider") or "").upper() == "Y"} for p in workers],
        competencies=checks, steps=steps, ppe=ppe, plant=plant, references=refs, emergency=emergency, flags=flags,
        prepared_at=dt.datetime.now().isoformat(timespec="minutes"),
        assessment=([{"label": d["label"], "answer": d["answer"], "priority": d["priority"], "unsure": d["unsure"]}
                     for d in derived["details"]] if derived else []))
