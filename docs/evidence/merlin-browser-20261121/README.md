# Merlin browser evidence checkpoint — 2026-11-21

The published browser source and the actual OCI inventory are retained here.
Native installation, rendering, Merlin caller access and restart acceptance are
**pending** at this checkpoint. No native result has been inferred or inserted.

## Exact identities

| Evidence | Identity | What it establishes |
| --- | --- | --- |
| Product draft PR | [expert-robot #193](https://github.com/Mannyspiro/expert-robot/pull/193) | Published source and 33 local contract/integrity tests. |
| Product commit | `8e2f1d69371d5b4f7e01e3bbd5aa02a666ddd506` | Exact 12 additions; 395 existing blobs preserved. |
| Product tree | `20b0fdf671736fc9cb9eb3ae9fd7f0908538bf8e` | Published tree identity checked in the retained source review. |
| Product freeze | `349bb4f0898c3ef7cd326a7aa5f7c52390f42e2da571d9b8f1e4568b12aafacb` | Source/dependency/test/doc file identities; native gate remains separate. |
| OCI inventory | [run 44931107501, attempt 1](https://github.com/morganaspim/Cace-app/actions/runs/44931107501) | Successful read-only native host inventory and 12 controller tests. |
| Inventory workflow commit | `72efac38891be49eb538fd09dd2319c6d16a7e01` | Exact inventory controller/workflow source. |
| Inventory artifact | `14717573208`, 13,953 bytes | Original complete Actions ZIP, retained byte-for-byte. |
| Inventory ZIP SHA256 | `460c4871efaaa324f64be83e3cff04f664720f28e6ba9e2766a7e79429fd2c51` | Matches the retained GitHub artifact API digest. |

The inventory observed Oracle Linux 9.8 aarch64, Python 3.9.25, bubblewrap 0.6.3
and systemd 252. The unprivileged user-namespace probe passed. Chromium was not
installed, and Playwright was absent from the isolated system-Python path at
inventory time. The receipt explicitly records no browser launch, no host
configuration change, no private-state access and zero model calls.
These statements describe that timestamped inventory, not a later installation.
See [the exact inventory](inventory-44931107501/artifact/inventory.json) and
[the root's 12-check acceptance](inventory-44931107501/root-review.json).

## Retained files

- `inventory-44931107501/artifact.zip` is the unmodified original archive.
- `inventory-44931107501/api-evidence.json` preserves the complete retrieved
  run, job, artifact and request metadata.
- `inventory-44931107501/artifact/` preserves all nine archive members exactly,
  including source, workflow, logs and test output.
- `source/published-source-review.json` is the unmodified root review of the
  published product commit and its additions.
- `evidence-index.json` identifies observed coverage and the exact evidence
  still required for native acceptance.
- `provenance-manifest.json` records each retained/derived file's size, SHA256
  and origin. It excludes its own bytes to avoid a circular digest.

The local 33-test evidence is already part of the product commit under `local/`;
it is referenced rather than duplicated in this overlay. Synthetic page tests
cannot establish real Chromium rendering or an installed Merlin service.

## Native continuation

Append the actual native bootstrap ZIP, API metadata, full raw bounded evidence
and independent review under `bootstrap-RUN_ID-attempt-RUN_ATTEMPT/` once available.
Retain failed attempts alongside successful ones. Update the evidence index and
production checkpoint only from actual receipts: package/runtime identities,
real sandboxed JavaScript and screenshots, public acquisition episodes, UID 982
submit/read calls, readback after restart, and preserved private runtime/provider
state. The remaining model-generation budget is not increased by this work.
No capability qualification, learned policy or general self-improvement is
claimed by either inventory or source publication.
