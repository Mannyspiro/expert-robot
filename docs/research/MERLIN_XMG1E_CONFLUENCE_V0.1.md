# Merlin XMG-1E: Critical-Pair and Confluence Explorer v0.1

## Purpose

XMG-1E explores competing one-step rewrites of typed glyph expressions. It
detects overlapping rewrite sites, follows both branches to bounded normal
forms, and classifies each explored pair as joinable, non-joinable, or
unresolved.

This is a diagnostic layer for the Glyph Foundry and XMG-1C normalizer. It is
not a general theorem prover and does not infer semantic equivalence from
matching fingerprints.

## Core definitions

For a rewrite relation (\to_R), a critical pair is a pair of branches
(u \leftarrow_R t \to_R v) produced by overlapping rewrite sites in the
same expression. A pair is joinable when there exists a term (w) such that
(u \to_R^* w \leftarrow_R^* v).

XMG-1E currently uses deterministic, bounded normalization to search for a
common normal form. It enumerates AST positions in preorder and regards two
positions as overlapping when one is an ancestor of the other. Disjoint
rewrites are omitted because they are not critical overlaps for this
exploration.

## Status meanings

- `joinable`: both branches reached the same fingerprinted normal form under
  the exact supplied rewrite set.
- `non_joinable`: both branches reached distinct normal forms under that set.
  This is a concrete non-confluence witness for the explored expression when
  all accepted rewrite steps strictly decrease AST node count.
- `unresolved`: at least one branch exhausted its global normalization step
  budget.
- `truncated`: the pair-enumeration budget was exhausted before all overlaps
  in the supplied expression could be examined.

The engine enforces type-signature preservation and strictly size-decreasing
rewrites. Since AST node count is a positive natural number and decreases at
each accepted rewrite, every rewrite sequence terminates. This establishes
termination for this restricted engine, not for arbitrary future rewrite
systems.

## Reproducibility and evidence

A report records the ordered rule IDs, source fingerprint, redex positions,
branch fingerprints, normal-form fingerprints, classification, and reason.
The report is scoped to the exact rule order, implementation version, input
expression, and resource bounds. A report is not itself a Lean proof or CACE
qualification receipt.

The normal-form routine uses one global step budget per branch. Fingerprint
memoization charges cached rewrite traces again at every occurrence, so shared
subexpressions cannot bypass the budget.

## Known limits

- Rules are currently Python matcher/replacement callbacks, not a declarative
  first-order pattern language with metavariables.
- The engine examines concrete expressions supplied by the caller. It does
  not prove confluence for all possible expressions.
- Fingerprint equality is structural equality of the canonical AST, not
  semantic equivalence.
- Approximate/numerical agreement is outside this module.
- Critical-pair enumeration is bounded and can be truncated.

## Next research steps

1. Introduce declarative typed patterns and metavariables.
2. Add critical-pair generation from pattern overlaps, not only concrete ASTs.
3. Export branch derivations as proof obligations in Lean.
4. Add a finite rewrite-system termination/confluence certificate format.
5. Route reproducible candidate corpora and stress tests to the Avrea math
   benchmark workflow, then pass independent receipts to CACE.
6. Add cross-representation critical pairs for Cartesian, complex, quaternion,
   tensor, and geometric-algebra adapters.
