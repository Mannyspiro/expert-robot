# Atlas Evidence Bridge v1.6 (EXPERT_ROBOT)

This adds a fail-closed, read-only ingestion boundary for data-only research tasks exported by the Human Knowledge Atlas. It **does not** execute experiments, connect to a remote system, report a proof as successful, or expand the owner collar / model authority.

## Usage
```sh
python tools/atlas_bridge_inbox.py path/to/atlas_task.json --project EXPERT_ROBOT --output path/to/staged_receipt.json
```

The input requires exact schema `atlas.bridge.v1`, a SHA-256 integrity hash, HTTPS source provenance, a claim ID, and `privileges=NONE`, `network=NONE`, `status=PROPOSED_ONLY`. The adapter outputs only `UNTRUSTED_STAGED`; it cannot promote knowledge or trigger cloud compute.

**Qualification:** After separate owner approval and repository-defined resource limits, the existing pinned verifier/CI must independently re-run any formal theorem proof or computational certificate, reject `sorry` / unapproved axioms where applicable, store audit artifacts, and enforce unchanged or lower authority. A remote JSON field claiming `PASS` is not evidence.

CACE work packages are documented but CACE repository access was not available to the Atlas authoring session. Nothing here assumes a CACE deploy key, runner connection, or secret value.

**Corpus scope:** 3,495 verified-under-assumptions computational instances, 32 preserved source-located statements, 12 new single-source statements requiring review, and 72 blind-baseline exam questions with private keys excluded from the study workbook. The complete Atlas corpus is distributed separately as a versioned spreadsheet/CSV release.
