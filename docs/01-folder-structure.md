# Folder structure (Microsoft 365)

Two places, kept separate:

| Where | What | Who |
|---|---|---|
| **This Git repo** | Tooling only: schema, rules library, templates, scripts, prompts, docs. **No client data, ever** (`clients/` is git-ignored). | Steve, Ivana |
| **SharePoint site "Compliance Ops"** (tenant data residency: Australia) | All client data, registers, outputs, ops workbook. | Staff by role; clients see only their shared folders |

Check the tenant's data location in the M365 admin centre (Settings > Org settings > Organization profile > Data location). Sydney and Melbourne should be listed for SharePoint/OneDrive/Exchange.

## SharePoint layout

```
Compliance Ops (SharePoint site, private)
├── 01_Clients/                      ← document library; sync this to the ops PC for the engine
│   ├── C001_ABC-Plumbing-Pty-Ltd/   ← created by: python -m engine.new_client
│   │   ├── 00_Register/             C001_Register.xlsx (the client's single source of truth)
│   │   ├── 01_Intake_Inbox/         client "Request files" upload link + emailed attachments land here
│   │   │   └── _processed/          moved here once extracted into the register
│   │   ├── 02_People_Credentials/   P001_Sam-Smith/  P001_ACT_PLUMBER_2026-12-19.pdf …
│   │   ├── 03_Insurance/
│   │   │   ├── Client/              I001_PL_2027-01-08.pdf
│   │   │   └── Subcontractors/      S001_Placeholder-Drainage/ …
│   │   ├── 04_Jobs/                 J0001_12-Smith-St-Kambah/ (SWMS drafts, issued SWMS, permits)
│   │   ├── 05_Chemicals_SDS/        CH001_PVC-solvent-cement_SDS_2024-05.pdf
│   │   ├── 06_Incidents/
│   │   ├── 07_Plant/                test & tag, service records
│   │   ├── 08_Policies_Procedures/  Current/ · Superseded/
│   │   ├── 09_Client_Reports/       ← SHARED READ-ONLY WITH CLIENT
│   │   │   ├── Monthly/  Quarterly/  Registers/ (PDF/XLSX snapshots of the live register)
│   │   ├── 10_Correspondence/
│   │   ├── _outbox/YYYY-MM-DD/      engine drafts awaiting review (internal only)
│   │   ├── _system/                 alert_state.csv, engine_runs.csv (internal only)
│   │   └── 99_Archive/
│   └── C002_…
├── 02_Templates/                    copies of /templates and /intake from this repo
├── 03_Rules_Library/                Rules_Library_REVIEW.xlsx (Ivana signs off here)
├── 04_Ops/                          Master_Client_List.xlsx (client list, Time Log, Audit Log)
└── 05_Sales/                        pitch, offer, service agreement, prospect lists
```

## File naming

`<ItemID>_<Code>_<Expiry YYYY-MM-DD>.<ext>`. For example, `P003_HRWL_LF_2029-05-12.pdf` or `S001_PL_2027-06-30.pdf`.
IDs never change, so links in the register don't break. Superseded evidence goes to `99_Archive`. Never delete it, because it's the audit trail.

## Access (least privilege)

| Group | Access |
|---|---|
| Owners (Steve, Ivana) | Full control of the site |
| Compliance staff / VAs | Edit on `01_Clients` and `04_Ops`; no site-settings rights |
| Client (each contact, by email) | **Upload-only** "Request files" link to their `01_Intake_Inbox`. **View-only** on their `09_Client_Reports`. Nothing else. |
| Engine (ops PC / service account) | OneDrive sync of `01_Clients` and `04_Ops` |

Use MFA on every account. Turn off "Anyone" links at the site level except for the Request-files links. Review external sharing quarterly.

## Why one workbook per client

- The client's whole compliance position sits in one file you can hand over, snapshot or archive.
- Excel Online lets two of us edit at once, and version history gives a free change log.
- At 100+ clients, the same schema can move into SharePoint Lists or Dataverse without changing field names. That's why `engine/schema.py` is the single source of truth.
