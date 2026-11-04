# Real-World Equation Atlas — Merlin Research Package

This directory contains the 100-entry atlas, research prompt, Merlin context, source crosswalk, normalized entry tranche, validation code, reproducible experiments, XMG contract, Lean theorem candidates, and Math Kung Fu lesson sequence.

## Research and data files
- `PROMPT.md` — complete Merlin research instruction.
- `ATLAS_001-100.md` — initial equation atlas.
- `SOURCES_AND_CITATION_CROSSWALK.md` — authoritative source register and equation-ID mapping, with explicit gaps.
- `NORMALIZED_ENTRIES_001-020.json` — normalized variables, units, dimensions, assumptions, and source IDs for the first 20 entries.
- `equation-entry.schema.json` — normalized machine-readable entry schema.
- `MERLIN_CONTEXT.md` — relevant project context and research architecture.
- `XMG_MULTI_FRAME_CONTRACT.md` — typed multi-frame representation, transformations, invariants, and visualization contract.
- `LESSON_001_OPTIMIZATION.md`, `LESSON_SEQUENCE_V0.2.md` — learning modules.

## Verification and experiments
- `VERIFICATION_AND_LEAN.md` — evidence layers and promotion gates.
- `EXPERIMENT_RUNBOOK.md` — reproducible commands and experiment definitions.
- `BASELINE_EXPERIMENT_RESULTS.json` — captured deterministic reference values.
- `python/merlin/equation_atlas/` — dimensional, symbolic, and numerical starter modules.
- `tests/test_merlin_equation_atlas.py` — regression tests.
- `lean/MerlinEquationAtlas/Basic.lean` — formal theorem candidates.

## Status
This is an initial research implementation, not a completed verification of all 100 equations. Entries 001–020 have a normalized metadata tranche; executable dimensional checks cover eight representative relations; source coverage gaps are listed explicitly. Lean code is a candidate until compiled using the repository-pinned toolchain. Numerical baselines are synthetic reproducibility checks, not empirical validation.

## Next completion gates
1. Add specialist primary sources for each remaining entry and close every crosswalk gap.
2. Normalize entries 021–100.
3. Extend dimensional and symbolic checks across all applicable entries.
4. Run Python tests and Lean proofs in the pinned CI environment; archive logs and artifacts.
5. Serialize XMG objects and generate multi-frame SVG/GLTF visualizations.
6. Promote lessons only with claim-level evidence labels.
