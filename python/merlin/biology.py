"""Small, auditable biochemical kinetics and evolutionary fitting primitives.

These are deterministic educational/research models, not wet-lab protocols,
clinical models, or validated biological predictions.
"""
from __future__ import annotations

from math import ceil, exp, isfinite, sqrt
import random
from typing import Iterable


def _finite_nonnegative(name: str, value: float) -> float:
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


def michaelis_menten(substrate: float, vmax: float, km: float) -> float:
    substrate = _finite_nonnegative("substrate", substrate)
    vmax = _finite_nonnegative("vmax", vmax)
    km = float(km)
    if not isfinite(km) or km <= 0:
        raise ValueError("km must be finite and positive")
    return vmax * substrate / (km + substrate)


def hill_activation(concentration: float, half_response: float, hill_coefficient: float) -> float:
    concentration = _finite_nonnegative("concentration", concentration)
    half_response = float(half_response)
    hill_coefficient = float(hill_coefficient)
    if not isfinite(half_response) or half_response <= 0:
        raise ValueError("half_response must be finite and positive")
    if not isfinite(hill_coefficient) or hill_coefficient <= 0:
        raise ValueError("hill_coefficient must be finite and positive")
    if concentration == 0:
        return 0.0
    # Ratio form avoids unnecessary overflow for large concentrations.
    ratio = (half_response / concentration) ** hill_coefficient
    return 1.0 / (1.0 + ratio)


def simulate_enzyme_reaction(
    substrate0: float, vmax: float, km: float, duration: float, dt: float = 0.01
) -> dict:
    """Integrate dS/dt=-v(S), dP/dt=v(S) using fixed-step RK4."""
    substrate0 = _finite_nonnegative("substrate0", substrate0)
    vmax = _finite_nonnegative("vmax", vmax)
    km = float(km)
    duration = float(duration)
    dt = float(dt)
    if not isfinite(km) or km <= 0:
        raise ValueError("km must be finite and positive")
    if not isfinite(duration) or duration < 0:
        raise ValueError("duration must be finite and non-negative")
    if not isfinite(dt) or dt <= 0:
        raise ValueError("dt must be finite and positive")
    if duration == 0:
        return {"times": [0.0], "substrate": [substrate0], "product": [0.0], "mass_balance_error": 0.0}
    steps = max(1, ceil(duration / dt))
    step = duration / steps

    def derivative(s: float) -> float:
        return -michaelis_menten(max(0.0, s), vmax, km)

    s = substrate0
    times = [0.0]
    substrates = [s]
    products = [0.0]
    for index in range(steps):
        k1 = derivative(s)
        k2 = derivative(s + 0.5 * step * k1)
        k3 = derivative(s + 0.5 * step * k2)
        k4 = derivative(s + step * k3)
        s = min(substrate0, max(0.0, s + step * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0))
        t = (index + 1) * step
        times.append(t)
        substrates.append(s)
        products.append(substrate0 - s)
    error = max(abs((a + b) - substrate0) for a, b in zip(substrates, products))
    return {
        "times": times,
        "substrate": substrates,
        "product": products,
        "mass_balance_error": error,
        "model": "closed_single_substrate_michaelis_menten",
        "evidence_class": "HYPOTHESIS_ONLY",
    }


def fit_michaelis_menten(
    observations: Iterable[tuple[float, float]],
    vmax_bounds: tuple[float, float] = (0.01, 10.0),
    km_bounds: tuple[float, float] = (0.01, 10.0),
    population_size: int = 48,
    generations: int = 80,
    mutation_rate: float = 0.18,
    seed: int = 0,
) -> dict:
    """Fit Vmax/Km by a bounded, seeded evolutionary search minimizing MSE."""
    rows = [(float(s), float(v)) for s, v in observations]
    if len(rows) < 3:
        raise ValueError("at least three observations are required")
    if any(not isfinite(s) or s < 0 or not isfinite(v) or v < 0 for s, v in rows):
        raise ValueError("observations must be finite and non-negative")
    for name, bounds in (("vmax_bounds", vmax_bounds), ("km_bounds", km_bounds)):
        if len(bounds) != 2 or not all(isfinite(float(x)) for x in bounds) or float(bounds[0]) <= 0 or float(bounds[1]) <= float(bounds[0]):
            raise ValueError(f"{name} must be an increasing positive pair")
    if type(population_size) is not int or not 8 <= population_size <= 500:
        raise ValueError("population_size must be in [8,500]")
    if type(generations) is not int or not 1 <= generations <= 2000:
        raise ValueError("generations must be in [1,2000]")
    if not 0 < mutation_rate <= 1:
        raise ValueError("mutation_rate must be in (0,1]")

    vlo, vhi = map(float, vmax_bounds)
    klo, khi = map(float, km_bounds)
    rng = random.Random(seed)

    def score(candidate: tuple[float, float]) -> float:
        vmax, km = candidate
        return sum((michaelis_menten(s, vmax, km) - rate) ** 2 for s, rate in rows) / len(rows)

    def clamp(value: float, lo: float, hi: float) -> float:
        return min(hi, max(lo, value))

    population = [(rng.uniform(vlo, vhi), rng.uniform(klo, khi)) for _ in range(population_size)]
    for _ in range(generations):
        ranked = sorted(population, key=score)
        next_population = ranked[:2]
        while len(next_population) < population_size:
            contestants = rng.sample(ranked[:max(4, population_size // 2)], k=3)
            parent_a = min(contestants, key=score)
            contestants = rng.sample(ranked[:max(4, population_size // 2)], k=3)
            parent_b = min(contestants, key=score)
            alpha = rng.random()
            child_v = alpha * parent_a[0] + (1 - alpha) * parent_b[0]
            child_k = alpha * parent_a[1] + (1 - alpha) * parent_b[1]
            if rng.random() < mutation_rate:
                child_v += rng.gauss(0, (vhi - vlo) * 0.08)
            if rng.random() < mutation_rate:
                child_k += rng.gauss(0, (khi - klo) * 0.08)
            next_population.append((clamp(child_v, vlo, vhi), clamp(child_k, klo, khi)))
        population = next_population

    best = min(population, key=score)
    mse = score(best)
    return {
        "vmax": best[0],
        "km": best[1],
        "rmse": sqrt(mse),
        "seed": seed,
        "generations": generations,
        "population_size": population_size,
        "observation_count": len(rows),
        "evidence_class": "HYPOTHESIS_ONLY",
        "model": "michaelis_menten_parameter_fit",
        "note": "Evolutionary fit to supplied observations; independent validation is required.",
    }
