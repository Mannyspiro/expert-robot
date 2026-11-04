"""Deterministic baseline experiments for Merlin's equation atlas.

Run from repository root:
    python -m merlin.equation_atlas.experiments.baseline
Requires NumPy. Outputs JSON to stdout; no network access or external data.
"""
import json
import math
import numpy as np
from merlin.equation_atlas.experiments.signal_processing import run_signal_checks

def logistic_rk4(r=0.35, capacity=1000.0, initial=80.0, dt=0.1, duration=20.0):
    steps = int(round(duration / dt))
    value = float(initial)
    def rhs(z):
        return r * z * (1.0 - z / capacity)
    for _ in range(steps):
        k1 = rhs(value)
        k2 = rhs(value + 0.5 * dt * k1)
        k3 = rhs(value + 0.5 * dt * k2)
        k4 = rhs(value + dt * k3)
        value += (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
    return value

def heat_ftcs(nx=51, alpha=0.01, steps=100, courant=0.4):
    dx = 1.0 / (nx - 1)
    dt = courant * dx * dx / alpha
    x = np.linspace(0.0, 1.0, nx)
    u = np.sin(np.pi * x)
    lam = alpha * dt / (dx * dx)
    if lam > 0.5:
        raise ValueError("1-D explicit heat FTCS stability condition violated")
    for _ in range(steps):
        old = u.copy()
        u[1:-1] = old[1:-1] + lam * (old[2:] - 2*old[1:-1] + old[:-2])
        u[0] = 0.0
        u[-1] = 0.0
    return {"lambda": float(lam), "center_value": float(u[nx//2]), "stable": bool(lam <= 0.5)}

def run():
    area = 12.0
    side = math.sqrt(area)
    # Least-squares regression with deterministic, fixed perturbations.
    x = np.arange(10, dtype=float)
    noise = np.array([0.10, -0.10, 0.05, 0.0, -0.05, 0.08, -0.08, 0.02, -0.02, 0.0])
    y = 2.5*x - 1.25 + noise
    slope, intercept = np.linalg.lstsq(np.column_stack((x, np.ones_like(x))), y, rcond=None)[0]

    # One-second sampled record of a 5 Hz sinusoid at 64 samples/second.
    fs, f0 = 64.0, 5.0
    t = np.arange(0.0, 1.0, 1.0/fs)
    signal = np.sin(2.0*np.pi*f0*t)
    frequencies = np.fft.rfftfreq(signal.size, d=1.0/fs)
    amplitudes = np.abs(np.fft.rfft(signal))
    peak_hz = float(frequencies[1 + np.argmax(amplitudes[1:])])

    return {
        "experiment_set": "merlin-equation-atlas-baseline-v0.1",
        "seed": "not_applicable_no_random_sampling",
        "optimization": {
            "fixed_area_m2": area,
            "optimal_square_side_m": side,
            "minimum_perimeter_m": 4.0*side,
            "analytic_solution": "square",
        },
        "least_squares": {
            "true_slope": 2.5,
            "estimated_slope": float(slope),
            "estimated_intercept": float(intercept),
            "observations": int(x.size),
        },
        "heat_equation_ftcs": heat_ftcs(),
        "logistic_rk4": {
            "r_per_time_unit": 0.35,
            "capacity_population": 1000.0,
            "initial_population": 80.0,
            "duration_time_units": 20.0,
            "dt_time_units": 0.1,
            "population_at_end": logistic_rk4(),
        },
        "signal_processing_checks": run_signal_checks(),
        "fourier_sampling": {
            "sample_rate_hz": fs,
            "input_frequency_hz": f0,
            "dominant_fft_bin_hz": peak_hz,
            "record_duration_s": 1.0,
        },
    }

if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
