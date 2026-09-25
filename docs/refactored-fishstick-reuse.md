# Reusing refactored-fishstick

Expert Robot intentionally reuses verified design work from
`Mannyspiro/refactored-fishstick` rather than rebuilding equivalent systems.

## Pinned source

The initial source is the `owner-collar-frozen-runtime` branch at:

`77224183e78a262a34b2c1c311b1d1fbc7c59b4e`

This is the head of draft PR #53 at the time of integration. It is not treated
as canonical merely because it is imported.

See `config/upstream/refactored-fishstick.lock.json`.

## Reuse rule

### Copy directly

Artifacts whose semantics are independent of the old Python runtime may be
copied with provenance:

- Lean theorem/proof modules
- schemas
- deterministic configuration
- sandbox policy concepts
- qualification contracts
- test vectors

### Port to C++

Operational modules are ported to C++ because Expert Robot keeps Python thin:

- capability registry
- deterministic Lean proof search
- proof-search memory
- recursive lemma factory
- theorem/lemma knowledge graph
- exact geometry kernel
- algebra-geometry bridge
- geometry-to-Lean bridge
- specialist agents
- benchmark engine
- research notebook/state machine
- capability growth controller
- novelty/reuse engine
- RSI candidate lineage and qualification logic

The old Python implementation is the behavioral reference, not the production
runtime.

### Do not copy automatically

- owner identity/trust records
- private authentication material
- model weights
- old model choices that conflict with Expert Robot's selected models
- environment-specific live-USB state

## Trust boundary

Imported code is not automatically trusted. Every port must gain its own tests
in Expert Robot. Formal claims remain trusted only after the pinned Lean kernel
accepts them and the local qualification path passes.

## First imported slice

1. Exact rational 3D geometry Lean bridge.
2. Lean trust seed.
3. Lean 4.34.0 + Mathlib 4.34.0 formal environment pin.
4. Sandbox deny-by-default policy adapted to Expert Robot paths.
5. Capability registry semantics ported from Python to C++.

## Next ports

The next high-value ports should be:

1. deterministic Lean proof search
2. SQLite proof memory
3. theorem/lemma knowledge graph
4. recursive lemma factory
5. research state machine
6. specialist routing
7. benchmark-driven capability growth
8. novelty/reuse engine
9. immutable RSI candidate lineage
