# Merlin Proof Observatory — Knowledge Graph and Engineering IR Bridge v0.1

**Date:** 2026-11-04  
**Repository:** `Mannyspiro/expert-robot`  
**Implementation branch:** `feat/merlin-lean-proof-optimization-atlas-20261104`  
**Starting commit:** `216faab900aeef64566b8b8bc1a7fad3dc77b297`  
**Latest implementation commit:** `ed0777544faf0dbf820a8ec2397a4e4b3a91ceee`  
**Status:** draft implementation; exact-head CI/Avrea qualification pending.

## Purpose

Connect proof and benchmark evidence to the persistent Merlin Knowledge Graph and to a specific, hash-verified Engineering IR revision. The bridge is deliberately revision-specific: an object view from an older CAD/wiring revision cannot be attached to evidence for a newer revision.

## Implemented contracts

- `object_view` is now a first-class Knowledge Graph node type.
- `register_engineering_revision_views` loads an exact EngineeringProjectStore revision, verifies the complete revision history, recomputes its canonical project hash, and creates a revision node plus object views for every part and net.
- `register_representation_graph_views` converts exact coordinate frames into object-view nodes bound to the same project revision. Rational matrix entries are serialized exactly as strings.
- `link_observatory_to_graph` checks the Knowledge Graph snapshot hash, benchmark receipt self-hash, theorem DAG integrity, exact project revision, and every object-view binding before creating theorem/evidence links.
- The Knowledge Graph uses `contains` edges from the engineering revision to its part/net/frame views and `tests` edges from object views to theorem nodes. The Observatory stores matching cross-domain link receipts.
- The proof-observatory link operation now validates the theorem DAG before persisting the benchmark receipt, preventing one known partial-write case.

## Evidence and claim boundaries

- A Knowledge Graph edge records a typed relationship; it does not prove the linked theorem or establish that a CAD/wiring design is safe.
- Engineering revision hashes establish content identity, not physical correctness.
- Benchmark receipts are self-hashed and bound to a source commit; this bridge does not independently authenticate GitHub's workflow logs or Avrea runner identity.
- The theorem DAG's Lean header hashes remain surface-syntax fingerprints, not elaborated theorem identities.
- The bridge does not replace Lean kernel checking, axiom audits, ERC/DRC, circuit simulation, standards review, fabrication checks or human engineering approval.
- Existing object views are immutable by revision identity. A later Engineering IR change creates a new revision and new object-view IDs.

## Tests added

`tests/test_observatory_graph_bridge.py` contains six integration tests covering real EngineeringProjectStore revisions, part/net object views, coordinate-frame registration, theorem linking, stale-revision rejection, malformed theorem-DAG rejection before receipt persistence, project-node identity mismatch, and invalid string-as-collection input.

The six tests are added to the existing Avrea-backed CI suite. The exact-head Avrea check suite is queued and has not yet reported job results; the GitHub Actions workflow check has failed without exposing any jobs or test logs. Cloudflare preview checks are separate deployment checks. Passing Avrea CI on the exact current commit is still required before treating the implementation as validated. Passing CI on this exact commit is still required before treating the implementation as validated.
