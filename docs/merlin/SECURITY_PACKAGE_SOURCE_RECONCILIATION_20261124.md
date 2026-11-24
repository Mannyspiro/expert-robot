# Bind security acceptance to the current package sources

Parent Studio: `d8bb406b633c8271dcfdd42a3aee3cf31cd562f3`, PR #229.
Pinned producer: `33303d5947024d10155a66a6dc6d46221088276a`, PR #228.
This is a child of `20261124-security-active-lineage.json`. Earlier receipts
and source checkpoints remain unchanged.

## Observed mismatch and its scope

The parent Studio's three workflows passed on attempt one. Its security-review
[run 45394416813](https://github.com/Mannyspiro/expert-robot/actions/runs/45394416813)
passed 55 tests and all three actual producer/package HTTP scenarios. The
downloaded artifact nevertheless had a different package identity from the
earlier local archive:

| Evidence | Earlier local package | Exact parent CI package |
| --- | --- | --- |
| ZIP bytes | 100,495 | 100,572 |
| ZIP SHA-256 | `e6954bcc495e32f137061b55ede260cca2d6878fcb2dc12b1bb7ae78214e141e` | `9d179b5f52f9e7ee72b7bf88f024f5480d8d4c4902c547c8e78c6525ebf7d520` |
| Handoff receipt SHA-256 | `e37e8efd6cae145d6865ea6f1f150289fb623754c577c84709b325742331f9bc` | `f6d970bbd6a2b7512bc65c375e878214879d72158e723c4d5b53751e553708b5` |

Every decompressed ZIP member was compared. Exactly two differed:
`tests/test_security_review.py` and its corresponding manifest entry. The
earlier local package preceded the final 918-byte truncated-prefix regression
addition. All other 29 members, including all runtime code, were byte-identical.
The complete current CI payload also matched the canonical builder's 30
source inputs in the published checkout. The two receipts differed only in
`package_sha256`; all scenario results and snapshot digests matched.

The observed cause was stale input bytes, not a compression difference. The
builder's separate reproducibility condition still requires identical inputs
and Python/zlib. The earlier archive correctly passed its own manifest check;
that check establishes internal consistency, not equality to the intended
source checkout. The acceptance entry point lacked the latter comparison.

## Acceptance repair

Before package extraction or producer execution, the handoff now verifies the
source-only ZIP against the current checkout's canonical builder inventory.
It reuses `build_portable.collect_sources()` and the repository verifier; it
does not maintain a second list of shipped files.

The additional boundary compares the exact archive root and inventory, every
payload byte, builder-defined file modes and source-only metadata, and each
manifest origin annotation against the canonical mapping. Manifest-provided
origins are never used as filesystem paths. A self-consistent old package,
extra payload, altered source annotation or incompatible source-only contract
fails before any producer child runs.

This verifies equality to the selected checkout. It does not independently
authenticate the checkout's origin, qualify a model/runtime or grant execution
authority. Published source and actual CI checkout identities continue to be
recorded separately, with complete-tree comparison where CI uses a merge ref.

The combined handoff receipt advances to `merlin-security-handoff-evidence/3`
and explicitly includes `package_source_verified=true`. Historical schema-v2
receipts remain valid records of their narrower checks and are not rewritten.
The three synthetic scenarios and their non-authorizing scope remain unchanged.

## Discriminating verification and remaining scope

The new regression exercises a package whose changed payload and recomputed
manifest are internally consistent. The repository's integrity verifier must
accept it, while the new source comparison must reject it. The actual older
local archive provides a second concrete stale-file case. A freshly built
source-only package must match the current sources and complete all three
pinned-producer handoffs.

The accompanying parent-linked plan records the exact targeted test results,
old-archive rejection, corrected package identity and complete new receipt.
Final-candidate CI results belong to the publication that contains this guard;
the parent CI run above is retained as parent evidence only.

Local repair validation passed five targeted tests in 0.173 seconds. The
actual older ZIP passed the baseline verifier and was then rejected by the
new handoff before producer use. The fresh archive is 100,572 bytes and has
the exact parent CI package hash `9d179b5f52f9e7ee72b7bf88f024f5480d8d4c4902c547c8e78c6525ebf7d520`.
All three actual pinned-producer handoffs passed in 3.285 seconds. The new
receipt hash is `739b43f86d09d61bdf14f469ddcaeadf3ac5643ba660a85184f455c6abef10ba`;
its only semantic changes from the parent CI receipt are the schema version
and explicit source-verification field. No packaged runtime or test payload
was changed by the acceptance-boundary repair.

Operational Titan key/current-anchor custody, a reviewed isolated monitoring
profile and authenticated private-host release qualification remain open. This
repair addresses artifact/source reconciliation at the acceptance boundary.
It changes no application runtime behavior or deployment authority.

Method: treat archive integrity, equality to intended source, observed runtime
behavior and production authority as independent evidence dimensions. The
negative case prevents a passing behavioral scenario or an internally valid
manifest from silently standing in for the missing source comparison.
