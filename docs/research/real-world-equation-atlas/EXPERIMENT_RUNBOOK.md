# Reproducible experiment runbook

## Environment
- Python 3.10+ recommended.
- NumPy 2.x and SymPy 1.12+ for the current starter experiments/checks.
- No network data is downloaded at runtime.
- All current baseline examples are deterministic; no random generator is used.

## Commands
```bash
PYTHONPATH=python python -m merlin.equation_atlas.dimensions
PYTHONPATH=python python -m merlin.equation_atlas.symbolic_checks
PYTHONPATH=python python -m merlin.equation_atlas.experiments.baseline
PYTHONPATH=python python -m unittest discover -s tests -p 'test_merlin_equation_atlas.py'
```

## Experiment definitions
- **Optimization:** fixed area 12 m²; compare perimeter and analytic square optimum.
- **Least squares:** ten deterministic points from y=2.5x−1.25 plus a fixed perturbation vector; solve by NumPy least squares.
- **Heat:** 1-D diffusion on [0,1], Dirichlet zero boundaries, initial sin(πx), α=0.01, 51 nodes, explicit FTCS, λ=αΔt/Δx²=0.4. For this one-dimensional scheme the standard stability bound is λ≤1/2.
- **Logistic growth:** RK4, r=0.35 per time unit, K=1000, N(0)=80, dt=0.1, duration 20.
- **Fourier sampling:** 5 Hz sine sampled at 64 Hz for one second; dominant FFT bin is expected at 5 Hz.

## Interpretation limits
These are synthetic sanity-check experiments, not empirical validations of any industrial, biological, or medical system. Heat stability is specific to the stated explicit 1-D scheme. Numerical results are regression baselines, not universal performance claims.
