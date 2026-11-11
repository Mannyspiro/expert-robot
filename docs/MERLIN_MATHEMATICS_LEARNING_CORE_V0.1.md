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
- `LessonSession` enforces sequential stage completion, so symbolic notation cannot be reached by skipping the concrete and visual stages.
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

## Spaced repetition and retrieval scheduling

The core now includes an SM-2-inspired review scheduler with per-learner/per-concept cards, due dates, intervals, ease factors, repetition counts, and recall quality. Successful recall expands intervals; difficult recall schedules an early retry. Reviews write explicit retention evidence back to the learner attempt store. This is a practical initial scheduler, not a claim that SM-2 is universally optimal; interval policy should be evaluated against delayed recall and learner burden.

## Comprehensive learner input

`LearningInput` and `LearningInputStore` normalize text, choice, numeric, expression, code, proof, graph, audio, video and mixed-mode responses. The envelope also captures confidence, hints, elapsed time, accessibility metadata and source references. Large audio/video payloads are deliberately stored outside this table; the record retains references and structured response metadata. Input metadata must be JSON-serializable and finite.

## Parrondo-inspired teaching strategy optimization

The implementation treats the paradox as a hypothesis about strategy portfolios, not as course content and not as a guarantee. A mixed policy cycles through retrieval practice, worked examples, interleaving, visual exploration, self-explanation and spaced review. Single-strategy control assignments and a comparison summarizer are included.

The comparison tracks immediate accuracy, delayed retention, transfer and independent solving. The intended test is whether a measured mixture can outperform the best individual strategy on durable learning outcomes, even if some individual sessions or component strategies look worse. This requires randomized learner/concept-level assignment, comparable tasks, delayed assessments, adequate sample sizes and held-out replication before making causal or optimization claims. The current cycling policy is an experiment primitive, not yet an adaptive causal policy.

## Next implementation increments

1. Browser-based interactive lesson player with graph manipulation, equation/number-line visualizations, keyboard and screen-reader alternatives.
2. Daily review queue integrated into lesson selection, with a bounded review load and learner-controlled deferral.
3. Strategy experiment allocator with reproducible randomization, baseline arms, assignment logs, outcome capture and confidence intervals.
4. Curriculum compiler for the three learning paths with explicit prerequisite, representation and assessment coverage.
5. Hermes tutoring adapter that proposes hints/questions but cannot mark mastery without assessed evidence.
6. Canonical learner registry integration after schema inspection; do not fork the source of truth.
7. Video/resource discovery with provenance, accessibility and rights metadata.
8. Held-out evaluation of delayed retention, transfer, independent solving and time-to-mastery.

The review queue supports a per-request limit and learner-controlled deferral by whole days. Deferral changes the due date without fabricating a recall result or changing mastery. A reproducible hash-based learner/concept cluster allocator now assigns experiment arms from a preregistered seed and arm list; allocation still needs balance checks and persisted study receipts in a production experiment.
