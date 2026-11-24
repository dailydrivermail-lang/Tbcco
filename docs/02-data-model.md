# Data model (generated)

Generated from `engine/schema.py` by `python -m engine.build_templates`. Do not edit by hand.

Each client has one register workbook (`00_Register/<ClientID>_Register.xlsx`) with the sheets below.
**Req** = must be captured at intake. Formula columns are computed in Excel; the engine recomputes them in Python.

## Business

One row per client business. Key facts the engine and reports pull from.

| Field | Type | Req | Notes |
|---|---|---|---|
| Client ID | text | Y | Our ID, e.g. C001. Matches the folder name. |
| Legal name | text | Y | Entity name as on the ABR. |
| Trading name | text |  | If different. |
| ABN | text | Y | 11 digits, no spaces. |
| Entity type | text |  | Company / trust / partnership / sole trader. |
| Trades | text | Y | Semicolon list: Plumbing; Drainage; Gasfitting; Roof plumbing; Backflow; Fire services; HVAC. |
| States operated | list (state) | Y | ACT, NSW, or both. |
| Business licence numbers | text |  | ACT corporate licence / NSW contractor licence numbers (details go on the Credentials sheet against the nominee). |
| Employees (FTE) | int |  | Headcount used for first-aid ratios and tier fit. |
| Regular subcontractors | int |  | Count. |
| Head contractors worked for | text |  | Semicolon list. Their prequalification requirements are captured in the gap analysis (Phase 2). |
| Residential / commercial mix | text |  | e.g. 60% residential. |
| Insurer | text |  | Main liability insurer. |
| Broker | text |  | Broker firm and contact. |
| Broker email | text |  |  |
| Primary contact | text | Y | Person who receives alerts and the monthly summary. |
| Primary contact email | text | Y |  |
| Primary contact mobile | text | Y |  |
| Safety contact (if different) | text |  |  |
| Safety contact email | text |  |  |
| Xero connected | list (yes_no) |  | Plus tier only. Read-only connection. |
| Service tier | text | Y | Essentials / Standard / Plus. |
| Service start date | date | Y |  |
| ACT Leave employer registration no. | text |  | ACT portable long service leave (construction) registration, if they employ in the ACT. |
| Notes | text |  |  |

## People

Every worker who goes on site: employees, apprentices, subcontractors and their workers.

| Field | Type | Req | Notes |
|---|---|---|---|
| Person ID | text | Y | P001, P002... Never reused. |
| Full name | text | Y |  |
| Person type | list (person_type) | Y |  |
| Subcontractor ID | text |  | If a subbie or subbie's worker: the S### on the Subcontractors sheet. |
| Roles | text | Y | Semicolon list from the Roles lookup, e.g. 'Licensed plumber; Gasfitter'. Drives which licences the engine expects. |
| States worked | list (state) | Y |  |
| Mobile | text |  | For SMS alerts. Format 04xx xxx xxx. |
| Email | text |  |  |
| Alert channel | list (alert_channel) |  | How the worker is chased. 'Client only' = we only tell the employer. |
| Start date | date |  |  |
| End date | date |  | Leave blank while active. |
| Active | list (yes_no) | Y | N stops alerts for this person. |
| Does high-risk construction work | list (yes_no) |  | Y if they do any work listed in WHS Reg r 291 (heights over 2m, trenches over 1.5m, confined spaces etc.). |
| Designated first aider | list (yes_no) |  |  |
| Notes | text |  |  |

## Subcontractors

Subcontractor businesses. Their insurances go on the Insurances sheet with Holder type = Subcontractor.

| Field | Type | Req | Notes |
|---|---|---|---|
| Subcontractor ID | text | Y | S001... |
| Business name | text | Y |  |
| ABN | text | Y |  |
| Trade | text |  |  |
| Contact name | text |  |  |
| Contact email | text |  |  |
| Contact mobile | text |  |  |
| States worked | list (state) |  |  |
| Engaged from | date |  |  |
| Active | list (yes_no) | Y |  |
| Notes | text |  |  |

## Credentials

The licence and ticket register: one row per licence, ticket or training record.

| Field | Type | Req | Notes |
|---|---|---|---|
| Credential ID | text | Y | L0001... |
| Person ID | text | Y |  |
| Person name | formula |  | Looked up from People. |
| Credential type | list (credential_codes) | Y | Code from the Lookups sheet, which matches the rules library. |
| Jurisdiction | list (state) |  | Issuing state. |
| Licence / card number | text | Y |  |
| Class / categories | text |  | e.g. 'Advanced sanitary drainer' or 'Plumbing, Draining, Gasfitting'. |
| Endorsements / conditions | text |  |  |
| Issuer | text |  |  |
| Issue date | date |  |  |
| Expiry date | date | Y |  |
| No expiry | list (yes_no) |  | Y for White Card, 11084NAT etc. Leave Expiry blank. |
| Days to expiry | formula |  |  |
| Status | formula |  |  |
| Verification | list (verify_status) | Y | Unverified until a human has checked the document or the public register. |
| Verified by | text |  |  |
| Verified on | date |  |  |
| Evidence file | link |  | SharePoint link to the scan. |
| Intake source | list (intake_source) |  |  |
| Extracted by | list (extracted_by) |  |  |
| Extraction confidence | text |  | High / Medium / Low from Claude's extraction. |
| Notes | text |  |  |

