# Verified mathematical research engine

Expert Robot now has a bounded end-to-end research loop rather than a loose
collection of agents.

## Core episode

```
formal target
    |
    v
retrieve known structure
    |
    v
cheap direct proof search
    |
    +---- Lean accepts --------------------------+
    |                                           |
    |                                           v
    |                                    consolidate target
    |
    +---- proof fails
            |
            v
      cognition controller
            |
      +-----+--------------------+
      |                          |
      v                          v
recursive lemma factory      imagination swarm
      |                          |
Lean-proven children         skeptic gate
      |                          |
      |                          v
      |                  informal -> formal
      |                          |
      +------------+-------------+
                   |
                   v
             retry parent
                   |
          +--------+---------+
          |                  |
          v                  v
      Lean accepts       new search cycle
          |
          v
 verified theorem graph
          |
          v
 hash-chained episode log
```

Only target-level Lean verification can complete a research episode. A verified
helper lemma is useful evidence, but it routes to a parent retry rather than
being mistaken for success on the original theorem.

## Research state machine

The C++ state machine uses explicit phases:

- Intake
- RetrieveKnown
- DirectProof
- Imagine
- Decompose
- VerifyCandidate
- RetryParent
- Consolidate
- Complete
- Exhausted

Hard budgets exist for:

- research cycles
- model calls
- proof attempts
- generated ideas
- generated lemmas

Hard resource pressure can also terminate an unproductive episode. Once the
target is already Lean-verified, final consolidation is allowed to finish even
if the bookkeeping step reaches the budget boundary.

## Imagination to formal mathematics

A shortlisted imagination idea is not proof material by itself.

The candidate-verification pipeline is:

```
skeptic-approved idea
        |
        v
ModelFormalizationProposer
        |
        v
strict C++ FormalizationProposal validation
        |
        v
deterministic / memory-guided proof search
        |
        v
Lean boundary
```

The model may propose a theorem statement, but may not return a proof, `sorry`,
`admit`, axioms, unsafe declarations, directives, or extra JSON fields.

Malformed candidates are isolated as candidate failures and do not abort the
whole research episode.

## Verified knowledge consolidation

Only proof-accepted candidates can be consolidated.

A verified candidate becomes a theorem-graph node with:

- status: `verified`
- generated-source provenance
- its formal statement
- mathematical domain
- `generated` and `lean_verified` tags

When the target theorem is present, helper theorems are linked by a `USES`
edge. The graph can be persisted after every consolidation.

Conflicting reuse of an existing theorem name with a different statement is
rejected.

## Hash-chained episode lineage

Every episode can be written to an append-only C++ ledger backed by SQLite.

Each event stores:

- episode ID
- monotonic sequence
- event type
- payload
- payload SHA-256
- previous event hash
- event hash

Verification recomputes the complete chain. Out-of-band edits to old SQLite
payloads are detected.

The chain records state transitions and verified-knowledge consolidation
events, providing reproducible lineage for later qualification or comparison.

## Safe skill growth

The skill system now has explicit stages:

- `experimental`
- `qualified`
- `deprecated`

Production imagination uses **qualified skills only**.

A model may propose a new skill only into the
`math.experimental.*` namespace. Proposed procedures are rejected if they
contain proof-bypass or authority-expanding instructions.

Experimental skills live in a separate SQLite store.

They can be exercised only when an imagination request is explicitly marked
`evaluation_mode=true`. Ordinary production requests containing experimental
skills are rejected.

The skill ledger records:

- attempts
- skeptic passes
- shortlist appearances
- downstream verified results
- downstream failures

Evidence may produce a **promotion recommendation**, but never changes the
skill stage automatically. Promotion still requires an explicit registry/code
change.

## Ablation/evaluation

The math-evaluation ledger records variant/case results including:

- Lean-verified success
- dead-end escape
- wall time
- model calls
- proof attempts
- generated lemmas
- generated ideas
- duplicate ideas
- normalized resource cost

Candidate variants are compared against a baseline. A keep recommendation
requires enough cases, no unacceptable verification-rate regression, acceptable
compute efficiency, and bounded duplicate growth.

Like skill qualification, the recommendation is advisory only.

## Multi-hop theorem inspiration

Imagination is no longer limited to direct theorem-graph neighbors.

Bounded breadth-first theorem paths provide controlled multi-hop inspiration
with:

- maximum depth
- maximum path count
- per-path cycle avoidance
- deterministic traversal

This gives analogical agents access to more distant mathematical structure
without an unconstrained graph crawl.

## Authority hierarchy

```
model
  -> proposes text/statements/skills

agents + skills
  -> explore procedures

cognition
  -> allocates search

research state machine
  -> controls workflow and budgets

C++ validators/supervisors
  -> enforce contracts

Lean proof boundary
  -> accepts formal proof candidates

explicit consolidation/promotion
  -> changes trusted persistent state
```

The existing invariants remain:

```
verification_rigor_multiplier = 1.0
authority_delta = 0.0
```
