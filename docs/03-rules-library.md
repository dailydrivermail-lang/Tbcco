# Rules library v1: plumbing, ACT and NSW

**Source of truth:** `rules/rules_library.csv`, 60 rules. **Review copy for Ivana:** `rules/Rules_Library_REVIEW.xlsx` (colour-coded by confidence, with an `ivana_status` dropdown).

## Structure

| Column | Meaning |
|---|---|
| `rule_id` | `P-` person, `B-` business, `S-` subcontractor, `J-` job; then the jurisdiction; then a number. Never reuse an ID. |
| `jurisdiction` | ACT, NSW or ALL (both: harmonised WHS law, Commonwealth law, or market practice) |
| `trigger_roles` | Roles from the People sheet that the rule applies to (semicolon list) |
| `condition` | Blank = always applies to those roles. `flag:<People field>=Y` and `biz:<Business field>>0` are machine-checked. Any other text is a human question, which the engine lists under "Confirm with client". |
| `evidence_code` | Credential or insurance code that satisfies the rule (`A\|B` = either). `DOC:` codes are policy or document evidence (checked in the Phase 2 gap analysis). |
| `obligation_type` | **Statutory** / **Code of practice / regulator guidance** / **Contractual / market practice**. Client documents must never present a market-practice item as the law. |
| `source_instrument`, `source_provision`, `source_url` | Where the rule comes from |
| `confidence` | **A** checked against an official page while building v1 · **B** well established, but confirm the section number and wording · **C** uncertain: don't rely on it yet |
| `ivana_status` | Not reviewed → Verified / Verified with changes / Rejected / Needs research |

The engine labels every gap from a rule Ivana hasn't verified **PENDING LEGAL REVIEW** in the internal review report. The client email only says "we don't have X on file". It states a fact about our records, not a legal conclusion.

## Coverage (v1)

- **Trade licensing:** ACT plumber, drainer, gasfitter and gas appliance worker classes, plus the backflow endorsement (Construction Occupations (Licensing) Act 2004 / Regulation 2004, Access Canberra). NSW contractor licence, qualified supervisor certificate and tradesperson certificate by category, with the immediate-supervision rule for unlicensed workers (Building Commission NSW).
- **WHS training:** White Card; **ACT-mandatory asbestos awareness 11084NAT and silica 10830NAT**; HRWL (LF, WP, scaffolding) with the PCBU duty to sight evidence (r 85); first aid and CPR; confined space; heights; EWP under 11 m; ARCtick; restricted electrical.
- **Business:** workers' comp (ACT and NSW); NSW s 175B subcontractor statements; ACT Leave portable LSL; NSW LSL levy; HBCF; PL (market practice); refrigerant trading authorisation; the core WHS system duties (s 19, s 27, Part 3.1, consultation, first aid r 42, emergency plan r 43, notifiable incidents s 35-39, chemicals r 344/346, electrical testing, audiometry r 58, plant, psychosocial).
- **Subcontractors:** PL, WC, personal accident; ACT deemed-worker exposure.
- **Jobs:** SWMS for high-risk construction work (r 291, r 299-303); principal contractor ≥ $250k (WHS management plan); asbestos check for pre-2004 buildings and the ACT loose-fill register; confined space permits; Before You Dig; silica; hot works; NSW and ACT plumbing and gas compliance paperwork.

## Ivana's verification queue (in priority order)

