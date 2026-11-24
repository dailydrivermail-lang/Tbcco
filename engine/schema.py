"""Single source of truth for the client data model.

Every register (sheet) in a client's register workbook is defined here.
build_templates.py turns this into:
  - templates/Client_Register_TEMPLATE.xlsx
  - docs/02-data-model.md
so the workbook, the docs and the engine never drift apart.

Column spec keys:
  name      header text (the engine reads columns by this name)
  desc      what goes in it (also written as a header comment)
  type      text | date | datetime | int | money | bool | link | formula | list
  list      name of a lookup list in LOOKUPS (adds an Excel dropdown)
  formula   Excel formula with {r} for the row number (computed columns)
  req       True if intake must capture it
  width     column width in Excel
"""

# ---------------------------------------------------------------------------
# Controlled vocabularies (Lookups sheet + dropdowns)
# Credential and insurance codes are shared with rules/rules_library.csv.
# ---------------------------------------------------------------------------

CREDENTIAL_TYPES = [
    # code, display name, issuer/regulator, typical validity (years, '' = no expiry / varies)
    ("ACT_PLUMBER", "ACT plumber licence (class as listed)", "Access Canberra (Construction Occupations Registrar)", "verify"),
    ("ACT_DRAINER", "ACT drainer licence (advanced sanitary / journeyperson / operative)", "Access Canberra", "verify"),
    ("ACT_GASFITTER", "ACT gasfitter licence (general / advanced / LPG / other class)", "Access Canberra", "verify"),
    ("ACT_GAS_APPLIANCE", "ACT gas appliance worker licence", "Access Canberra", "verify"),
    ("ACT_BACKFLOW_END", "ACT backflow prevention testing endorsement", "Access Canberra", "verify"),
    ("NSW_CONTRACTOR_PDG", "NSW contractor licence - plumbing/draining/gasfitting", "Building Commission NSW", "1-5"),
    ("NSW_QS_PDG", "NSW qualified supervisor certificate - plumbing/draining/gasfitting", "Building Commission NSW", "1-5"),
    ("NSW_TRADE_PDG", "NSW tradesperson certificate - plumbing/draining/gasfitting", "Building Commission NSW", "1-5"),
    ("WHITE_CARD", "General construction induction (White Card, CPCWHS1001)", "WHS regulator (any state)", ""),
    ("ACT_ASB_AWARE", "Asbestos awareness - 11084NAT (ACT mandatory)", "Approved RTO", ""),
    ("ACT_SILICA", "Crystalline silica exposure prevention - 10830NAT (ACT mandatory)", "Approved RTO", ""),
    ("ACT_ASB_ACM", "Working safely with asbestos-containing materials (ACT, specified occupations)", "Approved RTO", ""),
    ("HRWL_WP", "High risk work licence - boom-type EWP 11m+ (WP)", "WHS regulator", "5"),
    ("HRWL_LF", "High risk work licence - forklift (LF)", "WHS regulator", "5"),
    ("HRWL_SB", "High risk work licence - basic scaffolding (SB)", "WHS regulator", "5"),
    ("HRWL_DG", "High risk work licence - dogging (DG)", "WHS regulator", "5"),
    ("HRWL_OTHER", "High risk work licence - other class (specify)", "WHS regulator", "5"),
    ("FIRST_AID", "Provide first aid (HLTAID011)", "RTO", "3"),
    ("CPR", "Provide CPR (HLTAID009)", "RTO", "1"),
    ("CONFINED_SPACE", "Enter and work in confined spaces (e.g. RIIWHS202E)", "RTO", "verify"),
    ("WORK_AT_HEIGHTS", "Work safely at heights (e.g. RIIWHS204E)", "RTO", "verify"),
    ("GAS_TEST_ATMOS", "Gas test atmospheres (e.g. MSMWHS217)", "RTO", "verify"),
    ("ARCTICK_RHL", "ARCtick refrigerant handling licence", "Australian Refrigeration Council", "verify"),
    ("ELEC_RESTRICTED", "Restricted electrical licence (disconnect/reconnect)", "State licensing body", "verify"),
    ("TEST_TAG", "Test and tag competency", "RTO", "verify"),
    ("EWP_YELLOW", "EWP under 11m operator training (IPAF/EWPA yellow card)", "Industry", "5"),
    ("DRIVER_LICENCE", "Driver licence", "State road authority", "varies"),
    ("OTHER", "Other (describe in notes)", "", ""),
]

