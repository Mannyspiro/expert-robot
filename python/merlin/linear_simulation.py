"""Bounded deterministic RK4 backend for linear continuous-time models.

The solver is intentionally narrow and auditable: dx/dt = A x + b u.
It is a real numerical integrator, not a general-purpose symbolic simulator.
"""
from __future__ import annotations

import json
import math
from typing import Any, Callable, Mapping, Sequence


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + " must be a finite number")
    return float(value)


def simulate_linear_ode(
    matrix: Sequence[Sequence[float]],
    initial_state: Sequence[float],
    *,
    start: float = 0.0,
    stop: float,
    step: float,
    input_vector: Sequence[float] | None = None,
    input_value: float = 0.0,
    max_steps: int = 100000,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Integrate dx/dt=A*x+b*u using classical fourth-order Runge-Kutta."""
    n = len(initial_state) if isinstance(initial_state, Sequence) else 0
    if not 1 <= n <= 64 or len(matrix) != n:
        raise ValueError("matrix and state dimensions must agree and be between 1 and 64")
    a = [[_finite(v, "matrix entry") for v in row] for row in matrix]
    if any(len(row) != n for row in a):
        raise ValueError("A must be a square matrix matching the state dimension")
    x0 = [_finite(v, "initial state") for v in initial_state]
    t0, tf, dt = _finite(start, "start"), _finite(stop, "stop"), _finite(step, "step")
    u = _finite(input_value, "input value")
    if tf <= t0 or dt <= 0:
        raise ValueError("stop must exceed start and step must be positive")
    steps = math.ceil((tf - t0) / dt)
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or not 1 <= max_steps <= 1000000 or steps > max_steps:
        raise ValueError("simulation exceeds max_steps")
    b = [0.0] * n if input_vector is None else [_finite(v, "input vector") for v in input_vector]
    if len(b) != n:
        raise ValueError("input_vector must match state dimension")

    def derivative(state):
        return [sum(a[i][j] * state[j] for j in range(n)) + b[i] * u for i in range(n)]

    def add(state, delta, scale):
        return [state[i] + scale * delta[i] for i in range(n)]

    state = x0[:]
    samples = [{"t": t0, "state": state[:]}]
    t = t0
    for index in range(steps):
        h = min(dt, tf - t)
        k1 = derivative(state)
        k2 = derivative(add(state, k1, h / 2))
        k3 = derivative(add(state, k2, h / 2))
        k4 = derivative(add(state, k3, h))
        state = [
            state[i] + h * (k1[i] + 2*k2[i] + 2*k3[i] + k4[i]) / 6
            for i in range(n)
        ]
        if any(not math.isfinite(v) for v in state):
            raise FloatingPointError("simulation diverged to a non-finite state")
        t = min(tf, t + h)
        samples.append({"t": t, "state": state[:]})
        if progress is not None and ((index + 1) % 100 == 0 or index + 1 == steps):
            progress(index + 1, steps)
    return {
        "schema": "merlin-linear-ode-result/1",
        "engine": "merlin-rk4-linear-ode/1",
        "equation": "dx/dt = A*x + b*u",
        "matrix": a,
        "input_vector": b,
        "input_value": u,
        "initial_state": x0,
        "start": t0,
        "stop": tf,
        "step": dt,
        "steps": steps,
        "series": [
            {"name": "state_" + str(i), "points": [
                {"x": sample["t"], "y": sample["state"][i]} for sample in samples
            ]}
            for i in range(n)
        ],
        "samples": samples,
    }


def linear_ode_task_executor(task: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Hermes numerical-experiment executor for a declared linear ODE model."""
    spec = task.get("experiment_spec")
    if not isinstance(spec, Mapping) or spec.get("engine") != "merlin-rk4-linear-ode/1":
        raise ValueError("numerical task must declare engine=merlin-rk4-linear-ode/1")
    budget = context.resource_budget
    max_steps = min(100000, max(1, int(budget.get("compute_budget_units", 1))))
    result = simulate_linear_ode(
        spec.get("matrix", []), spec.get("initial_state", []),
        start=spec.get("start", 0.0), stop=spec.get("stop"),
        step=spec.get("step"), input_vector=spec.get("input_vector"),
        input_value=spec.get("input_value", 0.0), max_steps=max_steps,
        progress=lambda done, total: context.emit_progress(
            "RK4 integration progress", {"steps_completed": done, "steps_total": total}
        ),
    )
    encoded = (json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    return {
        "artifact_bytes": encoded,
        "media_type": "application/vnd.merlin.linear-ode+json",
        "summary": "RK4 integration completed in " + str(result["steps"]) + " steps",
        "metadata": {"engine": result["engine"],
                     "tool_identity": result["engine"],
                     "steps": result["steps"],
                     "state_dimension": len(result["initial_state"])},
    }


__all__ = ["simulate_linear_ode", "linear_ode_task_executor"]
