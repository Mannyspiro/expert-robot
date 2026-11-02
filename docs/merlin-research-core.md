# Merlin research core: ideonomy, evidence, reframing and RSI gates

This module implements four deterministic, model-independent contracts for Merlin.

## Evidence ledger
Claims carry explicit evidence classes. Engineering verification requires a hashed test-log artifact; numerical certification requires a hashed certificate; proof requires a hashed formal receipt. Confidence or an LLM statement cannot promote a claim.

## Alien-lacuna ideonomy
The ideonomy layer may recombine concepts across disciplines, but each candidate must state a mechanism, assumptions, constraints, an observable, and a falsifier. Invalid and duplicate ideas are rejected before ranking. Surviving ideas are ranked by explicit weighted novelty, feasibility, evidence fit, testability and resource efficiency. Results remain research candidates; the "alien" framing is a creativity prompt, not an epistemic claim.

## Verified problem reframing
A difficult problem may be translated to a simpler graph, algebra, geometry or optimization problem only if entity and operation mappings are explicit, all required invariants are preserved, both boundary-condition sets are declared, and failure modes are listed. The solver must translate the result back and test it against the original problem.

## RSI gate
Candidate promotion is blocked unless tests, independent review, held-out qualification, rollback readiness, authority non-expansion, human approval and compute-budget compliance all pass. The gate never performs automatic promotion.

## Run tests
\`python3 -m unittest discover -s tests/research -v\`

This is a deterministic core, not an LLM, scientific oracle, or autonomous authority system.
