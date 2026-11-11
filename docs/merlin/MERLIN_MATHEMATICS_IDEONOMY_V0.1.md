# Merlin mathematics lesson Ideonomy v0.1

## Purpose

Merlin should not jump from one attractive lesson idea to another by intuition alone. This bounded Ideonomy module makes a deliberately scoped design space enumerable, records why combinations are excluded, and ranks coherent candidates with inspectable heuristics. It is a design aid, not an efficacy claim.

## Current enumeration

The first Parrondo-focused design space is the Cartesian product of six axes:

| Axis | Values |
|---|---:|
| Learner path | 3 |
| Representation | 4 |
| Activity | 4 |
| Evidence type | 4 |
| Pedagogical sequence | 3 |
| Context | 3 |
| **Total** | **1,728** |

The paths are mathematician, mathematics programmer, and computational hacker. Representations range from concrete objects to executable models. Activities include prediction, simulation, transition-rule derivation, and implementation. Evidence includes concept checks, independent transfer, formal proof, and reflection.

## Coherence constraints

The enumerator rejects, with named reasons, combinations such as:
- formal-proof evidence assigned outside the mathematician path;
- implementation tasks assigned to a path where they are not the primary activity;
- executable representations without computational activities;
- code-first sequences without executable representations;
- reflection alone being treated as evidence of mastery.

The filters are explicit and testable. They are hypotheses about coherence, not immutable educational truths; future measured learner outcomes should revise them.

## Ranking and use

Surviving designs receive a deterministic heuristic score. The current score favors prediction before feedback, visible state representations, independent transfer, and an appropriate path/activity fit. Every retained design carries a short rationale. Tie-breaking is deterministic. The default call returns the top 24, while the report retains the full evaluation count and rejection-reason histogram.

Example:

```python
from merlin.ideonomy import parrondo_design_shortlist

report = parrondo_design_shortlist(limit=12)
print(report.cartesian_size, report.evaluated, report.rejected)
for design in report.retained:
    print(design.score, design.path, design.activity, design.evidence)
    print(*design.rationale, sep="; ")
```

## Next empirical loop

1. Convert top-ranked designs into lesson variants only after checking prerequisite coverage.
2. Collect attempts, hints, response latency, independent transfer, and delayed retention in the existing learner store.
3. Keep exploration/simulation events separate from assessed evidence. Merely running Game A/B or viewing a graph must never grant mastery.
4. Compare variants with predeclared outcomes and reproducible assignments; do not infer effectiveness from the heuristic score.
5. Expand the axes only when new requirements or measured observations justify them. Track the combinatorial growth and retain explicit caps.

## Scope boundary

This version enumerates lesson-design combinations only. It does not generate arbitrary scientific claims, execute generated code, call external models, or certify proofs. Formal verification and CACE receipts remain separate evidence channels.
