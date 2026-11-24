# SWMS generator v1

Turns a job on the client's **Jobs** sheet into a site-specific SWMS PDF, checks the assigned workers' licences and tickets against the work, and **won't issue until a named person has reviewed it**.

## Flow (target: within 24 hours of the request)

```
Client: portal "Request a SWMS" (or email/phone)  ──►  Staff inbox: "Add to Jobs register"  (status Requested, clock starts)
   ──►  Staff: assign workers + plant on the Jobs sheet
   ──►  Generate draft      python -m swms draft --client-dir … --job J0002     (or the portal button)
        → 04_Jobs/J0002_…/Drafts/J0002_SWMS_v1_DRAFT.pdf + .json, status "In review", Audit Log row
   ──►  Review: work through the checklist on the last page; fix the register and re-draft as needed
   ──►  Issue               python -m swms issue --client-dir … --job J0002 --reviewer "Ivana"   (or the portal button)
        → 04_Jobs/J0002_…/Issued/J0002_SWMS_v1.pdf, status "Issued", Reviewed by, SWMS issued at, Audit Log row
   ──►  Client downloads it from the portal (Jobs & SWMS) and workers sign on at the site
```

The Jobs sheet's **SWMS turnaround (hrs)** = issued at − requested at, so we measure the 24-hour promise from day one.

## What goes into a SWMS

| Section | Source |
|---|---|
| PCBU, site, scope, dates, principal contractor, plant | Business and Jobs sheets |
| r 291 high-risk construction work ticks | The job's hazard ticks, mapped by `swms/model.py` (`HRCW_MAP`) |
| Work steps → hazards → initial risk → **controls in hierarchy order** → residual risk → responsible person | Task template (chosen from the scope wording) plus a hazard module for each ticked hazard, from `swms/library/` |
| People, licences, competencies | Assigned workers' Credentials, checked **at the job's start date** (and flagged if they expire before the end date) |
| PPE, references, emergency and notifiable-incident arrangements, review triggers, worker sign-on sheet | Library and fixed text |
| **Reviewer checklist** (drafts only) | Blockers and checks raised while building |

## Blockers vs checks

**Blockers** stop issue: no workers assigned or an unknown worker; missing site, scope or start date; a worker without a White Card (or other mandatory ticket) at the start date; **no assigned worker holding a current licence for the trade in that state** (ACT plumber, drainer or gasfitter; for NSW, the certificate's **categories** must cover the work); forklift listed without HRWL LF.

**Checks** must be confirmed by the reviewer: Before You Dig, trench support method, the asbestos register and the 10 m² / friable threshold, the ACT loose-fill register, traffic management, who isolates electrical, an ACT-only licensee on an NSW job (mutual recognition), EWP class, the earthmoving operator's VOC, first aider, $250k+ principal contractor, and generic steps when the scope didn't match a template.

Override (CLI only, logged in the SWMS JSON and the Audit Log): `--override "reason"`. Use it rarely.

## Tailoring a draft

Issue publishes **exactly the latest draft** a reviewer looked at. To tailor wording, steps or controls, edit the draft's `.json` (same folder as the PDF), then issue. If you fix the register (assign workers, add a licence), **re-draft** instead. Each re-draft becomes v2, v3, and so on.

## Library (`swms/library/`)

- `tasks.yaml`: plumbing task templates (sewer/stormwater drainage, hot water, gasfitting, roof plumbing, general) chosen by keywords in the scope; trade licence codes per state; regulator contacts.
- `hazards.yaml`: modules for base site work (always), trench over 1.5 m, height over 2 m, confined space, live electrical, asbestos, silica, hot works, gas lines, traffic and mobile plant. Each has steps, controls (E/S/I/Eng/A/PPE), PPE, competencies, Code of Practice references and reviewer flags.

**Status: not yet reviewed by Ivana.** The controls are generic good practice drawn from the cited Codes of Practice. Before the first pilot SWMS goes out, Ivana should review `hazards.yaml`, especially the asbestos thresholds, the confined space regulation numbers, the trench support wording, and the regulator phone numbers. `tests/test_swms.py` checks the library's structure on every change.

## Known limits (v1)

- One trade (plumbing) and two states (ACT, NSW).
- The library is deterministic: no AI-written content, so nothing is invented. A later version can have Claude propose job-specific steps from the scope for the reviewer to accept.
- Tailoring is done by editing JSON. An edit screen in the portal is the natural next step.
- Some head contractors require their own SWMS template. Note it on the request; v1 produces our format only.