INSURANCE_TYPES = [
    ("PL", "Public and products liability"),
    ("WC_ACT", "Workers' compensation - ACT"),
    ("WC_NSW", "Workers' compensation - NSW (icare)"),
    ("PI", "Professional indemnity"),
    ("CONTRACT_WORKS", "Contract works / construction risk"),
    ("MOTOR", "Commercial motor vehicle"),
    ("TOOLS", "Tools and equipment"),
    ("PERSONAL_ACCIDENT", "Personal accident / sickness (sole-trader subbie)"),
    ("HBCF", "NSW Home Building Compensation Fund certificate"),
    ("NSW_SUBBIE_STMT", "NSW subcontractor statement (s 175B WC Act 1987)"),
    ("OTHER", "Other (describe in notes)"),
]

ROLES = [
    "Licensed plumber", "Drainer", "Gasfitter", "Apprentice", "Labourer",
    "Supervisor / foreman", "Site manager", "Director (on site)", "Office (non-site)",
    "Plant operator", "Other",
]

LOOKUPS = {
    "credential_codes": [c[0] for c in CREDENTIAL_TYPES],
    "insurance_codes": [c[0] for c in INSURANCE_TYPES],
    "roles": ROLES,
    "person_type": ["Employee", "Apprentice", "Subcontractor (individual)", "Subcontractor worker", "Labour hire"],
    "yes_no": ["Y", "N"],
    "state": ["ACT", "NSW", "ACT;NSW", "Other"],
    "alert_channel": ["Email", "SMS", "Email+SMS", "Client only"],
    "holder_type": ["Client", "Subcontractor"],
    "intake_source": ["Onboarding form", "Upload folder", "Email inbox", "Phone", "Public register check", "Other"],
    "extracted_by": ["Claude", "Human"],
    "verify_status": ["Unverified", "Verified - document", "Verified - public register", "Rejected"],
    "incident_type": ["Injury", "Near miss", "Dangerous incident", "Property damage", "Environmental", "Other"],
    "open_closed": ["Open", "Closed"],
    "plant_kind": ["Portable electrical", "Plant", "Vehicle", "Lifting gear", "Gas detector", "Other"],
    "doc_category": ["Policy", "Procedure", "SWMS", "Form", "Certificate", "Plan", "Other"],
    "swms_status": ["Not required", "Requested", "Drafting", "In review", "Issued", "Superseded"],
}

# ---------------------------------------------------------------------------
# Shared formula fragments
# ---------------------------------------------------------------------------

def _days(col):
    return f'=IF({col}{{r}}="","",{col}{{r}}-TODAY())'


def _status(days_col, noexp_col=None, date_col=None):
    """Expiry status: same buckets as engine/expiry_engine.py."""
    no_exp = f'{noexp_col}{{r}}="Y",' if noexp_col else ""
    no_exp_open = f'IF({no_exp}"NO EXPIRY",' if noexp_col else ""
    close = ")" if noexp_col else ""
    return (
        f'={no_exp_open}IF({date_col}{{r}}="","MISSING DATE",'
        f'IF({days_col}{{r}}<0,"EXPIRED",IF({days_col}{{r}}<=7,"DUE 7",'
        f'IF({days_col}{{r}}<=30,"DUE 30",IF({days_col}{{r}}<=60,"DUE 60","CURRENT"))))){close}'
    )


# ---------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------

