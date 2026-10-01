# Recursive lemma factory

Expert Robot ports the bounded recursive lemma factory from
`Mannyspiro/refactored-fishstick` into the C++ runtime.

## Purpose

When a parent Lean theorem fails deterministic proof search, the factory may
decompose it into smaller helper lemmas, prove those helpers, inject their
accepted declarations into the local retry context, and retry the parent.

```
parent theorem
      |
      v
initial Lean proof search
      |
   fails
      |
      v
bounded decomposition
      |
      +--> child lemma A --> Lean
      |
      +--> child lemma B --> Lean
      |
      +--> child lemma C --> Lean
      |
      v
accepted child declarations only
      |
      v
parent retry
      |
      v
Lean
```

## Core invariants

The factory is deliberately bounded by:

- maximum recursion depth
- maximum children per node
- global maximum node count
- active recursion-path cycle detection

A child lemma contributes to the parent context **only when its formalization
has an accepted Lean proof result**.

Failed, budget-exhausted, cyclic, or depth-limited child nodes cannot become
trusted context.

## Status values

Nodes use explicit result states:

- `proven`
- `proven_after_children`
- `children_insufficient`
- `undecomposed_failure`
- `depth_limit`
- `node_budget`
- `cycle`

## Formalization safety

Helper proposals pass through the strict C++ formalizer.

The proposal parser rejects:

- invalid Lean identifiers
- duplicate binders
- unknown decomposition fields
- duplicate helper names
- empty imports
- newline-bearing Lean expressions
- `sorry`
- `admit`
- `axiom`
- `unsafe`
- `set_option`
- command fragments beginning with `#`

Generated helper JSON may describe candidate statements only. It does not
supply trusted proofs.

## Cognition integration

The `CognitionLemmaBridge` connects the personality executive to recursive
decomposition.

The factory runs only when the executive selects:

`DECOMPOSE_PROBLEM`

For example:

```
proof failures
      |
      v
artificial interoception
  stagnation rises
      |
      v
software neuromodulation
 strategy-switch pressure rises
      |
      v
personality executive
 DECOMPOSE_PROBLEM
      |
      v
recursive lemma factory
      |
      v
smaller Lean goals
      |
      v
verified child declarations
      |
      v
retry parent
```

Other cognitive actions do not invoke the factory.

## Decomposer boundary

The recursive engine is independent of how child proposals are generated.

Current interfaces support:

- `StaticLemmaDecomposer` for deterministic tests, stored plans, and replay
- strict JSON parsing for future math-model-generated decomposition plans

A future Qwen math specialist adapter can call `decomposition_prompt(...)`,
return JSON helper proposals, and feed the parsed candidates into the same
bounded factory.

The model will remain an **untrusted proposal generator**. Lean remains the
verification authority.

## Proof memory

The factory accepts any `IProofSearcher`, including
`MemoryGuidedProofSearch`.

This allows exact-goal proof history to reorder the already-approved tactic
list for parent and child goals without changing what counts as a proof.

## Trust boundary

Recursive decomposition can increase search depth and mathematical capability.
It cannot:

- declare a theorem proven without Lean acceptance
- use failed child statements as assumptions
- use `sorry`, `admit`, or axioms
- expand system permissions
- bypass the sandbox
- alter personality authority
- promote an RSI generation

The existing invariants remain unchanged:

```
verification_rigor_multiplier = 1.0
authority_delta = 0.0
```
