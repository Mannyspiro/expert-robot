"""Small, auditable numerical execution primitives for Merlin XMG.

Scope: explicit-Euler toy solvers and direct-method SSA. These routines are
reference implementations for synthetic tests, not production scientific
solvers. Stability, units, boundary conditions, and model assumptions remain
the caller's responsibility and are recorded in run metadata.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Callable, Sequence

import numpy as np


@dataclass(frozen=True)
class SimulationConfig:
    dt: float
    steps: int
    seed: int = 0
    method: str = "explicit_euler"


@dataclass
class SimulationResult:
    states: list[list[float]]
    times: list[float]
    metadata: dict


def _canonical_hash(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _array_hash(array: np.ndarray) -> str:
    a = np.ascontiguousarray(array, dtype=np.float64)
    return hashlib.sha256(a.tobytes()).hexdigest()


def _validate_config(config: SimulationConfig) -> None:
    if not np.isfinite(config.dt) or config.dt <= 0:
        raise ValueError("dt must be finite and positive")
    if config.steps < 0:
        raise ValueError("steps must be nonnegative")
    if config.method != "explicit_euler":
        raise ValueError("only explicit_euler is currently implemented")


def explicit_euler(
    initial_state: Sequence[float],
    rhs: Callable[[np.ndarray, float], np.ndarray],
    config: SimulationConfig,
    *,
    model_id: str,
    parameters: dict,
    boundary_conditions: str,
    code_revision: str = "untracked",
) -> SimulationResult:
    """Integrate a declared RHS and retain every state for inspectability."""
    _validate_config(config)
    state = np.asarray(initial_state, dtype=float)
    if state.ndim != 1 or not np.all(np.isfinite(state)):
        raise ValueError("initial_state must be a finite one-dimensional vector")
    initial_hash = _array_hash(state)
    states = [state.copy()]
    times = [0.0]
    for index in range(config.steps):
        derivative = np.asarray(rhs(state.copy(), index * config.dt), dtype=float)
        if derivative.shape != state.shape or not np.all(np.isfinite(derivative)):
            raise ValueError(f"RHS returned invalid derivative at step {index}")
        state = state + config.dt * derivative
        if not np.all(np.isfinite(state)):
            raise FloatingPointError(f"non-finite state at step {index}")
        states.append(state.copy())
        times.append((index + 1) * config.dt)
    metadata = {
        "schema": "merlin-simulation-run/0.1",
        "model_id": model_id,
        "method": config.method,
        "dt": config.dt,
        "steps": config.steps,
        "seed": config.seed,
        "boundary_conditions": boundary_conditions,
        "initial_state_sha256": initial_hash,
        "parameters_sha256": _canonical_hash(parameters),
        "code_revision": code_revision,
        "final_state_sha256": _array_hash(state),
        "status": "SYNTHETIC_NUMERICAL_RUN_NOT_EMPIRICAL_VALIDATION",
    }
    metadata["run_sha256"] = _canonical_hash(metadata)
    return SimulationResult(
        states=[row.tolist() for row in states],
        times=times,
        metadata=metadata,
    )


def periodic_diffusion_rhs(diffusivity: float, dx: float) -> Callable:
    """Return 1-D periodic centered-difference diffusion RHS."""
    if diffusivity < 0 or dx <= 0:
        raise ValueError("diffusivity must be nonnegative and dx positive")
    return lambda u, _t: diffusivity * (np.roll(u, 1) - 2*u + np.roll(u, -1)) / dx**2


def periodic_upwind_advection_rhs(velocity: float, dx: float) -> Callable:
    """Return first-order upwind periodic advection RHS."""
    if dx <= 0:
        raise ValueError("dx must be positive")
    if velocity >= 0:
        return lambda u, _t: -velocity * (u - np.roll(u, 1)) / dx
    return lambda u, _t: -velocity * (np.roll(u, -1) - u) / dx


def graph_exchange_rhs(adjacency: Sequence[Sequence[float]], rate: float) -> Callable:
    """Balanced pairwise exchange on an undirected weighted graph."""
    graph = np.asarray(adjacency, dtype=float)
    if graph.ndim != 2 or graph.shape[0] != graph.shape[1]:
        raise ValueError("adjacency must be square")
    if not np.all(np.isfinite(graph)) or np.any(graph < 0):
        raise ValueError("adjacency weights must be finite and nonnegative")
    if not np.allclose(graph, graph.T, atol=1e-12):
        raise ValueError("balanced exchange requires symmetric adjacency")
    if not np.allclose(np.diag(graph), 0.0):
        raise ValueError("self-loops are not supported")
    if rate < 0:
        raise ValueError("rate must be nonnegative")
    laplacian = np.diag(graph.sum(axis=1)) - graph
    return lambda x, _t: -rate * (laplacian @ x)


def run_gillespie_ssa(
    initial_counts: Sequence[int],
    stoichiometry: Sequence[Sequence[int]],
    propensity: Callable[[np.ndarray], Sequence[float]],
    end_time: float,
    *,
    seed: int,
    model_id: str,
    parameters: dict,
    code_revision: str = "untracked",
    max_events: int = 1_000_000,
) -> dict:
    """Direct-method SSA for a finite reaction network."""
    state = np.asarray(initial_counts, dtype=int)
    nu = np.asarray(stoichiometry, dtype=int)
    if state.ndim != 1 or np.any(state < 0):
        raise ValueError("initial counts must be a nonnegative vector")
    if nu.ndim != 2 or nu.shape[1] != state.size:
        raise ValueError("stoichiometry must have shape (reactions, species)")
    if end_time < 0 or not np.isfinite(end_time):
        raise ValueError("end_time must be finite and nonnegative")
    rng = np.random.default_rng(seed)
    states, times, events = [state.copy()], [0.0], []
    t = 0.0
    while t < end_time and len(events) < max_events:
        rates = np.asarray(propensity(state.copy()), dtype=float)
        if rates.shape != (nu.shape[0],) or not np.all(np.isfinite(rates)) or np.any(rates < 0):
            raise ValueError("propensities must be finite nonnegative rates per reaction")
        total = float(rates.sum())
        if total == 0.0:
            break
        tau = float(rng.exponential(1.0 / total))
        if t + tau > end_time:
            break
        reaction = int(rng.choice(len(rates), p=rates / total))
        candidate = state + nu[reaction]
        if np.any(candidate < 0):
            raise ValueError("reaction propensity selected an update that makes counts negative")
        t += tau
        state = candidate
        states.append(state.copy())
        times.append(t)
        events.append(reaction)
    if len(events) >= max_events and t < end_time:
        raise RuntimeError("max_events reached before end_time")
    result = {
        "schema": "merlin-ssa-run/0.1",
        "model_id": model_id,
        "seed": seed,
        "end_time": end_time,
        "times": times,
        "states": [x.tolist() for x in states],
        "reaction_indices": events,
        "parameters_sha256": _canonical_hash(parameters),
        "initial_state_sha256": _array_hash(np.asarray(initial_counts, dtype=float)),
        "final_state_sha256": _array_hash(state.astype(float)),
        "code_revision": code_revision,
        "status": "SYNTHETIC_STOCHASTIC_RUN_NOT_EMPIRICAL_VALIDATION",
    }
    result["run_sha256"] = _canonical_hash(result)
    return result
