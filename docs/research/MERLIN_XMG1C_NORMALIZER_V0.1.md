# Merlin XMG-1C: Glyph Normalizer and Equivalence Engine

**Status:** source addition; repository CI and Lean proof runs remain unverified.

## Scope

Normalize typed glyph expressions using a finite, explicitly versioned rewrite set. Rewrites are not automatically theorems. Every rewrite step records its rule identifier, before/after fingerprints, evidence status, and optional evidence reference.

## Initial rules

- INT_DOUBLE_NEGATION: NEGATE_INT composed with NEGATE_INT reduces to integer identity.
- INT_ABS_NEGATION: ABS_INT composed with NEGATE_INT reduces to ABS_INT.
- PROJECT_PAIR_LEFT: first projection of a pair reduces to its first component.
- PROJECT_PAIR_RIGHT: second projection of a pair reduces to its second component.

The current rules are labeled candidate unless separately linked to a verified proof. The test suite checks finite examples and implementation behavior; finite testing is not a universal proof.

## Termination and type safety

- Rewrites must preserve the exact input and output types.
- Current rewrite rules must strictly reduce AST node count.
- Fingerprints prevent revisiting an expression within a normalization pass.
- A configurable step limit prevents runaway normalization.
- Unsupported AST node types fail explicitly rather than being silently ignored.

This establishes termination for the current size-decreasing rewrite set. Future rewrite rules that do not strictly decrease node count require a separate termination argument, such as a well-founded lexicographic measure or a proved rewrite strategy.

## Equivalence claims

Equal normal forms establish only candidate_equivalent_under_rewrite_set. This means the expressions converge under the active rules. It does not mean all mathematically equivalent expressions have been found, nor that each rule has been formally proved.

Use distinct statuses:
- candidate: proposed rule, no verified proof.
- finite_tested: checked against a declared finite test set.
- formally_proved: a proof artifact is available and independently checked.

## Next

1. Add a Lean bridge for the four initial rewrite laws.
2. Add polymorphic rules and typed metavariables.
3. Add critical-pair detection and confluence analysis.
4. Add a proof-producing normalizer whose output includes a derivation trace.
5. Connect rule and proof fingerprints to CACE evidence verification.
