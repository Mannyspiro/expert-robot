# Verification plan: symbolic, dimensional, numerical, and Lean layers

## Evidence layers

1. **Symbolic:** algebraic identities, derivatives, equilibria, matrix shapes, exact simplifications.
2. **Dimensional:** every additive term has the same physical dimension; both sides of an equation match.
3. **Numerical:** deterministic reference experiments, convergence/stability sweeps, residuals, and regression tests.
4. **Empirical:** compare against independent measurements or benchmark datasets; include uncertainty and provenance.
5. **Formal:** Lean proves mathematical statements under explicit assumptions. Formal proof does not establish empirical adequacy.

## Implemented starter checks

- `python/merlin/equation_atlas/dimensions.py`: SI base-dimension algebra and eight representative homogeneity checks.
- `python/merlin/equation_atlas/symbolic_checks.py`: optimization derivative, logistic equilibria, least-squares gradient shape.
- `python/merlin/equation_atlas/experiments/baseline.py`: deterministic optimization, least-squares, explicit heat solver, logistic RK4, and FFT examples.
- `tests/test_merlin_equation_atlas.py`: regression tests for the starter layer.
- `lean/MerlinEquationAtlas/Basic.lean`: exact algebraic inequalities and normalized logistic positivity statements.
- `docs/research/real-world-equation-atlas/NORMALIZED_ENTRIES_001-020.json`: first normalized metadata tranche.

## Run

From repository root, with `python/` on PYTHONPATH:

```bash
PYTHONPATH=python python -m merlin.equation_atlas.dimensions
PYTHONPATH=python python -m merlin.equation_atlas.symbolic_checks
PYTHONPATH=python python -m merlin.equation_atlas.experiments.baseline
PYTHONPATH=python python -m unittest discover -s tests -p 'test_merlin_equation_atlas.py'
```

Lean project must use the repository's pinned Lean/mathlib toolchain. From its configured Lean project root:

```bash
lake env lean lean/MerlinEquationAtlas/Basic.lean
```

## Promotion gates

- No entry is FORMALLY_VERIFIED until the exact repository-pinned Lean toolchain compiles the theorem.
- No numerical experiment is REPRODUCED until the script runs in CI and its output is archived with code revision, environment, and tolerance.
- A symbolic identity is not a physical validation.
- Dimensional homogeneity is necessary, not sufficient.
- Numerical stability is scheme- and regime-specific.
- For stochastic experiments, pin generator, seed, version, and sampling procedure.
- For measured data, record data provenance, calibration, uncertainty, exclusions, and train/test split.
