# Cross-domain analogical mapping (CDAM)

## Purpose

CDAM searches for structure-preserving correspondences between systems whose
surface vocabulary and scientific domains differ. It extends the existing
analogy-transfer math skill with explicit, inspectable system representations
and a bounded graph matcher.

CDAM is a discovery aid. A structural match is not a proof of physical
equivalence, causal equivalence, dimensional consistency, or transferability.

## Components

- **USR (Universal System Representation):** typed nodes, directed labelled
  relations, SI dimension vectors, invariant references, assumptions, and
  validity regimes.
- **Structural matcher:** bounded backtracking search for a typed, relation-
  preserving node map. Node labels and domain names are deliberately excluded
  from matching.
- **UIML (Universal Invariant and Mechanism Library):** versioned definitions
  of candidate reusable invariants, assumptions, applicable domains, and
  known limitations.
- **Transfer and falsification (next phase):** equation translation,
  parameter/state transformations, counterexample generation, and experiment
  plans. These are not claimed as implemented by the initial matcher.

## Initial implemented behavior

The C++ headers under cpp/include/expert_robot/cdam/ provide:

1. USR data types and validation for identifiers, endpoints, duplicate edges,
   and bounded SI exponents.
2. Structural isomorphism and induced-subgraph candidate matching.
3. A hard search-state budget. Exhaustion is reported as inconclusive rather
   than as proof that no mapping exists.
4. Separate node, edge, and shared-invariant coverage.
5. Explicit unit-validation state and caveats.
6. A starter invariant catalog covering conservation, network balance,
   energy balance, symmetry, state-space dynamics, diffusion, and oscillation.

The smoke fixture compares an electrical series-network representation with a
hydraulic network representation. It uses domain-specific labels and different
physical dimensions while retaining an abstract typed relational graph. This
demonstrates a structural correspondence only. It does not establish that
every electrical or hydraulic model is interchangeable.

## Matching contract

The current matcher requires:
- compatible node kinds;
- injective node mapping;
- preservation of directed, labelled edges between mapped nodes;
- degree bounds that permit a source to embed in a larger target;
- a finite search-state budget.

Node labels, domain names, units, assumptions, and validity regimes are not
silently treated as equivalent. Units are reported separately. Assumptions and
regimes remain attached to the USR so later transfer/qualification stages can
compare them explicitly.

An exact structural isomorphism is reported only when node and edge counts
match and a complete mapping is found. Otherwise a complete source mapping
into a larger target is reported as an induced-subgraph embedding. The matcher
does not yet compute general graph-edit distance or approximate partial
mappings.

## Integration contract

- **Ideonomy:** use mappings as candidate cross-domain search seeds, never as
  accepted hypotheses.
- **Hermes:** dispatch bounded extraction/matching/falsification tasks and
  preserve task lineage.
- **Knowledge graph:** store mapping artifacts and typed relationships such
  as STRUCTURALLY_ANALOGOUS_TO, ISOMORPHIC_TO, PRESERVES_INVARIANT,
  VALID_ONLY_UNDER, and ANALOGY_DISPROVED_BY. Each edge must point to its
  mapping evidence.
- **Logos:** challenge assumptions, hidden regime changes, unmatched
  constraints, and superficial correspondences.
- **MCFC/Avrea:** execute bounded extraction, symbolic comparison, and
  reproducible experiments with resource receipts.
- **CACE:** verify exact mapping inputs, algorithm version, output digest,
  dimensional checks, derivations, and experiment receipts. A graph match
  alone must never be upgraded to a proof.
- **RSI:** evaluate discovery strategies against fixed held-out domain pairs.
  Performance recommendations do not automatically promote code or skills.

## Next engineering phases

1. Equation AST and symbolic normalization.
2. Explicit dimensional-analysis engine and unit conversion.
3. Higher-order relation/hypergraph representation.
4. Invariant matching with formal definitions rather than identifier overlap.
5. State-space and differential-equation correspondence.
6. Category-theoretic mapping adapters where mathematically justified.
7. Transfer proposal generator with assumptions and regime checks.
8. Counterexample and falsification adapters.
9. Persistent mapping registry and evidence receipts.
10. Discovery Atlas visualization and benchmark-driven RSI.

## Acceptance criteria

- Recover the electrical/hydraulic structural fixture.
- Reject a fixture with a changed relation label.
- Support a source graph embedded in a larger target.
- Reject malformed USR data.
- Enforce the search-state budget.
- Report unchecked units as a caveat.
- Preserve the distinction between structural candidate, mathematical
  equivalence, physical validity, and independent verification.
- Keep all candidate generation advisory; no automatic qualification,
  promotion, or authority expansion.
