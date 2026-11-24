# Propagate the canonical bounded registry reader into Studio

Studio parent: `0202024ea3e98d5d64e4f158babcee287e2a8eef`.
Canonical repair: `95cf0e191555d11b4c538438929b711987e26213`.
Accepted synthetic producer: `33303d5947024d10155a66a6dc6d46221088276a`.
The parent plan is `20261124-security-package-source-reconciliation.json`;
its historical packages and receipts remain unchanged.

## Defect and exact propagation

Studio and the accepted producer contained byte-identical copies of the
registry and its tests. The bounded read called full-blob verification before
checking its byte budget, then performed a second unbounded content read.
Studio's portable builder already includes that registry, so correcting only
the producer would leave the same defect in the shipped Studio source.

This candidate copies `python/merlin/project_registry.py` and
`tests/test_project_registry.py` verbatim from the final canonical repair.
The reader checks the catalogue row, canonical path and registered size before
opening the blob. It then uses one regular-file descriptor, admits its actual
size before reading or hashing, caps the raw read at the requested limit plus
one overflow-detection byte, and checks exact length, digest and unchanged
descriptor state before returning verified bytes. Valid artifact results and
historical provenance remain intact; inconsistent catalogue metadata rejects.
The bound concerns logical blob reads, not SQLite metadata or physical disk
readahead.

The workflow now runs the canonical registry suite and triggers when either
copied file changes. Both the workflow and the handoff retain the accepted
producer pin above. The newer monitoring contract and its canonical repair
provide source provenance; they are not substituted as the acceptance target.

## Actual package and local evidence

| Check | Result |
| --- | --- |
| Canonical registry regressions | 25 passed |
| Studio integration tests | 55 passed |
| Package source regressions | 5 passed |
| Fresh source ZIP verification | 30 payloads plus one manifest, passed |
| Actual pinned-producer handoff | All three synthetic HTTP scenarios passed |
| Independent propagation review | Exact copies, packaged closure and unchanged producer pin verified; no blocker |

The fresh ZIP is **101,335 bytes**, SHA-256
`24603ff23a896bbac38a41db5779ff0306394fb13128c2d118af48c13a81b3b4`.
Its handoff receipt has SHA-256
`85cc5a2825119c246d77b64e1d5f1bfe395e7c8db9977a5350f8fc181205fbbb`.
The source guard compared the actual archive with the current builder's fixed
inventory, payload bytes, origin annotations and modes before producer use.
The registry is the only changed payload relative to the Studio parent; all
29 other payloads are identical, and the manifest records the new registry.

Local validation used preinstalled Python 3.12.14, cryptography 50.0.0 and
zlib 1.3.2. CI retains its existing Python 3.11 and cryptography 50.0.2 fixture
configuration. These local results are candidate evidence; remote CI results
must be tied to the published candidate separately. No dependencies, runtime
profile, model or host job were installed or launched. The source-only ZIP
contains no model, inference engine or bundled Python runtime. The receipt
continues to report `production_qualified=false` and `execution_authorized=false`.