1. **S-ACT-03, ACT deemed workers.** This affects workers' comp advice for every ACT client with subbies.
2. **P-NSW-01/02/03 and automatic mutual recognition.** Can an ACT licensee work in NSW under AMR, and is notification needed? Today the engine flags these workers as a gap.
3. **P-ACT-08, silica declared occupations.** Does NI2023-299 cover plumbers, drainers and labourers?
4. **P-ACT-07, asbestos instrument.** Confirm the current instrument number and that it applies to all construction workers.
5. **P-ALL-12, restricted electrical.** Common in hot water replacement businesses.
6. **P-ALL-01, the 2-year White Card rule.** Confirm in the ACT reg and the NSW 2025 reg. If confirmed, the engine needs a "last construction work date".
7. The remaining **C** rules: P-ACT-05, P-ACT-06, P-ACT-09, B-ACT-01, B-NSW-04, B-NSW-05, J-ALL-05, J-ALL-06, J-NSW-01, J-NSW-02, J-ACT-01.
8. **Every B rule:** confirm section numbers in the **NSW WHS Regulation 2025** (which replaced the 2017 Regulation from 22 August 2025) and in the ACT WHS Regulation 2011.

## Change control

1. Edit the CSV in a branch, with a one-line reason in the commit message.
2. Run `python -m pytest` (it checks codes, roles and that sources exist) and `python -m engine.build_templates`.
3. Ivana sets `ivana_status` and initials in `ivana_notes`.
4. A law change triggers the annual WHS policy review for affected clients (Phase 2: a list of rules changed since each client's last pack).

## Sources checked while building v1

- [NSW WHS Regulation 2025 (in force)](https://legislation.nsw.gov.au/view/whole/html/inforce/2025-10-03/sl-2025-0440) · [SafeWork NSW legislation page](https://www.safework.nsw.gov.au/legal-obligations/legislation) · [Clayton Utz: key changes](https://www.claytonutz.com/insights/2025/november/work-health-and-safety-regulation-2025-nsw-key-changes)
- [WorkSafe ACT: asbestos awareness training](https://www.worksafe.act.gov.au/health-and-safety-portal/safety-topics/dangerous-goods-and-hazardous-substances/asbestos/asbestos-awareness-training) · [WorkSafe ACT: accredited training alert](https://www.worksafe.act.gov.au/health-and-safety-portal/safety-alerts/asbestos-awareness-accredited-training)
- [WorkSafe ACT: silica training](https://www.worksafe.act.gov.au/health-and-safety-portal/safety-alerts/crystalline-silica-exposure-prevention-training) · [Fines for silica training failures](https://www.worksafe.act.gov.au/health-and-safety-portal/safety-alerts/fines-for-pcbus-failing-to-meet-silica-training-requirements) · [ACT silica declaration NI2023-299](https://www.legislation.act.gov.au/DownloadFile/ni/2023-299/current/PDF/2023-299.PDF)
- [ACT plumber, drainer and gasfitter licence classes](https://www.planning.act.gov.au/professionals/regulation-and-responsibilities/construction-licences/accordion-content/plumber-drainer-and-gasfitter-licence) · [ACT construction licences](https://www.planning.act.gov.au/professionals/regulation-and-responsibilities/construction-licences)
- [NSW plumbing, draining and gasfitting licensing](https://www.nsw.gov.au/business-and-economy/licences-and-credentials/building-and-trade/plumbing-draining-and-gasfitting) · [Building Commission NSW regulatory intent](https://www.nsw.gov.au/departments-and-agencies/building-commission/about-us/statements-of-regulatory-intent/plumbing-draining-and-gasfitting) · [NSW automatic mutual recognition](https://www.nsw.gov.au/business-and-economy/licences-and-credentials/automatic-mutual-recognition/occupations/plumbing-draining-and-gasfitting)
- [HIA: subcontractor statements](https://hia.com.au/resources-and-advice/managing-your-business/working-with-contractors/articles/subcontractors-statement) · [ACT Leave: construction employers](https://actleave.act.gov.au/construction/employers/)
- [Model WHS Regulations (1 July 2024)](https://www.safeworkaustralia.gov.au/sites/default/files/2024-07/model-whs-regulations-1_july_2024.pdf) · [Safe Work Australia: HRWL classes](https://safeworkaustralia.gov.au/safety-topic/managing-health-and-safety/licences/high-risk-work-licence-classes)
