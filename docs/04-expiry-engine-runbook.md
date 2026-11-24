# Licence and expiry register: runbook

## What it does

The **live register** is each client's `C###_Register.xlsx`. Status columns recalculate every time it's opened (days are counted from `TODAY()`), so the register is always current without running anything.

The **engine** (`engine/expiry_engine.py`) runs daily or weekly and:

1. Buckets every licence, ticket, insurance, plant test and document review into **EXPIRED · DUE 7 · DUE 30 · DUE 60 · CURRENT · NO EXPIRY · MISSING DATE**.
2. Checks each active person, subcontractor and the business against the rules library, and finds missing credentials and insurances.
3. Drafts an alert only when an item **moves into a more urgent stage** (60 → 30 → 7 → expired). Expired items are re-chased **weekly**. Running it twice in a day drafts nothing new.
4. Writes everything to `<client>/_outbox/<date>/`:
   - `C###_REVIEW_<date>.xlsx`: internal review sheet (items, missing items tagged with legal-review status, questions to confirm with the client)
   - `C###_client_summary_<date>.eml`: draft to the client contact (opens in Outlook as an editable draft)
   - `C###_worker_P###_<date>.eml`: draft to each worker whose channel includes email
   - `C###_sms_drafts_<date>.csv`: SMS drafts with an `Approved (Y/N)` column, ready for an SMS tool (e.g. MessageMedia or ClickSend, both of which have Australian data hosting options)
5. Updates the **Master Client List**: RAG, counts, last run, and one **Audit Log** row per draft (status "Draft - awaiting review").

**Nothing is sent automatically.** A reviewer opens each draft, edits it, sends it, then fills in *Reviewed by / Reviewed at / Sent at* in the Audit Log.

## RAG

- **RED:** any credential or insurance expired, or any statutory requirement missing
- **AMBER:** anything due within 30 days, a missing date, or a non-statutory gap
- **GREEN:** otherwise

## Daily routine (target: 5 to 10 minutes per client per week)

```bash
# on the ops PC with 01_Clients and 04_Ops synced via OneDrive
python -m engine.expiry_engine --clients-root "~/OneDrive - Firm/Compliance Ops/01_Clients" \
       --master "~/OneDrive - Firm/Compliance Ops/04_Ops/Master_Client_List.xlsx"
```

1. Open the Master Client List and sort by RAG.
2. For each client with new drafts, open `REVIEW.xlsx`. Sanity-check it (for example, is the person still employed?).
3. Send the emails and approved SMS. Log the time in **Time Log** (activity "Alert review / chasing").
4. When renewals come back: process the inbox (extraction prompt → `intake_import extraction`), verify, and update the expiry date.

Schedule it with Windows Task Scheduler (daily at 6:30am). Don't run it while someone has the register open in desktop Excel; Excel Online co-authoring is fine.

## New client

```bash
python -m engine.new_client --root ".../01_Clients" --id C001 --name "ABC Plumbing Pty Ltd" \
       --tier Standard --states "ACT;NSW" --master ".../04_Ops/Master_Client_List.xlsx"
python -m engine.intake_import sheet --client-dir ".../01_Clients/C001_ABC-Plumbing-Pty-Ltd" --file Filled_Intake.xlsx
```

## Changing fields

Edit `engine/schema.py`, then run `python -m engine.build_templates`. Existing client registers don't change automatically. Add the new column to them by hand, or with a small migration script, before relying on it.

## Time tracking (from day one)

Log every touch in **Master_Client_List.xlsx → Time Log** (date, client, staff, activity, minutes). The Clients sheet totals human minutes month to date per client, and the target is under 240. Keep the activity names fixed so we can see where time goes (SWMS drafting vs chasing vs onboarding).
