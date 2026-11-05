# Integrated Mathematical Discovery Adapters

This integration composes existing Merlin components through one adapter factory:
`merlin.math_discovery_integrated.build_integrated_math_discovery_handlers`.

## Current implementation

- Ideonomy consumes the real `IDEONOMY_PRIMITIVES` and
  `enumerate_simplex_combinations(3)` outputs. It preserves primitive IDs,
  domains, functions, simplex IDs and atlas seed IDs. The existing Ideonomy
  invention catalogue is not treated as a theorem generator. Without an
  explicitly injected claim factory, outputs remain
  `ideonomy_proposal_unformalized` and cannot be translated to Lean.
- A claim factory must return explicit assumptions, a falsifiable statement,
  a formal statement and (when Lean execution is intended) a concrete
  `lean_source`. These remain proposed, unproved conjectures.
- Lean project discovery locates the pinned project under `formal/`, reads
  `lean-toolchain`, `lakefile.toml` and `lake-manifest.json`, and hashes the
  dependency configuration. The compiler adapter runs `lake env lean` with a
  bounded timeout and captures exit status, stdout, stderr, toolchain,
  dependency hashes and source digest. A compiler pass is labelled
  `compiled_unverified`, never `proof_verified`; placeholders are rejected.
- The numerical adapter requires a supplied solver, seed, precision and
  parameters. It replays the same request twice within a bounded runtime and
  awards reproducibility only when canonical output bytes match. It records
  environment and raw-output digests.
- The counterexample adapter requires a supplied bounded search backend,
  declared domain, bounds, method and seed. Timeout/error/incomplete outcomes
  remain incomplete; no negative search conclusion is inferred.
- Hermes registration uses the existing `build_hermes_stage_handlers` and
  `ResearchEvidenceRecorder`. Exact aggregate artifact bytes are written to
  the canonical registry, linked to the hypothesis ledger and graph, then
  passed to the existing `CaceVerificationAdapter.verify_artifact` method.
  Registry integrity and independent CACE verification remain distinct.
- No Avrea transport is assumed. Worker execution must be explicitly injected
  through approved backends; no implicit remote dispatch is performed.
- Titan is unchanged. All outputs have `promotion_authority: false`; no
  automatic promotion is implemented.

## Configuration required before production execution

The caller must supply:
1. A real CACE adapter configured with its independent verification transport.
2. A numerical solver implementation and its actual engine/tool versions.
3. A bounded counterexample searcher and its actual engine/tool versions.
4. An Ideonomy claim factory if formal conjectures are desired. It must preserve
   source IDs and return explicit assumptions, falsifiable/formal statements,
   and optional Lean source.
5. A canonical `ResearchEvidenceRecorder`, registry project ID, repository
   identity, exact commit SHA and requester identity.

The factory returns the standard Hermes stage-handler mapping. The
`research`, `numerical_experiment` and `proof_search` handlers currently
share the integrated executor and differ in the existing stage evidence
contract. A production caller should supply task specs appropriate to the
requested stage.

## Verification status

Contract tests were added in `tests/test_math_discovery_integrated.py`.
They have not been run. No Lean compilation, numerical experiment,
counterexample search, CACE submission, Avrea dispatch, merge or deployment
is claimed by this change.
