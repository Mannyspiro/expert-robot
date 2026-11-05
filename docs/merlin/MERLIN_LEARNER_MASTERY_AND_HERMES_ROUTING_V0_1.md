# Merlin Learning: learner mastery and Hermes lesson routing v0.1

## Purpose

Merlin Learning measures what a learner can demonstrate through problems, not grade labels, time spent, or self-report alone. Hermes chooses lessons from the canonical mathematical idea graph using evidence, uncertainty and prerequisite structure.

## Evidence model

Every attempt is an immutable event with learner pseudonymous ID, canonical idea ID, problem and rubric versions, representation, response/work artifact, correctness, hints, retries, confidence, and evidence provenance. Time is context, never a mastery proxy by itself.

Maintain separate estimates for:
- recognition and interpretation;
- conceptual explanation;
- procedural execution;
- translation between representations;
- estimation and error detection;
- transfer to a changed context;
- proof, justification and counterexample construction;
- delayed retention.

Each estimate stores confidence, uncertainty, sample count, recency and links to attempts. An unobserved skill is not a failed skill.

## Adaptive placement

Start with accessible prerequisite problems. Branch on evidence:
- correct with explanation: test transfer or a deeper relationship;
- correct without explanation: ask for reasoning or a second representation;
- incorrect with coherent reasoning: diagnose the misconception;
- incorrect without usable reasoning: step back one prerequisite;
- inconsistent responses: collect another independent observation.

Use constructed response, worked solutions, diagrams, explanations, proofs, estimates and transfer. Distinguish arithmetic slips from conceptual errors. A lucky multiple-choice guess cannot establish mastery.

## Hermes routing

Hermes reads a learner-state snapshot and the canonical idea graph. Candidate lessons are ranked by prerequisite readiness, expected learning gain, uncertainty reduction, retention need, modality preference, cognitive load and compute cost. Every recommendation carries a short evidence trace explaining which demonstrated skills and prerequisite gaps led to the choice.

Hermes may sequence lessons but cannot silently edit canonical mathematics or learner history. Scoring rubrics are versioned; attempt history is append-only.

## Mastery states

Use unobserved → emerging → practicing → provisionally mastered → retained. Provisional mastery requires configured evidence thresholds and at least two independent observations. Retained additionally requires delayed retrieval. Contradictory evidence reduces confidence and reopens practice without erasing history.

## Rotation pilot

Lesson ID: rotation-four-representations-v0.1.

Canonical concepts: planar rotation, linear map, complex multiplication, quaternion rotor, geometric-algebra rotor, coordinate transformation and representation equivalence.

Problems:
1. Predict the image of (1,0) under a 90-degree rotation.
2. Apply the 2x2 rotation matrix.
3. Express the same operation as complex multiplication.
4. Explain the quaternion half-angle in qvq-inverse.
5. Explain the geometric-algebra rotor sandwich.
6. Translate the result between two representations.
7. Transfer to a different vector or compose two rotations.

The HTML file is an offline interactive prototype. Its one multiple-choice item is formative only and is not a placement or mastery instrument. Production placement requires constructed work, multiple evidence types and delayed checks.

## Privacy and fairness

Use pseudonymous learner IDs, data minimization, explicit retention periods, export/deletion paths and role-based access. Do not infer sensitive traits or use demographic proxies for ability. Provide accessible alternatives to timed, visual or speech-based tasks. Audit calibration and measurement bias.

## Acceptance criteria

- Every problem links to a canonical idea ID and versioned rubric.
- Placement reports strengths, gaps and uncertainty by dimension.
- Hermes cites evidence and prerequisites behind each lesson selection.
- Correct answers without reasoning do not establish conceptual mastery.
- Transfer and delayed retention are measured separately.
- Learner attempts are append-only; scoring revisions are versioned.
- The rotation lesson works offline.
- Learner-state updates never expand agent execution permissions.
