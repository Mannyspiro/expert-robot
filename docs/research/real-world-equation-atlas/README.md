# Real-World Equation Atlas — Merlin Research Package

This directory contains the 100-entry atlas, research prompt, Merlin context, source crosswalk, normalized entry tranche, validation code, reproducible experiments, XMG contract, Lean theorem candidates, and Math Kung Fu lesson sequence.

## Research and data files
- `PROMPT.md` — complete Merlin research instruction.
- `ATLAS_001-100.md` — initial equation atlas.
- `SOURCES_AND_CITATION_CROSSWALK.md` — source register and equation-ID mapping, with explicit application-specific gaps.
- `NORMALIZED_ENTRIES_001-020.json` — first normalized metadata tranche; it is not yet a complete canonical-schema export.
- `equation-entry.schema.json` — intended canonical machine-readable entry schema.
- `MERLIN_CONTEXT.md` — relevant project context and research architecture.
- `PHASE_0.3_EXECUTION_PLAN.md` — next-stage workstreams, evidence receipts, verification ladder, XMG integration, and recommended execution order.
- `RESEARCH_STATUS_V0.2.md` — current status record (document heading tracks v0.3 and records the observed Avrea run).
- `XMG_MULTI_FRAME_CONTRACT.md` — typed multi-frame representation, transformations, invariants, and visualization contract.
- `LESSON_001_OPTIMIZATION.md`, `LESSON_SEQUENCE_V0.2.md` — learning modules.

## Verification and experiments
- `VERIFICATION_AND_LEAN.md` — evidence layers and promotion gates.
- `EXPERIMENT_RUNBOOK.md` — reproducible commands and experiment definitions.
- `BASELINE_EXPERIMENT_RESULTS.json` — local reference values.
- `python/merlin/equation_atlas/` — dimensional, symbolic, and numerical starter modules.
- `tests/test_merlin_equation_atlas.py` — regression tests.
- `formal/MathAI/EquationAtlas.lean` — active Lean theorem candidates.
- `formal/MathAI/Audit.lean` and `formal/theorem_registry.json` — axiom-audit binding and theorem candidate registry.

## Avrea execution evidence
On 2026-11-04, CI run 1271 (run ID `41837021534`) completed successfully on the configured Avrea runner. The equation-atlas dimensional, symbolic, and numerical check step passed, and the `merlin-equation-atlas-baseline` artifact was published and inspected. This confirms execution of the configured starter checks, not empirical validity of the models or formal proof success.

## Status and limitations
This is an initial research implementation, not a completed verification of all 100 equations. Entries 001–020 have a normalized metadata tranche; executable dimensional checks cover eight representative relations; source coverage gaps remain. The normalized tranche still needs conversion/validation against the canonical schema. Lean code remains candidate until the separate pinned formal-qualification workflow compiles it and its axiom report is reviewed. Numerical baselines are synthetic reproducibility checks, not empirical validation.

## Next completion gates
1. Close specialist primary-source gaps with claim-level citations.
2. Normalize entries 021–100 and reconcile the first tranche with the canonical schema.
3. Extend dimensional and symbolic checks across all applicable entries.
4. Add convergence, sensitivity, uncertainty, and benchmark comparisons to the numerical experiments.
5. Run and inspect the separate pinned Lean qualification workflow.
6. Build evidence receipts that bind source, equation version, code commit, environment, test output, and artifact hash.
7. Serialize XMG objects and generate deterministic multi-frame SVG/GLTF views with transform invariants.
8. Generate lessons only from entries with explicit evidence labels.
