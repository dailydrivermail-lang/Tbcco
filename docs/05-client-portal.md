# Client portal

A small web app on top of the existing registers. **The Excel register stays the source of truth.** The portal reads it with the same engine and rules as the expiry engine, so the statuses always agree.

## What clients get

| Page | What it shows / does |
|---|---|
| **Overview** | Red/amber/green banner; counts (expired, due ≤30 days, 31-60 days, things we need); "What we need from you" with an Upload button on each item; coming up in 60 days; latest reports; Request a SWMS |
| **People & licences** | Every active worker, their licences, tickets and training, expiry status, and whether we've checked the document |
| **Insurance** | Their policies and their subbies' certificates of currency |
| **Jobs & SWMS** | Jobs and SWMS status. **An issued SWMS can only be downloaded once the register says `Issued` and `Reviewed by` is filled in**, and the PDF is in `04_Jobs/<JobID>_…/Issued/`. That's the human-review gate. |
| **Request a SWMS** | Guided job assessment: pick the job type, answer only the questions that job triggers, pick the crew, confirm the key answers. Submitting starts the 24-hour clock. See `docs/06-swms-generator.md`. |
| **Reports** | Anything we put in `09_Client_Reports` (monthly, quarterly, register snapshots) |
| **Upload** | Phone photos or PDFs go to `01_Intake_Inbox/portal/`, tagged with type and who it's for. They show as "Received" until we move the file to `_processed`. |

## What staff get

- **All clients**: red first, with expired, due and missing counts, new uploads, and pending SWMS requests.
- **Inbox**: every pending SWMS request and upload across clients. **Add to Jobs register** writes the request into the client's Jobs sheet (status `Requested`, with the requested-at timestamp).
- **Staff view of any client**: the same pages the client sees, plus items from rules Ivana hasn't verified yet, tagged "Staff only: rule pending review".

## The legal-review gate

By default, clients **only** see "not on file" items that come from rules Ivana has marked `Verified` in `rules/rules_library.csv`. Right now that's none, so clients see expired items and missing dates only (facts about their records), and staff see everything. Once Ivana verifies a rule, its gaps appear to clients automatically. `PORTAL_SHOW_UNREVIEWED_RULE_GAPS=1` overrides this; don't use it in production.

## Running it

```bash
pip install -r requirements.txt

# Demo with fictional data (two clients):
python -m portal.run --demo            # http://127.0.0.1:8080
#   client: pat@example.com / demo-client-password
#   staff:  staff@example.com / demo-staff-password

# Real data on the ops PC (localhost only):
set PORTAL_CLIENTS_ROOT=C:\Users\steve\OneDrive - Firm\Compliance Ops\01_Clients
python -m portal.manage add --email steve@ourfirm.com.au --role staff --name Steve
python -m portal.manage add --email pat@abcplumbing.com.au --client C001 --name "Pat Owner"
python -m portal.run
```

Users, the audit log (`portal_audit.csv`: logins, failed logins, uploads, downloads, SWMS requests and acceptances) and the session key live in `04_Ops/portal/`.

## Getting clients onto it (localhost is not reachable by clients)

On the ops PC, the portal is for us: development, Ivana's review, and screen-sharing with pilots. For clients to log in themselves:

1. **Azure App Service (Linux, Python), region Australia East.** About $20-50 a month at B1. Start command: `waitress-serve --port=8000 --call portal:create_app`.
2. Storage: mount the SharePoint data through a sync job, or (better, at scale) move the registers to Azure Files or SharePoint via Microsoft Graph. This is the main piece of work for that step. The portal only touches files through `portal/data.py`, so that's the one module to change.
3. App settings: `PORTAL_CLIENTS_ROOT`, `PORTAL_DATA_DIR`, `PORTAL_SECRET_KEY` (from Key Vault), `PORTAL_SECURE_COOKIES=1`. HTTPS only.
4. Optional: put Microsoft Entra ID sign-in in front for staff, and keep the portal's own accounts for clients.

## Security notes

- Passwords are hashed (Werkzeug scrypt/pbkdf2) with a 12-character minimum, and staff issue temporary passwords (`portal.manage add/reset`).
- 8 failed logins per IP in 15 minutes triggers a lockout; failed logins are audit-logged.
- Every POST has a CSRF token. Session cookies are HttpOnly and SameSite=Lax (Secure in production), with an 8-hour session.
- Each client can only access its own `client_id`; tests check that one client can't see another's data.
- Downloads are confined to `09_Client_Reports` and issued SWMS folders (path traversal is tested). Uploads are allow-listed by extension with magic-byte checks, capped at 25 MB, and renamed on save.
- Security headers: strict CSP (no inline scripts), `X-Frame-Options: DENY`, `no-store` caching.
- **Before production, get a short external security review.** It holds staff personal information.

## Known limits (pilot)

- Desktop Excel holding the register open can block "Add to Jobs register". The portal reports this; close the file and retry. Excel Online co-authoring is fine.
- No self-service password reset yet: staff reset passwords on request.
- No email notifications from the portal itself. The expiry engine's reviewed drafts remain the alert channel.