REGISTERS = [
    {
        "sheet": "Business",
        "purpose": "One row per client business. Key facts the engine and reports pull from.",
        "id_prefix": None,
        "columns": [
            {"name": "Client ID", "type": "text", "req": True, "desc": "Our ID, e.g. C001. Matches the folder name."},
            {"name": "Legal name", "type": "text", "req": True, "desc": "Entity name as on the ABR."},
            {"name": "Trading name", "type": "text", "desc": "If different."},
            {"name": "ABN", "type": "text", "req": True, "desc": "11 digits, no spaces."},
            {"name": "Entity type", "type": "text", "desc": "Company / trust / partnership / sole trader."},
            {"name": "Trades", "type": "text", "req": True, "desc": "Semicolon list: Plumbing; Drainage; Gasfitting; Roof plumbing; Backflow; Fire services; HVAC."},
            {"name": "States operated", "type": "list", "list": "state", "req": True, "desc": "ACT, NSW, or both."},
            {"name": "Business licence numbers", "type": "text", "desc": "ACT corporate licence / NSW contractor licence numbers (details go on the Credentials sheet against the nominee)."},
            {"name": "Employees (FTE)", "type": "int", "desc": "Headcount used for first-aid ratios and tier fit."},
            {"name": "Regular subcontractors", "type": "int", "desc": "Count."},
            {"name": "Head contractors worked for", "type": "text", "desc": "Semicolon list. Their prequalification requirements are captured in the gap analysis (Phase 2)."},
            {"name": "Residential / commercial mix", "type": "text", "desc": "e.g. 60% residential."},
            {"name": "Insurer", "type": "text", "desc": "Main liability insurer."},
            {"name": "Broker", "type": "text", "desc": "Broker firm and contact."},
            {"name": "Broker email", "type": "text"},
            {"name": "Primary contact", "type": "text", "req": True, "desc": "Person who receives alerts and the monthly summary."},
            {"name": "Primary contact email", "type": "text", "req": True},
            {"name": "Primary contact mobile", "type": "text", "req": True},
            {"name": "Safety contact (if different)", "type": "text"},
            {"name": "Safety contact email", "type": "text"},
            {"name": "Xero connected", "type": "list", "list": "yes_no", "desc": "Plus tier only. Read-only connection."},
            {"name": "Service tier", "type": "text", "req": True, "desc": "Essentials / Standard / Plus."},
            {"name": "Service start date", "type": "date", "req": True},
            {"name": "ACT Leave employer registration no.", "type": "text", "desc": "ACT portable long service leave (construction) registration, if they employ in the ACT."},
            {"name": "Notes", "type": "text", "width": 40},
        ],
            },
    {
        "sheet": "People",
        "purpose": "Every worker who goes on site: employees, apprentices, subcontractors and their workers.",
        "id_prefix": "P",
        "columns": [
            {"name": "Person ID", "type": "text", "req": True, "desc": "P001, P002... Never reused."},
            {"name": "Full name", "type": "text", "req": True, "width": 24},
            {"name": "Person type", "type": "list", "list": "person_type", "req": True},
            {"name": "Subcontractor ID", "type": "text", "desc": "If a subbie or subbie's worker: the S### on the Subcontractors sheet."},
            {"name": "Roles", "type": "text", "req": True, "width": 26, "desc": "Semicolon list from the Roles lookup, e.g. 'Licensed plumber; Gasfitter'. Drives which licences the engine expects."},
            {"name": "States worked", "type": "list", "list": "state", "req": True},
            {"name": "Mobile", "type": "text", "desc": "For SMS alerts. Format 04xx xxx xxx."},
            {"name": "Email", "type": "text"},
            {"name": "Alert channel", "type": "list", "list": "alert_channel", "desc": "How the worker is chased. 'Client only' = we only tell the employer."},
            {"name": "Start date", "type": "date"},
            {"name": "End date", "type": "date", "desc": "Leave blank while active."},
            {"name": "Active", "type": "list", "list": "yes_no", "req": True, "desc": "N stops alerts for this person."},
            {"name": "Does high-risk construction work", "type": "list", "list": "yes_no", "desc": "Y if they do any work listed in WHS Reg r 291 (heights over 2m, trenches over 1.5m, confined spaces etc.)."},
            {"name": "Designated first aider", "type": "list", "list": "yes_no"},
            {"name": "Notes", "type": "text", "width": 30},
        ],
    },
    {
        "sheet": "Subcontractors",
        "purpose": "Subcontractor businesses. Their insurances go on the Insurances sheet with Holder type = Subcontractor.",
        "id_prefix": "S",
        "columns": [
            {"name": "Subcontractor ID", "type": "text", "req": True, "desc": "S001..."},
            {"name": "Business name", "type": "text", "req": True, "width": 26},
            {"name": "ABN", "type": "text", "req": True},
            {"name": "Trade", "type": "text"},
            {"name": "Contact name", "type": "text"},
            {"name": "Contact email", "type": "text"},
            {"name": "Contact mobile", "type": "text"},
            {"name": "States worked", "type": "list", "list": "state"},
            {"name": "Engaged from", "type": "date"},
            {"name": "Active", "type": "list", "list": "yes_no", "req": True},
            {"name": "Notes", "type": "text", "width": 30},
        ],
    },
    {
        "sheet": "Credentials",
        "purpose": "The licence and ticket register: one row per licence, ticket or training record.",
        "id_prefix": "L",
        "columns": [
            {"name": "Credential ID", "type": "text", "req": True, "desc": "L0001..."},
            {"name": "Person ID", "type": "text", "req": True},
            {"name": "Person name", "type": "formula", "width": 22,
             "formula": '=IFERROR(INDEX(People!$B:$B,MATCH(B{r},People!$A:$A,0)),"")',
             "desc": "Looked up from People."},
            {"name": "Credential type", "type": "list", "list": "credential_codes", "req": True, "width": 20,
             "desc": "Code from the Lookups sheet, which matches the rules library."},
            {"name": "Jurisdiction", "type": "list", "list": "state", "desc": "Issuing state."},
            {"name": "Licence / card number", "type": "text", "req": True},
            {"name": "Class / categories", "type": "text", "width": 24, "desc": "e.g. 'Advanced sanitary drainer' or 'Plumbing, Draining, Gasfitting'."},
            {"name": "Endorsements / conditions", "type": "text", "width": 20},
            {"name": "Issuer", "type": "text"},
            {"name": "Issue date", "type": "date"},
            {"name": "Expiry date", "type": "date", "req": True},
            {"name": "No expiry", "type": "list", "list": "yes_no", "desc": "Y for White Card, 11084NAT etc. Leave Expiry blank."},
            {"name": "Days to expiry", "type": "formula", "formula": _days("K")},
            {"name": "Status", "type": "formula", "width": 14, "formula": _status("M", noexp_col="L", date_col="K")},
            {"name": "Verification", "type": "list", "list": "verify_status", "req": True, "width": 22,
             "desc": "Unverified until a human has checked the document or the public register."},
            {"name": "Verified by", "type": "text"},
            {"name": "Verified on", "type": "date"},
            {"name": "Evidence file", "type": "link", "width": 30, "desc": "SharePoint link to the scan."},
            {"name": "Intake source", "type": "list", "list": "intake_source"},
            {"name": "Extracted by", "type": "list", "list": "extracted_by"},
            {"name": "Extraction confidence", "type": "text", "desc": "High / Medium / Low from Claude's extraction."},
            {"name": "Notes", "type": "text", "width": 30},
        ],
    },
    {
        "sheet": "Insurances",
        "purpose": "Client policies and subcontractor certificates of currency.",
        "id_prefix": "I",
        "columns": [
            {"name": "Insurance ID", "type": "text", "req": True, "desc": "I001..."},
            {"name": "Holder type", "type": "list", "list": "holder_type", "req": True},
            {"name": "Holder ID", "type": "text", "req": True, "desc": "Client ID (C###) or Subcontractor ID (S###)."},
            {"name": "Holder name", "type": "text", "width": 24},
            {"name": "Policy type", "type": "list", "list": "insurance_codes", "req": True, "width": 18},
            {"name": "Insurer", "type": "text"},
            {"name": "Policy number", "type": "text", "req": True},
            {"name": "Sum insured / limit", "type": "money", "desc": "e.g. 20000000 for $20m PL."},
            {"name": "Period start", "type": "date"},
            {"name": "Expiry date", "type": "date", "req": True},
            {"name": "Days to expiry", "type": "formula", "formula": _days("J")},
            {"name": "Status", "type": "formula", "width": 14, "formula": _status("K", date_col="J")},
            {"name": "Certificate on file", "type": "list", "list": "yes_no"},
            {"name": "Evidence file", "type": "link", "width": 30},
            {"name": "Principal / interested party noted", "type": "text", "desc": "Head contractor named on the certificate, if required."},
            {"name": "Verification", "type": "list", "list": "verify_status", "req": True},
            {"name": "Notes", "type": "text", "width": 30},
        ],
    },
    {
        "sheet": "Jobs",
        "purpose": "Jobs that need a SWMS or site-specific compliance. Feeds the SWMS generator.",
        "id_prefix": "J",
        "columns": [
            {"name": "Job ID", "type": "text", "req": True, "desc": "J0001..."},
            {"name": "Client job ref", "type": "text"},
            {"name": "Site address", "type": "text", "req": True, "width": 30},
            {"name": "State", "type": "list", "list": "state", "req": True},
            {"name": "Principal / head contractor", "type": "text"},
            {"name": "Scope of work", "type": "text", "req": True, "width": 40},
            {"name": "Start date", "type": "date", "req": True},
            {"name": "End date", "type": "date"},
            {"name": "Est. value ($)", "type": "money", "desc": "From $250k the principal contractor needs a WHS management plan."},
            {"name": "Plant and equipment", "type": "text", "width": 26},
            {"name": "Hazard: height over 2m", "type": "list", "list": "yes_no"},
            {"name": "Hazard: trench over 1.5m", "type": "list", "list": "yes_no"},
            {"name": "Hazard: confined space", "type": "list", "list": "yes_no"},
            {"name": "Hazard: live electrical", "type": "list", "list": "yes_no"},
            {"name": "Hazard: asbestos", "type": "list", "list": "yes_no"},
            {"name": "Hazard: silica", "type": "list", "list": "yes_no"},
            {"name": "Hazard: hot works", "type": "list", "list": "yes_no"},
            {"name": "Hazard: gas lines", "type": "list", "list": "yes_no"},
            {"name": "Hazard: traffic / mobile plant", "type": "list", "list": "yes_no"},
            {"name": "Other hazards", "type": "text", "width": 24},
            {"name": "Workers assigned (Person IDs)", "type": "text", "width": 20},
            {"name": "SWMS required", "type": "formula",
             "formula": '=IF(COUNTIF(K{r}:S{r},"Y")>0,"Y","Check")',
             "desc": "Y if any high-risk construction work hazard is ticked."},
            {"name": "SWMS status", "type": "list", "list": "swms_status"},
            {"name": "SWMS requested at", "type": "datetime"},
            {"name": "SWMS issued at", "type": "datetime"},
            {"name": "SWMS turnaround (hrs)", "type": "formula",
             "formula": '=IF(OR(X{r}="",Y{r}=""),"",ROUND((Y{r}-X{r})*24,1))'},
            {"name": "SWMS file", "type": "link", "width": 30},
            {"name": "Reviewed by", "type": "text"},
            {"name": "Notes", "type": "text", "width": 30},
        ],
    },
    {
        "sheet": "Chemicals",
        "purpose": "Hazardous chemicals register and SDS library index (WHS Reg r 344, r 346).",
        "id_prefix": "CH",
        "columns": [
            {"name": "Chemical ID", "type": "text", "req": True},
            {"name": "Product name", "type": "text", "req": True, "width": 26},
            {"name": "Manufacturer / supplier", "type": "text"},
            {"name": "Used for", "type": "text", "width": 24},
            {"name": "Hazardous chemical (GHS)", "type": "list", "list": "yes_no"},
            {"name": "Dangerous goods class", "type": "text"},
            {"name": "Where stored / max quantity", "type": "text"},
            {"name": "SDS issue date", "type": "date"},
            {"name": "SDS review due", "type": "formula",
             "formula": '=IF(H{r}="","",EDATE(H{r},60))',
             "desc": "Manufacturers must review SDSs at least every 5 years. Flags SDSs that may be out of date."},
            {"name": "SDS file", "type": "link", "width": 30},
            {"name": "Notes", "type": "text", "width": 30},
        ],
    },
    {
        "sheet": "Incidents",
        "purpose": "Incident and near-miss register. Notifiable incident records are kept for at least 5 years (WHS Act s 38(7)).",
        "id_prefix": "INC",
        "columns": [
            {"name": "Incident ID", "type": "text", "req": True},
            {"name": "Date / time", "type": "datetime", "req": True},
            {"name": "Job ID", "type": "text"},
            {"name": "Site", "type": "text", "width": 24},
            {"name": "People involved (IDs)", "type": "text"},
            {"name": "Type", "type": "list", "list": "incident_type", "req": True},
            {"name": "Description", "type": "text", "req": True, "width": 40},
            {"name": "Notifiable (WHS Act s 35)", "type": "list", "list": "yes_no", "req": True},
            {"name": "Regulator notified on", "type": "date"},
            {"name": "Regulator reference", "type": "text"},
            {"name": "Corrective actions", "type": "text", "width": 30},
            {"name": "Action owner", "type": "text"},
            {"name": "Close-out date", "type": "date"},
            {"name": "Status", "type": "list", "list": "open_closed"},
        ],
    },
    {
        "sheet": "Plant",
        "purpose": "Plant and equipment register, including test and tag.",
        "id_prefix": "PL",
        "columns": [
            {"name": "Plant ID", "type": "text", "req": True},
            {"name": "Description", "type": "text", "req": True, "width": 26},
            {"name": "Kind", "type": "list", "list": "plant_kind"},
            {"name": "Make / model", "type": "text"},
            {"name": "Serial / rego", "type": "text"},
            {"name": "Last inspection / test", "type": "date"},
            {"name": "Interval (months)", "type": "int", "desc": "e.g. 3 for construction-site electrical equipment under AS/NZS 3012."},
            {"name": "Next due", "type": "formula",
             "formula": '=IF(OR(F{r}="",G{r}=""),"",EDATE(F{r},G{r}))'},
            {"name": "Days to due", "type": "formula", "formula": _days("H")},
            {"name": "Status", "type": "formula", "width": 14, "formula": _status("I", date_col="H")},
            {"name": "Record file", "type": "link", "width": 30},
            {"name": "Notes", "type": "text", "width": 30},
        ],
    },
    {
        "sheet": "Documents",
        "purpose": "WHS policy set, procedures, plans and forms with review dates.",
        "id_prefix": "D",
        "columns": [
            {"name": "Document ID", "type": "text", "req": True},
            {"name": "Title", "type": "text", "req": True, "width": 34},
            {"name": "Category", "type": "list", "list": "doc_category"},
            {"name": "Version", "type": "text"},
            {"name": "Owner", "type": "text"},
            {"name": "Approved date", "type": "date"},
            {"name": "Review interval (months)", "type": "int"},
            {"name": "Next review", "type": "formula",
             "formula": '=IF(OR(F{r}="",G{r}=""),"",EDATE(F{r},G{r}))'},
            {"name": "Days to review", "type": "formula", "formula": _days("H")},
            {"name": "Status", "type": "formula", "width": 14, "formula": _status("I", date_col="H")},
            {"name": "File", "type": "link", "width": 30},
            {"name": "Notes", "type": "text", "width": 30},
        ],
    },
]

