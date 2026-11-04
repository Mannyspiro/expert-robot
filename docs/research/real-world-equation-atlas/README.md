# Real-World Equation Atlas — Merlin Research Package

This directory contains the 100-entry atlas, research prompt, Merlin context, source crosswalk, normalized entry tranche, validation code, reproducible experiments, XMG contract, Lean theorem candidates, and Math Kung Fu lesson sequence.

## Research and data files
- `PROMPT.md` — complete Merlin research instruction.
- `ATLAS_001-100.md` — initial equation atlas.
- `SOURCES_AND_CITATION_CROSSWALK.md` — source register and equation-ID mapping, with explicit application-specific gaps.
- `NORMALIZED_ENTRIES_001-020.json` — first normalized metadata tranche; it is not yet a complete canonical-schema export.
- `equation-entry.schema.json` — canonical machine-readable entry schema, including SI dimension metadata.
- `NORMALIZED_ENTRIES_001-020_V0.3.json` — generated canonical migration output (created and validated in CI).
- `EVIDENCE_RECEIPT_CONTRACT_V0.1.md` — content-addressed reproducibility receipt contract.
- `evidence-receipt.schema.json` — schema for receipt validation.
- `MERLIN_CONTEXT.md` — relevant project context and research architecture.
- `PHASE_0.3_EXECUTION_PLAN.md` — next-stage workstreams, evidence receipts, verification ladder, XMG integration, and recommended execution order.
- `RESEARCH_STATUS_V0.2.md` — current status record (document heading tracks v0.3 and records the observed Avrea run).
- `XMG_MULTI_FRAME_CONTRACT.md` — typed multi-frame representation, transformations, invariants, and visualization contract.
- `LESSON_001_OPTIMIZATION.md`, `LESSON_SEQUENCE_V0.2.md` — learning modules.

## Verification and experiments
- `VERIFICATION_AND_LEAN.md` — evidence layers and promotion gates.
- `EXPERIMENT_RUNBOOK.md` — reproducible commands and experiment definitions.
- `BASELINE_EXPERIMENT_RESULTS.json` — local reference values.
- `python/merlin/equation_atlas/` — dimensional, symbolic, numerical, canonical normalization, and evidence-receipt modules.
- `tests/test_merlin_equation_atlas.py` — regression tests.
- `formal/MathAI/EquationAtlas.lean` — active Lean theorem candidates.
- `formal/MathAI/Audit.lean` and `formal/theorem_registry.json` — axiom-audit binding and theorem candidate registry.

## Avrea execution evidence
On 2026-11-04, CI run 1271 (run ID `41837021534`) completed successfully on the configured Avrea runner for the earlier starter implementation. The new schema migration and evidence-receipt changes are awaiting their own CI run. The updated workflow now validates both canonical entries and receipt structure, and hashes the dependency lock and receipt schema into the evidence record. Do not infer their success from the earlier run. The earlier baseline artifact confirms execution of the original starter checks, not empirical validity of the models or formal proof success.

## Status and limitations
This is an initial research implementation, not a completed verification of all 100 equations. Entries 001–020 have a legacy normalized metadata tranche and a new schema-driven canonical migration. The migration preserves variable dimensions and legacy conditions, maps source IDs into explicit review-required citation records, and intentionally marks all migrated entries `UNVERIFIED`. CI now validates each migrated entry against the canonical JSON Schema. Executable dimensional checks still cover eight representative relations; source coverage gaps remain. Lean code remains candidate until the separate pinned formal-qualification workflow compiles it and its axiom report is reviewed. Numerical baselines are synthetic reproducibility checks, not empirical validation.

## Next completion gates
1. Close specialist primary-source gaps with claim-level citations.
2. Run Avrea CI for the new canonical migration and receipt implementation; fix any failures before expanding the tranche.
3. Normalize entries 021–100 after schema migration passes.
4. Extend dimensional and symbolic checks across all applicable entries.
5. Add convergence, sensitivity, uncertainty, and benchmark comparisons to the numerical experiments.
6. Run and inspect the separate pinned Lean qualification workflow.
7. Extend evidence receipts to bind equation versions, dependency lock, seeds, tolerances, test output and benchmark provenance.
8. Serialize XMG objects and generate deterministic multi-frame SVG/GLTF views with transform invariants.
9. Generate lessons only from entries with explicit evidence labels.
