# Merlin Glyph Foundry v0.1

**Status:** prototype implementation. Nine local unit tests passed in the authoring environment. Formal Lean verification and repository CI have not yet been run.

## Purpose

The Glyph Foundry synthesizes higher-order operators from a small typed basis. It separates candidate invention from trust and promotion. Expression trees are immutable, type-checked, structurally fingerprinted, and evaluated only through explicitly registered primitive functions. Generated source code is never executed.

## Implemented

- Typed TypeRef, Primitive, Predicate, and immutable Expr nodes.
- Composition with type compatibility checks and identity elimination.
- Pair construction and projections.
- Equality expressions and typed runtime constraints.
- Deterministic structural fingerprints.
- Bounded composition enumeration with in-process deduplication.
- Candidate evidence states and promotion gates.
- Promotion requires test receipts, a formal-proof receipt, independent-review receipt, and benchmark improvement over a baseline.

## Important interpretation

The proof and review receipt fields currently hold identifiers; they do not cryptographically validate external evidence. Production integration must resolve each receipt against actual Lean/CACE artifacts and verify repository commit, toolchain, assumptions, data hashes, and provenance.

The local unit tests verify Python implementation behavior. They do not formally prove the mathematical semantics.

The initial executable examples are integer identity, negation, absolute value, and integer-to-float embedding. PAIR, PROJECT, EQUAL, CONSTRAIN, and COMPOSE are typed AST constructors. This is a narrow first slice, not a claim that the complete eight-operator mathematical basis is formally verified.

## Search model

The mathematical composition space can be unbounded, but each execution run has explicit limits: maximum expression depth, maximum AST node count, and maximum candidates per slice. The current in-memory seen-set deduplicates within one process only. A persistent search cursor and content-addressed candidate store are required before large-scale exploration.

## Promotion rule

A candidate is not trusted because it was generated, executed, or cached. Promotion requires:

1. Reproducible tests.
2. A formal proof receipt where the claim is formalizable.
3. Independent review.
4. Benchmark evidence of improvement over a declared baseline.

A benchmark must name its metric, direction of improvement, dataset/input hash, seed, environment, and uncertainty. Candidate value should be scoped to a domain and benchmark suite rather than treated as universal superiority.

## Next milestones

1. Replace stringly typed receipts with typed, verifiable evidence records.
2. Add polymorphic type variables and multi-argument operators.
3. Add rewrite rules with proof obligations and termination checks.
4. Add breadth-first/A-star search, persistent cursors, and cost-aware enumeration.
5. Add benchmark suites for expression compression, evaluation cost, and mathematical usefulness.
6. Formalize identity, composition associativity, pair/projection laws, and type preservation in Lean.
7. Connect candidate records to Merlin's knowledge graph and CACE qualification.
8. Add an Avrea adapter only after its actual runner/cache interface is available.
