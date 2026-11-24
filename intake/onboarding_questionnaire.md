# Intake: onboarding questionnaire and recurring intake

Target: a new client takes about **30 minutes of their time** and **under 2 hours of ours** to onboard.

## Channels (Microsoft 365)

| Channel | Use | Why |
|---|---|---|
| **Microsoft Form: "Business onboarding"** (Anyone with link) | Business details, insurances, trades, head contractors, current WHS documents | Structured, mobile-friendly, and responses land in an Excel file. |
| **Excel: `People_and_Licences_Intake.xlsx`** | Staff, subbies, licences, tickets, chemicals, plant | A 20-person list is painful in a form. Most clients already have a staff list to paste in. |
| **OneDrive "Request files" link** → client's `01_Intake_Inbox` | Photos and scans of licences, cards, certificates of currency, SDSs, policies | ⚠ Microsoft Forms **file upload only works for respondents inside our tenant**, so external clients can't upload through a Form. Request-files links are upload-only: clients can't see anything else. |
| **Shared mailbox** `compliance@…` | Anything clients email or forward. A Power Automate rule saves attachments to the client's `01_Intake_Inbox` (match on sender domain), or we file them by hand in the pilot. | Clients will email photos regardless. Make that the easy path. |
| **Microsoft Form: "New job / SWMS request"** (Standard and Plus) | Per-job details for the SWMS generator | Feeds the 24-hour SWMS commitment. Timestamp = SWMS requested at. |

Processing loop: inbox file → Claude extracts it (`intake/claude/extract_document_prompt.md`) → `python -m engine.intake_import extraction …` → a human verifies the rows (Verification = Verified - document / public register) → file renamed into `02_`/`03_` and the original moved to `_processed/`.

---

## Form 1: Business onboarding

Build it in Microsoft Forms in this order. **(R)** = required. The type is shown in brackets. *Maps to* = register field.

### Section A: Your business
1. Legal entity name **(R)** [text] *Maps to Business.Legal name*
2. Trading name [text] *Trading name*
3. ABN **(R)** [text, 11 digits; restrict to number] *ABN*
4. Entity type [choice: Company / Trust / Partnership / Sole trader] *Entity type*
5. Which work do you do? **(R)** [multi-choice: Plumbing (water) / Sanitary plumbing / Drainage / Gasfitting (natural gas) / LPG / Roof plumbing / Backflow testing / Fire services / Hot water (incl. heat pumps) / Air conditioning / Other] *Trades*
6. Where do you work? **(R)** [multi-choice: ACT / NSW / Other] *States operated*
7. Your business licence numbers (ACT corporate licence, NSW contractor licence) [long text] *Business licence numbers*
8. How many employees, including apprentices? **(R)** [number] *Employees (FTE)*
9. How many subcontractors do you use regularly? [number] *Regular subcontractors*
10. Main head contractors / builders you work for [long text] *Head contractors worked for*
11. Roughly what share of your work is residential? [choice: 0-25% / 26-50% / 51-75% / 76-100%] *Residential / commercial mix*

### Section B: Contacts
12. Main contact name, email and mobile **(R)** [3 text fields] *Primary contact…*
13. Who looks after safety day to day, if different? [text]
14. Best way to reach your workers about expiring tickets? [choice: Email / SMS / Both / Only tell me] *default for People.Alert channel*

### Section C: Insurance
15. Insurer and broker (firm, contact, email) [long text] *Insurer, Broker, Broker email*
16. Public liability: insurer, policy no., limit, expiry date [text, text, choice $5m/$10m/$20m/Other, date] *Insurances (PL)*
17. Workers' compensation: ACT policy no. and expiry; NSW (icare) policy no. and expiry [text/date pairs] *Insurances (WC_ACT / WC_NSW)*
18. Any other policies? [multi-choice: Contract works / Professional indemnity / Motor / Tools / None] then text for numbers and expiry
19. When is your main insurance renewal? [date] (used for the Plus-tier renewal pack)
20. NSW only: do you collect subcontractor statements from your subbies? [Yes / No / Not sure] *rule B-NSW-03*

