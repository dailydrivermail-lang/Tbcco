# Trade compliance service: back end

The internal tooling behind a managed WHS and licensing compliance service for Australian trade businesses (10-50 staff).
Clients send us raw inputs; we return audit-ready registers, alerts, SWMS and compliance packs. **We sell the service, not this software.**

**Phase 1 scope (decided):** plumbing (incl. drainage and gasfitting) · **ACT + NSW** · Microsoft 365 (SharePoint/OneDrive in the Australian region, Excel, Forms, Outlook).

## Principles

- **Human in the loop.** The engine only drafts. Every client-facing item is reviewed and logged in the Audit Log before it goes out.
- **Cite or flag.** Every rule carries its source and a confidence grade. Nothing is presented as law until Ivana has verified it.
- **No client data in Git.** Client data lives in SharePoint; this repo holds tooling only.
- **Cheap and modular.** Excel + Python + Claude. `engine/schema.py` is the one data model, so moving to SharePoint Lists or a database later is a port, not a rewrite.
- **Measure human minutes per client from day one** (Time Log).

## What's here

| Path | What |
|---|---|
| `docs/01-folder-structure.md` | SharePoint layout, naming, access model |
| `docs/02-data-model.md` | Every register and field (generated from `engine/schema.py`) |
| `docs/03-rules-library.md` | How the rules library works, Ivana's verification queue, sources |
| `docs/04-expiry-engine-runbook.md` | Daily routine, new client, alert logic, RAG |
| `docs/05-client-portal.md` | Client portal: features, legal-review gate, running locally, Azure deployment, security |
| `docs/06-swms-generator.md` | SWMS flow, blockers vs checks, tailoring, library status |
| `rules/rules_library.csv` | **60 rules** for plumbing, ACT/NSW, with sources and confidence (source of truth) |
| `rules/Rules_Library_REVIEW.xlsx` | Ivana's review copy |
| `intake/onboarding_questionnaire.md` | Microsoft Forms build spec (onboarding + SWMS request), channels, recurring intake |
| `intake/People_and_Licences_Intake.xlsx` | Client-facing bulk sheet: people, licences, subbies, chemicals, plant |
| `intake/claude/extract_document_prompt.md` | Claude prompt: licence or certificate image → JSON record |
| `templates/Client_Register_TEMPLATE.xlsx` | Per-client register: 10 sheets, dropdowns, live expiry status, colour coding |
| `templates/Master_Client_List.xlsx` | Ops workbook: Clients (RAG, minutes), Time Log, Audit Log |
| `engine/` | `schema.py` · `build_templates.py` · `new_client.py` · `intake_import.py` · `expiry_engine.py` |
| `swms/` | **SWMS generator**: library (`library/tasks.yaml`, `library/hazards.yaml`), model, PDF renderer, CLI. See `docs/06-swms-generator.md` |
| `portal/` | **Client portal** (Flask): client dashboard, registers, uploads, SWMS requests, reports; staff overview and inbox. See `docs/05-client-portal.md` |
| `deploy/` | Static demo of the portal for Cloudflare Pages (`build_static_demo.py`, output in `deploy/site/`). See `deploy/README.md` |
| `examples/make_demo.py` | Builds a fictional client end to end (scaffold → intake → engine → drafts) |

## Quick start

```bash
pip install -r requirements.txt
python -m engine.build_templates      # regenerate templates + data-model doc
python examples/make_demo.py          # demo clients in examples/demo/
python -m swms draft --client-dir examples/demo/C000_Demo-Plumbing-Pty-Ltd --job J0002
python -m portal.run --demo           # portal at http://127.0.0.1:8080 (demo logins printed)
python -m pytest -q                   # 36 tests
```

## Roadmap

- **Phase 1 (weeks 1-4):** ✅ rules library v1 · ✅ data model + folder structure · ✅ intake (Forms spec, bulk sheet, Claude extraction) · ✅ register + expiry engine + draft alerts · ✅ SWMS generator v1 (library pending Ivana's review) · ⏭ Ivana verifies the rules · ⏭ 3 pilot clients
- **Phase 2:** quarterly pack builder (PDF), chemical/incident registers in use, ops dashboard, gap analysis vs head contractor requirements
- **Phase 3:** hardening, ✅ client portal v1 (local; Azure Australia East to go live), case study template, broker renewal pack
- **Later:** asbestos removal rules, more states, Plus tier (Xero read-only), automated Claude extraction via the API