# Sheets with an expiry the engine watches: sheet -> (id col, date col, type col, holder col)
EXPIRY_SHEETS = {
    "Credentials": {"id": "Credential ID", "date": "Expiry date", "type": "Credential type",
                    "holder": "Person ID", "no_expiry": "No expiry", "number": "Licence / card number"},
    "Insurances": {"id": "Insurance ID", "date": "Expiry date", "type": "Policy type",
                   "holder": "Holder ID", "number": "Policy number"},
}

# Master client list (ops workbook)
MASTER_SHEETS = {
    "Clients": [
        "Client ID", "Legal name", "Tier", "Monthly fee ($)", "States", "Trades", "Status",
        "Start date", "Folder link", "Register file", "Primary contact", "Primary contact email",
        "RAG (latest)", "Expired items", "Due within 30 days", "Missing items", "Last engine run",
        "Human minutes (month to date)", "Notes",
    ],
    "Time Log": [
        "Date", "Client ID", "Staff", "Activity", "Minutes", "Billable to tier scope (Y/N)", "Notes",
    ],
    "Audit Log": [
        "Timestamp", "Client ID", "Item type", "Item reference", "Generated by", "File / location",
        "Status", "Reviewed by", "Reviewed at", "Sent at", "Notes",
    ],
}

TIME_ACTIVITIES = [
    "Onboarding", "Intake processing", "Credential verification", "Alert review / chasing",
    "SWMS drafting", "SWMS review", "Register maintenance", "Client call / email",
    "Quarterly pack", "Policy review", "Insurance renewal pack", "Xero snapshot", "Other",
]
