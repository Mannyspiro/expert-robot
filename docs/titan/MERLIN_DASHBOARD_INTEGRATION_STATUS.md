# Merlin Dashboard Integration Status

**Status:** read-only projection contract and export workflow implemented; live dashboard write/read integration pending target discovery.

## Implemented

- `docs/titan/TITAN_MERLIN_REGISTRY_CONTRACT_v1.json` defines the canonical record fields and non-promotion invariants.
- `scripts/export_titan_merlin_projection.py` converts checked-in Titan evidence records into a read-only projection.
- `tests/titan_merlin_projection_smoke.py` checks that the export contains records, preserves research-only status and never grants promotion authority.
- `.github/workflows/titan-merlin-projection.yml` executes the export on Avrea and publishes a 30-day workflow artifact.

## Verified projection run

- Workflow run: 42087869863
- Conclusion: success
- Artifact: `titan-merlin-projection-42087869863`
- Artifact SHA-256: `42c315e75e4b0ef186cf189b5308793d075c748e37ab00c8f26bf61715264ee3`
- Projection JSON SHA-256 after extraction: `d058a5fdb49d4bda5a50a4b432480555d18392475baeab27dde0a332a8161eb5`
- Records: 2 (one contract-smoke record and one provider-inventory record)

The provider-inventory record is explicitly `blocked` for PQC testing, and both records remain `research_only`, unsigned, and without promotion authority.

## Live dashboard boundary

The connected GitHub repositories and Vercel projects inspected in this work did not expose a Merlin-named dashboard repository or Vercel project. No dashboard endpoint or write API has been inferred or fabricated. The projection artifact is therefore a validated handoff format, not a claim that Merlin's live dashboard has been updated.

To finish the live connection, the exact Merlin dashboard repository or its canonical registry API must be identified. Once identified, the integration should be read-only from the dashboard perspective: ingest canonical records, render evidence and verification status, and never accept dashboard edits as proof or promotion authorization.
