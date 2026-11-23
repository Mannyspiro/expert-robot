# Experiment -> Mathematics -> Efficiency Loop

CACE experiments should not only answer scientific questions. They should also
produce **mathematical research questions**.

The loop is:

```
simulation / physical experiment
  -> structured result data
  -> invariant/pattern miner
  -> conjecture candidates
  -> skeptic/counterexample search
  -> formalization proposal
  -> recursive lemma factory
  -> Lean proof search
  -> theorem registry
  -> optimization hypothesis
  -> ablation + benchmark
  -> blind holdout
  -> qualified optimization rule
  -> faster CACE
  -> new experiments
```

## Epistemic separation

Three claims remain distinct:

1. **Observed pattern** — finite data exhibited a pattern.
2. **Theorem** — Lean proved a mathematical statement from explicit assumptions.
3. **Optimization value** — benchmarks showed that using the theorem improves
   CACE resource use without changing verified results.

No layer substitutes for another.

## High-value mathematical structures to mine

### Symmetry and invariance

If simulations repeatedly produce invariant outputs under rotations,
reflections, permutations, coordinate changes, or gauge-like transforms, create
a conjecture.

If proved, CACE may reduce the domain or canonicalize equivalent states.

Potential gains:

- fewer mesh cells;
- fewer candidate geometries;
- smaller caches;
- reduced parameter sweeps;
- less theorem search duplication.

### Scaling and dimensionless structure

Search for relations such as

```
F(lambda x) = lambda^k F(x)
```

or collapse under dimensionless groups.

If formally proved for a supported model, solve one normalized problem and reuse
the result across a scale family.

### Monotonicity and bounds

A proved monotonicity theorem can let CACE prune whole portions of an
optimization/search space without evaluating them.

### Periodicity

For lattices and metamaterials, observed translational symmetry can inspire
periodicity lemmas. Formalized symmetry plus valid PDE assumptions can justify
unit-cell/domain reduction. Numerical Bloch/Floquet calculations still require
their own certification.

### Operator factorization / separability

Experiments may reveal repeated block, tensor-product, sparse, low-rank, or
decoupled structure.

A proved factorization can turn a large solve into several smaller solves.

### Error laws

Adaptive-mesh runs can suggest relationships between local geometry,
regularity, residual indicators, and actual error. These can become conjectures
for tighter a-posteriori estimators.

If proved, CACE may refine fewer cells for the same certified error tolerance.

## Counterexample-first policy

Before expensive proof search, Expert Robot should actively try to break the
candidate:

- adversarial parameter values;
- boundary cases;
- degenerate geometry;
- alternate coordinate frames;
- random exact examples;
- known theorem-graph contradictions.

A found counterexample is valuable information and should be stored.

## Promotion into runtime optimization

A proved theorem is still *not* automatically an optimization.

To alter CACE execution, the derived rule must also pass:

```
formal proof
+ applicability preconditions
+ implementation equivalence tests
+ benchmark gain
+ blind holdout non-regression
+ rollback
+ lineage
+ authority_same_or_less
= qualified optimization
```

## Examples of self-efficiency gains

- prove rotational equivalence -> simulate one canonical orientation;
- prove distance symmetry -> canonicalize pair cache keys;
- prove periodicity -> operate on one fundamental cell;
- prove operator block decomposition -> solve blocks independently;
- prove monotone bound -> prune dominated design candidates;
- prove rescaling equivalence -> cache normalized solution families;
- prove local error dominance -> refine only cells that can affect certificate;
- prove graph isomorphism invariance -> deduplicate equivalent research objects.

This is **verified self-improvement**: experiments may suggest shortcuts, but
formal proof controls correctness and benchmarks control whether the shortcut is
worth using.