## Insurances

Client policies and subcontractor certificates of currency.

| Field | Type | Req | Notes |
|---|---|---|---|
| Insurance ID | text | Y | I001... |
| Holder type | list (holder_type) | Y |  |
| Holder ID | text | Y | Client ID (C###) or Subcontractor ID (S###). |
| Holder name | text |  |  |
| Policy type | list (insurance_codes) | Y |  |
| Insurer | text |  |  |
| Policy number | text | Y |  |
| Sum insured / limit | money |  | e.g. 20000000 for $20m PL. |
| Period start | date |  |  |
| Expiry date | date | Y |  |
| Days to expiry | formula |  |  |
| Status | formula |  |  |
| Certificate on file | list (yes_no) |  |  |
| Evidence file | link |  |  |
| Principal / interested party noted | text |  | Head contractor named on the certificate, if required. |
| Verification | list (verify_status) | Y |  |
| Notes | text |  |  |

## Jobs

Jobs that need a SWMS or site-specific compliance. Feeds the SWMS generator.

| Field | Type | Req | Notes |
|---|---|---|---|
| Job ID | text | Y | J0001... |
| Client job ref | text |  |  |
| Site address | text | Y |  |
| State | list (state) | Y |  |
| Principal / head contractor | text |  |  |
| Scope of work | text | Y |  |
| Start date | date | Y |  |
| End date | date |  |  |
| Est. value ($) | money |  | From $250k the principal contractor needs a WHS management plan. |
| Plant and equipment | text |  |  |
| Hazard: height over 2m | list (yes_no) |  |  |
| Hazard: trench over 1.5m | list (yes_no) |  |  |
| Hazard: confined space | list (yes_no) |  |  |
| Hazard: live electrical | list (yes_no) |  |  |
| Hazard: asbestos | list (yes_no) |  |  |
| Hazard: silica | list (yes_no) |  |  |
| Hazard: hot works | list (yes_no) |  |  |
| Hazard: gas lines | list (yes_no) |  |  |
| Hazard: traffic / mobile plant | list (yes_no) |  |  |
| Other hazards | text |  |  |
| Workers assigned (Person IDs) | text |  |  |
| SWMS required | formula |  | Y if a high-risk construction work category (WHS Reg r 291) is ticked. Silica and hot works alone are not r 291 categories but still go in the SWMS when present. |
| SWMS status | list (swms_status) |  |  |
| SWMS requested at | datetime |  |  |
| SWMS issued at | datetime |  |  |
| SWMS turnaround (hrs) | formula |  |  |
| SWMS file | link |  |  |
| Reviewed by | text |  |  |
| Notes | text |  |  |

## Chemicals

Hazardous chemicals register and SDS library index (WHS Reg r 344, r 346).

| Field | Type | Req | Notes |
|---|---|---|---|
| Chemical ID | text | Y |  |
| Product name | text | Y |  |
| Manufacturer / supplier | text |  |  |
| Used for | text |  |  |
| Hazardous chemical (GHS) | list (yes_no) |  |  |
| Dangerous goods class | text |  |  |
| Where stored / max quantity | text |  |  |
| SDS issue date | date |  |  |
| SDS review due | formula |  | Manufacturers must review SDSs at least every 5 years. Flags SDSs that may be out of date. |
| SDS file | link |  |  |
| Notes | text |  |  |

## Incidents

Incident and near-miss register. Notifiable incident records are kept for at least 5 years (WHS Act s 38(7)).

| Field | Type | Req | Notes |
|---|---|---|---|
| Incident ID | text | Y |  |
| Date / time | datetime | Y |  |
| Job ID | text |  |  |
| Site | text |  |  |
| People involved (IDs) | text |  |  |
| Type | list (incident_type) | Y |  |
| Description | text | Y |  |
| Notifiable (WHS Act s 35) | list (yes_no) | Y |  |
| Regulator notified on | date |  |  |
| Regulator reference | text |  |  |
| Corrective actions | text |  |  |
| Action owner | text |  |  |
| Close-out date | date |  |  |
| Status | list (open_closed) |  |  |

## Plant

Plant and equipment register, including test and tag.

| Field | Type | Req | Notes |
|---|---|---|---|
| Plant ID | text | Y |  |
| Description | text | Y |  |
| Kind | list (plant_kind) |  |  |
| Make / model | text |  |  |
| Serial / rego | text |  |  |
| Last inspection / test | date |  |  |
| Interval (months) | int |  | e.g. 3 for construction-site electrical equipment under AS/NZS 3012. |
| Next due | formula |  |  |
| Days to due | formula |  |  |
| Status | formula |  |  |
| Record file | link |  |  |
| Notes | text |  |  |

## Documents

WHS policy set, procedures, plans and forms with review dates.

| Field | Type | Req | Notes |
|---|---|---|---|
| Document ID | text | Y |  |
| Title | text | Y |  |
| Category | list (doc_category) |  |  |
| Version | text |  |  |
| Owner | text |  |  |
| Approved date | date |  |  |
| Review interval (months) | int |  |  |
| Next review | formula |  |  |
| Days to review | formula |  |  |
| Status | formula |  |  |
| File | link |  |  |
| Notes | text |  |  |

## Credential type codes

| Code | Name | Issuer | Typical validity (yrs) |
|---|---|---|---|
| ACT_PLUMBER | ACT plumber licence (class as listed) | Access Canberra (Construction Occupations Registrar) | verify |
| ACT_DRAINER | ACT drainer licence (advanced sanitary / journeyperson / operative) | Access Canberra | verify |
| ACT_GASFITTER | ACT gasfitter licence (general / advanced / LPG / other class) | Access Canberra | verify |
| ACT_GAS_APPLIANCE | ACT gas appliance worker licence | Access Canberra | verify |
| ACT_BACKFLOW_END | ACT backflow prevention testing endorsement | Access Canberra | verify |
| NSW_CONTRACTOR_PDG | NSW contractor licence - plumbing/draining/gasfitting | Building Commission NSW | 1-5 |
| NSW_QS_PDG | NSW qualified supervisor certificate - plumbing/draining/gasfitting | Building Commission NSW | 1-5 |
| NSW_TRADE_PDG | NSW tradesperson certificate - plumbing/draining/gasfitting | Building Commission NSW | 1-5 |
| WHITE_CARD | General construction induction (White Card, CPCWHS1001) | WHS regulator (any state) |  |
| ACT_ASB_AWARE | Asbestos awareness - 11084NAT (ACT mandatory) | Approved RTO |  |
| ACT_SILICA | Crystalline silica exposure prevention - 10830NAT (ACT mandatory) | Approved RTO |  |
| ACT_ASB_ACM | Working safely with asbestos-containing materials (ACT, specified occupations) | Approved RTO |  |
| HRWL_WP | High risk work licence - boom-type EWP 11m+ (WP) | WHS regulator | 5 |
| HRWL_LF | High risk work licence - forklift (LF) | WHS regulator | 5 |
| HRWL_SB | High risk work licence - basic scaffolding (SB) | WHS regulator | 5 |
| HRWL_DG | High risk work licence - dogging (DG) | WHS regulator | 5 |
| HRWL_OTHER | High risk work licence - other class (specify) | WHS regulator | 5 |
| FIRST_AID | Provide first aid (HLTAID011) | RTO | 3 |
| CPR | Provide CPR (HLTAID009) | RTO | 1 |
| CONFINED_SPACE | Enter and work in confined spaces (e.g. RIIWHS202E) | RTO | verify |
| WORK_AT_HEIGHTS | Work safely at heights (e.g. RIIWHS204E) | RTO | verify |
| GAS_TEST_ATMOS | Gas test atmospheres (e.g. MSMWHS217) | RTO | verify |
| ARCTICK_RHL | ARCtick refrigerant handling licence | Australian Refrigeration Council | verify |
| ELEC_RESTRICTED | Restricted electrical licence (disconnect/reconnect) | State licensing body | verify |
| TEST_TAG | Test and tag competency | RTO | verify |
| EWP_YELLOW | EWP under 11m operator training (IPAF/EWPA yellow card) | Industry | 5 |
| DRIVER_LICENCE | Driver licence | State road authority | varies |
| OTHER | Other (describe in notes) |  |  |

## Insurance / evidence codes

| Code | Name |
|---|---|
| PL | Public and products liability |
| WC_ACT | Workers' compensation - ACT |
| WC_NSW | Workers' compensation - NSW (icare) |
| PI | Professional indemnity |
| CONTRACT_WORKS | Contract works / construction risk |
| MOTOR | Commercial motor vehicle |
| TOOLS | Tools and equipment |
| PERSONAL_ACCIDENT | Personal accident / sickness (sole-trader subbie) |
| HBCF | NSW Home Building Compensation Fund certificate |
| NSW_SUBBIE_STMT | NSW subcontractor statement (s 175B WC Act 1987) |
| OTHER | Other (describe in notes) |

## Master client list (ops workbook)

- **Clients**: Client ID, Legal name, Tier, Monthly fee ($), States, Trades, Status, Start date, Folder link, Register file, Primary contact, Primary contact email, RAG (latest), Expired items, Due within 30 days, Missing items, Last engine run, Human minutes (month to date), Notes
- **Time Log**: Date, Client ID, Staff, Activity, Minutes, Billable to tier scope (Y/N), Notes
- **Audit Log**: Timestamp, Client ID, Item type, Item reference, Generated by, File / location, Status, Reviewed by, Reviewed at, Sent at, Notes
