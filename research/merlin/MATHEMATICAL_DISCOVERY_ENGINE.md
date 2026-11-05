# Merlin Mathematical Discovery Engine

## Implemented orchestration boundary

`python/merlin/math_discovery_engine.py` provides a deterministic orchestration layer over the mathematical discovery atlas. It generates explicit conjecture seeds from proof obligations and experiment prompts, accepts optional Ideonomy expansion, creates visibly incomplete Lean scaffolds, dispatches numerical and counterexample work only through injected adapters, compares experiment output only when an engine supplies an explicit comparison, and accepts CACE receipts only when they bind the exact submitted artifact digest.

## Adapter contracts

- Ideonomy: callable receiving candidate plus seed records; returns conjecture mappings.
- Lean: callable receiving conjecture plus scaffold; must return explicit status. A scaffold containing `sorry` is never a verified proof.
- Numerical: callable returns engine, engine_version, tool_version, precision and seed, plus result data and environment digest.
- Counterexample: callable returns the same reproducibility metadata plus an explicit search_scope and result.
- CACE: callable returns a verification status and the exact artifact_sha256 submitted. A mismatched digest is rejected.

No adapter is silently replaced with a mock or placeholder result. Unconfigured adapters return an explicit not-dispatched/not-requested state.

## Evidence scoring

The ranker uses a transparent composite:
- 50% evidence quality (proof 30%, reproducible experiment 20%, counterexample search 15%, CACE 25%, reviewed sources 10%)
- 30% reproducibility
- 20% mathematical significance

The significance score is a bounded human/reviewer-supplied field, not a model's novelty estimate. Ranking is triage only and has no promotion authority. Missing evidence scores zero.

## Important limitations

The Hermes research executor in this initial implementation generates atlas-derived seeds only. It does not invoke an LLM Ideonomy service, Lean compiler, numerical backend, counterexample engine or CACE service. Production use requires registering real adapters in the deployment's Hermes configuration and routing outputs through the existing ResearchEvidenceRecorder and CACE verification adapter. No experiment, proof or independent verification is claimed by this commit.

Titan remains unchanged. Every experimental candidate remains cryptographically ineligible.
