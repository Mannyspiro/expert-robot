# Merlin Dashboard Integration Status

**Status:** read-only projection contract and export workflow implemented; live dashboard write/read integration pending target discovery.

## Implemented

- `docs/titan/TITAN_MERLIN_REGISTRY_CONTRACT_v1.json` defines the canonical record fields and non-promotion invariants.
- `scripts/export_titan_merlin_projection.py` converts checked-in Titan evidence records into a read-only projection.
- `tests/titan_merlin_projection_smoke.py` checks that the export contains records, preserves research-only status and never grants promotion authority.
- `.github/workflows/titan-merlin-projection.yml` executes the export on Avrea and publishes a 30-day workflow artifact.

## Verified projection run

- Workflow run: 42092648922
- Conclusion: success
- Artifact: `titan-merlin-projection-42092648922`
- Artifact SHA-256: `009680c2c3b39a986f09bbac674b1cc74f6095ff76cae9f6e8068fe42bb799d9`
- Projection JSON SHA-256 after extraction: `d493270314e3abc699c8efe10db105aefb45a4c62577b1ee1d9c556c25b5d46a`
- Records: 4 (contract smoke, provider inventory, FIPS 203/204/205 ACVP run, and CACE independent verification)

The provider-inventory record is explicitly `blocked` for PQC testing, and both records remain `research_only`, unsigned, and without promotion authority.

## Live dashboard boundary

The connected GitHub repositories and Vercel projects inspected in this work did not expose a Merlin-named dashboard repository or Vercel project. No dashboard endpoint or write API has been inferred or fabricated. The projection artifact is therefore a validated handoff format, not a claim that Merlin's live dashboard has been updated.

To finish the live connection, the exact Merlin dashboard repository or its canonical registry API must be identified. Once identified, the integration should be read-only from the dashboard perspective: ingest canonical records, render evidence and verification status, and never accept dashboard edits as proof or promotion authorization.


The latest projection includes the completed Avrea ACVP run `42090360334`:
54/54 selected standardized parameter-set vectors passed (9 ML-KEM, 9 ML-DSA,
36 SLH-DSA), with zero failures. The NIST ACVP source commit is pinned to
`b121fee031dc65d32c96f4109a42a10dacbe2076`; its upstream commit is unsigned,
which is recorded rather than overstated.