### Section D: How you work (drives the rules engine)
21. Which of these do your people do? [multi-choice, each maps to a rule condition]
    - Work at heights over 2 m (roofs, stormwater, ceiling spaces)
    - Trenches deeper than 1.5 m
    - Confined spaces (pits, tanks, sewer structures)
    - Near live electrical / disconnect-reconnect hot water units
    - Work in pre-2004 buildings / likely asbestos (AC pipe, flues, eaves)
    - Cutting, chasing or core-drilling concrete, masonry or tiles (silica)
    - Hot works (brazing, soldering with flame)
    - Gas mains or pressurised gas lines
    - Refrigerant handling (heat pumps, split systems)
    - Backflow device testing
    - Forklift / EWP over 11 m / scaffolding
    - Traffic or mobile plant near the work area
22. Are you ever the principal contractor on jobs over $250,000? [Yes / No / Not sure] *rule J-ALL-02*
23. Who are your designated first aiders? [text] *People.Designated first aider*

### Section E: What you already have
24. Which of these do you have now? [multi-choice: WHS policy / Safety management system / SWMS templates / Chemical register / SDS folder / Incident register / Test & tag records / Emergency plan / Toolbox talk records / None]
25. Has a head contractor, insurer or WorkSafe asked for anything you couldn't produce in the last 12 months? [long text] (sales gold, and the baseline for the case study)
26. Roughly how many hours a month do you spend on compliance paperwork now? [number] (baseline for "time saved")

### Section F: Consent
27. "I confirm I'm authorised to provide this information, including staff personal information, for the purpose of managing our compliance, and that our staff have been told about this." **(R)** [checkbox]
    *(Ivana: check the wording against APP 5 notification and the service agreement.)*

**After submit:** a Power Automate flow (or, in the pilot, a manual step) runs `new_client.py`, emails the welcome pack (Request-files link and the People & Licences spreadsheet), and logs a 15-minute "Onboarding" entry in the Time Log.

---

## The People & Licences spreadsheet

`intake/People_and_Licences_Intake.xlsx` (generated). Tabs: Start here, People, Subcontractors, Chemicals, Plant.
One row per person, with licence and ticket columns across. Import it with:

```
python -m engine.intake_import sheet --client-dir ".../01_Clients/C001_…" --file ".../Filled_People_and_Licences_Intake.xlsx"
```

The import is append-only, de-duplicates people and subbies by name, and marks every credential **Unverified**.

---

## Form 2: New job / SWMS request (Standard and Plus)

1. Your business name **(R)**. 2. Site address **(R)**. 3. State **(R)**. 4. Builder / head contractor. 5. What's the job? (scope) **(R)**
6. Start date **(R)**. 7. Estimated value. 8. Who's on the job? (names) 9. Plant and equipment.
10. Hazards [same multi-choice list as Q21, plus "Other"]. 11. Building age (pre-1990 / 1990-2003 / 2004+ / unknown).
12. Anything special about the site? (access, live services, occupants, traffic). 13. Does the head contractor have its own SWMS template we must use? [Yes, upload by email / No]

The response timestamp becomes **SWMS requested at** on the Jobs sheet. That's when the 24-hour clock starts.

---

## Recurring intake (monthly)

| When | What | How |
|---|---|---|
| Continuous | Renewed cards and certificates | Workers and the client reply to alert emails or SMS with a photo; it lands in the inbox and is extracted |
| Per job | SWMS request | Form 2 |
| Monthly (1st business day) | "Anything new?" check-in: new starters, leavers, new subbies, incidents and near misses, new chemicals, plant serviced | Part of the monthly summary email: 5 tick-box questions with a reply-to link |
| Within 24h of the client knowing | Incidents | Phone or email to the shared mailbox. **Notifiable incidents: the client must notify the regulator immediately. We don't do this for them.** |
| Quarterly | Head contractor prequalification changes, insurance changes | Quarterly pack call (Standard and Plus) |
