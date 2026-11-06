# Arizona policy-form research pipeline

## Key discovery

Arizona DIFI exposes public property-and-casualty form, rate and rule filings through SERFF Filing Access. Search by business type, type of insurance and insurer. The public access portal states that Arizona filings become viewable upon disposition, subject to public-record exceptions. DIFI publishes separate filing checklists for homeowners (TOI 4.0), personal auto (TOI 19.0) and workers compensation (TOI 16.0).

## Ingestion contract

For each filing, retain:
- SERFF tracking number and disposition date;
- exact issuing insurer legal entity and NAIC company code;
- state, line and TOI/sub-TOI;
- form/endorsement number, edition and effective date;
- filing role (new product, form, rate or rule);
- source URL, retrieval timestamp and original file bytes;
- SHA-256 of each original document;
- extracted clause text with PDF page and section coordinates;
- parser name/version and extraction log;
- reviewer decision and CACE receipt.

Do not treat a checklist as a policy form. Do not treat a filing summary as the actual contract. A filing page being public does not mean every attached document is public or reusable; respect access terms and copyright restrictions.

## First Arizona filing batches

1. HO-3, HO-4, HO-6 and manufactured-home forms and endorsements.
2. Private passenger auto base forms, UM/UIM selections, household-member exclusions and valuation/repair endorsements.
3. Workers compensation forms and rate/rule materials.
4. BOP and commercial package forms, then CGL and commercial auto after confirming the exact SERFF TOI/sub-TOI taxonomy.

## Primary regulator sources

- DIFI SERFF Filing Access: https://difi.az.gov/sfa
- DIFI public filing search instructions: https://difi.az.gov/prr-insurance-rate-and-form-filings
- DIFI P&C form filing checklists: https://difi.az.gov/property-casualty-forms
- Arizona SERFF portal: https://portals.naic.org/serff-filing-access?state=AZ
- 2026 DIFI homeowners form checklist: https://difi.az.gov/sites/default/files/2026-03/PFC_4.0HO_FF_Checklist_0326_%281%29.pdf

## Merlin verification gate

The new `merlin.verifier` checks source snapshot hashes, exact quoted spans, cited source IDs, artifact digests, acceptance criteria and test logs. It deliberately does not equate a matching quotation with semantic truth. A separate reviewer must assess whether the source actually entails the claim, and that review must bind the exact claim-set digest. CACE should authenticate the reviewer identity and sign/verify the final receipt before any finding is promoted to verified knowledge.
