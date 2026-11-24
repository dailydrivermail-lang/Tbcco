# Claude prompt: extract a compliance document into a structured record

**Use:** attach one or more files from a client's `01_Intake_Inbox` (licence photos, White Cards, statements of attainment, certificates of currency) to Claude, paste the prompt below, and save the JSON reply as `extractions_YYYY-MM-DD.json` in the client's `_system` folder. Then run:

```
python -m engine.intake_import extraction --client-dir ".../C001_…" --file ".../_system/extractions_2026-11-24.json"
```

Rows land as **Unverified**. A reviewer checks each one against the image and, for licences, the public register (Access Canberra or Service NSW licence check), then sets Verification.

**Privacy:** only use Claude under a commercial agreement that doesn't train on our data. Don't paste TFNs, bank details or medical information. Redact them if they appear on a document.

---

## Prompt (copy from here)

You are extracting data from Australian construction-industry compliance documents for a compliance register.
Return **only** JSON matching the schema below. Rules:

1. **Never guess.** If a field isn't clearly legible on the document, set it to `null` and add a note to `flags_for_reviewer`.
2. Dates: output `YYYY-MM-DD`. Australian documents are day-first (`05/03/2027` is 5 March 2027).
3. One record per credential or policy. A card showing several licence classes (e.g. HRWL LF and WP) gives **one record per class**.
4. `credential_type` must be one of these codes, otherwise `OTHER`:
   ACT_PLUMBER, ACT_DRAINER, ACT_GASFITTER, ACT_GAS_APPLIANCE, ACT_BACKFLOW_END, NSW_CONTRACTOR_PDG, NSW_QS_PDG, NSW_TRADE_PDG, WHITE_CARD, ACT_ASB_AWARE (11084NAT), ACT_SILICA (10830NAT), ACT_ASB_ACM, HRWL_WP, HRWL_LF, HRWL_SB, HRWL_DG, HRWL_OTHER, FIRST_AID (HLTAID011), CPR (HLTAID009), CONFINED_SPACE, WORK_AT_HEIGHTS, GAS_TEST_ATMOS, ARCTICK_RHL, ELEC_RESTRICTED, TEST_TAG, EWP_YELLOW, DRIVER_LICENCE.
5. `policy_type` must be one of these codes, otherwise `OTHER`: PL, WC_ACT, WC_NSW, PI, CONTRACT_WORKS, MOTOR, TOOLS, PERSONAL_ACCIDENT, HBCF, NSW_SUBBIE_STMT.
6. White Cards and statements of attainment usually have no expiry: set `no_expiry: true`. First aid (HLTAID011) and CPR (HLTAID009) statements show a completion date, not an expiry. Put that date in `issue_date`, leave `expiry_date` null, and flag "expiry to be set by policy: first aid 3 yrs, CPR 12 months".
7. For 11084NAT or 10830NAT, record the RTO name in `issuer` and its RTO number in `endorsements` if shown. WorkSafe ACT only accepts approved RTOs.
8. Flag anything suspicious: expired on arrival, name mismatch between documents, edited-looking images, a missing photo on a photo card, a certificate of currency that doesn't name the insured entity, or a policy period that doesn't cover today.
9. `confidence`: High (all key fields clearly legible), Medium (one key field unclear), Low (photo poor or document type uncertain).

```json
{
  "records": [
    {
      "record_type": "credential",
      "source_file": "IMG_2041.jpg",
      "holder_name": "Sam Example",
      "credential_type": "ACT_PLUMBER",
      "jurisdiction": "ACT",
      "number": "2012345",
      "class_or_categories": "Sanitary plumber",
      "endorsements": null,
      "issuer": "Access Canberra",
      "issue_date": "2024-12-19",
      "expiry_date": "2026-12-19",
      "no_expiry": false,
      "confidence": "High",
      "flags_for_reviewer": []
    },
    {
      "record_type": "insurance",
      "source_file": "CoC_PlaceholderDrainage.pdf",
      "insured_name": "Placeholder Drainage Pty Ltd",
      "policy_type": "PL",
      "insurer": "Example Insurer Ltd",
      "policy_number": "PL-777",
      "limit_amount": 20000000,
      "period_start": "2025-11-21",
      "expiry_date": "2026-11-21",
      "interested_parties": null,
      "confidence": "High",
      "flags_for_reviewer": ["Policy expired 3 days before upload"]
    }
  ]
}
```

---

## Later (Phase 2): automate it

Once the prompt is stable across about 50 real documents, a small script can call the Claude API with the same prompt and a JSON schema (structured outputs), triggered by Power Automate when a file lands in `01_Intake_Inbox`. Keep the human verification step regardless.
