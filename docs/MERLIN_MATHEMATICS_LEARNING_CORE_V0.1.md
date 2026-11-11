# Merlin Mathematics Learning Core 0.1

**Status:** implemented as a dependency-free Python vertical slice; not yet a deployed learner-facing product.

## Purpose

Provide a shared, evidence-aware foundation for three paths:

- mathematician: discovery, abstraction, conjecture and proof;
- mathematics programmer: models, numerical methods and implementation;
- computational hacker: decomposition, algorithms, debugging and building.

The first lesson is deliberately zero-first. It begins with a concrete bicycle-distance story, then observations, a visual graph and nearby-point experiments. Symbolic notation appears only after the learner has explored the underlying idea. Learners who are uncomfortable with letters or equations are not assumed to know algebra.

## Implemented in this slice

- `python/merlin/learning_core.py`: canonical concept registry, prerequisite DAG validation, typed real-scalar expression IR, beginner-first derivative lesson specification, forward/backward/central finite differences, SQLite learner evidence, dimension-specific mastery estimates and deterministic next-lesson selection.
- `tests/test_merlin_learning_core.py`: unit tests for graph integrity, expression evaluation, numerical differentiation, zero-first sequencing, persistent attempts and adaptive selection.
- No external package is required by the learning core.

## Learner evidence model

Each attempt can contribute separately to six dimensions:

1. conceptual understanding;
2. procedural fluency;
3. representational understanding;
4. transfer;
5. proof ability;
6. retention.

An attempt records learner/lesson/task identifiers, scores, independence, hints, outcome and evidence metadata. Hinted or non-independent work contributes less evidence than an independent unassisted attempt. Missing dimensions remain unknown-as-zero evidence; they are not silently inferred from completion.

The current estimator is a transparent exponential moving update, not a validated psychometric model. It must be calibrated against held-out learning outcomes before production claims.

## Mathematical experiment

For a function (f), point (x), and positive step (h), the module exposes:

- forward difference: ((f(x+h)-f(x))/h);
- backward difference: ((f(x)-f(x-h))/h);
- central difference: ((f(x+h)-f(x-h))/(2h)).

These are numerical estimates, not symbolic derivatives or proofs. The derivative lesson uses them to make the transition from average change to instantaneous change experimentally visible.

## Safety and evidence boundaries

- A numerical match is not a proof.
- An expression accepted by the local IR is not Lean-verified.
- A Lean compile result is not independent CACE verification.
- This module emits no CACE receipt and authorizes no promotion.
- SQLite records are learning telemetry, not an authority source.
- Any later Hermes integration must preserve explicit eligibility, deadlines, idempotency and fail-closed verification states.

## Known gaps / next increments

1. Add a browser lesson renderer with graph interaction and accessible text alternatives.
2. Connect lesson attempts to the canonical learner/project registry only after its data contract is inspected.
3. Add a lesson compiler that validates prerequisite edges and lesson schema versions.
4. Add concept-specific evidence mappings instead of applying every lesson score to every target concept.
5. Add delayed retention checks and held-out curriculum evaluations.
6. Add Lean exercises only after informal understanding and with pinned toolchain receipts.
7. Add CACE verification only through the independently authenticated verifier boundary; absent credentials must remain `blocked_missing_credentials`.
8. Add video/resource recommendations with source provenance and rights metadata.

## Local test

```bash
PYTHONPATH=python python3 -m unittest discover -s tests -p 'test_merlin_learning_core.py' -v
```
