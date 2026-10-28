#!/usr/bin/env python3
"""Deterministic, dependency-free toy baselines for residual physics workflows.

These checks validate a workflow, not any target physical model. Output is JSON
so results can be archived and compared across code revisions.
"""
from __future__ import annotations

import json
import math
import random


def frg_toy(step: float, t_end: float = 1.0, g0: float = 0.25) -> dict:
    # Toy beta(g) = -g + g^2. Exact solution for 0 < g0 < 1:
    # g(t) = g0 / (g0 + (1-g0) exp(t)).
    steps = round(t_end / step)
    actual_step = t_end / steps
    g = g0
    for _ in range(steps):
        g += actual_step * (-g + g * g)  # explicit Euler
    exact = g0 / (g0 + (1.0 - g0) * math.exp(t_end))
    return {
        "step": actual_step,
        "steps": steps,
        "g_numeric": g,
        "g_exact": exact,
        "absolute_error": abs(g - exact),
        "fixed_points": [0.0, 1.0],
        "beta_prime_at_fixed_points": [-1.0, 1.0],
    }


def bell_pair_entropy_toy(pair_count: int = 4) -> list[dict]:
    # A pure product of Bell pairs has entropy k*ln(2) when exactly k pairs
    # cross the A|B cut. This is an exact toy identity, not a dynamical Page curve.
    return [
        {"crossing_bell_pairs": k, "entropy_nats": k * math.log(2.0)}
        for k in range(pair_count + 1)
    ]


def affine_fixed_point_toy() -> dict:
    # A x + b = 0, A=[[2,1],[1,3]], b=[1,-1].
    # Exact solution x=(-4/5, 3/5), verified by the residual.
    x = (-0.8, 0.6)
    residual = (2.0 * x[0] + x[1] + 1.0,
                x[0] + 3.0 * x[1] - 1.0)
    return {
        "matrix": [[2, 1], [1, 3]],
        "offset": [1, -1],
        "solution": list(x),
        "residual": list(residual),
        "jacobian": [[2, 1], [1, 3]],
        "eigenvalues": [(5.0 - math.sqrt(5.0)) / 2.0,
                        (5.0 + math.sqrt(5.0)) / 2.0],
    }


def gaussian_mcmc_toy(seed: int = 20261027, draws: int = 50_000,
                      warmup: int = 5_000) -> dict:
    # Random-walk Metropolis for a standard normal target and symmetric N(0, 1)
    # proposal. The finite chain is empirical evidence only.
    rng = random.Random(seed)
    x = 0.0
    accepted = 0
    samples = []
    for i in range(draws + warmup):
        proposal = x + rng.gauss(0.0, 1.0)
        log_alpha = -0.5 * (proposal * proposal - x * x)
        if math.log(max(rng.random(), 1e-300)) < min(0.0, log_alpha):
            x = proposal
            accepted += 1
        if i >= warmup:
            samples.append(x)
    mean = sum(samples) / len(samples)
    variance = sum((v - mean) ** 2 for v in samples) / (len(samples) - 1)
    return {
        "target": "standard_normal",
        "seed": seed,
        "draws": draws,
        "warmup": warmup,
        "proposal_sd": 1.0,
        "acceptance_rate_including_warmup": accepted / (draws + warmup),
        "sample_mean": mean,
        "sample_variance": variance,
        "analytic_mean": 0.0,
        "analytic_variance": 1.0,
        "warning": "Toy chain diagnostics are empirical; no real cosmological posterior is tested.",
    }


def main() -> None:
    coarse = frg_toy(0.1)
    fine = frg_toy(0.05)
    report = {
        "schema_version": 1,
        "scope": "toy baselines only; no physical research claim",
        "frg_scalar_flow": {
            "equation": "dg/dt = -g + g^2",
            "coarse": coarse,
            "fine": fine,
            "error_ratio_coarse_over_fine": coarse["absolute_error"] / fine["absolute_error"],
        },
        "bell_pair_entropy": {
            "model": "product of Bell pairs; k pairs cross the bipartition",
            "values": bell_pair_entropy_toy(),
        },
        "affine_fixed_point": affine_fixed_point_toy(),
        "gaussian_mcmc": gaussian_mcmc_toy(),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
