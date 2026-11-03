"""Repeatable scenario experiments over Merlin's deterministic simulator."""
from __future__ import annotations
from copy import deepcopy
from statistics import mean, pstdev
from typing import Any
from .simulation import MerlinSimulation

SCENARIOS = {
    "steady_research": ("advance", "advance", "verify", "advance", "advance", "verify"),
    "uncertainty_recovery": ("advance", "inject_uncertainty", "decompose", "advance", "verify"),
    "resource_pressure": ("explore", "explore", "compress", "decompose", "verify"),
}

def run_scenario(actions: tuple[str, ...], seed: int = 0) -> dict[str, Any]:
    if not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    sim = MerlinSimulation()
    for action in actions:
        sim.step(action)
    state = sim.snapshot()["state"]
    keys = ("tick", "progress", "confidence", "uncertainty", "cpu_percent",
            "memory_mb", "queue_depth", "verified_claims", "candidate_hypotheses")
    return {"schema": "merlin-scenario-result/1",
            "environment": "deterministic_simulation", "seed": seed,
            "actions": list(actions), "final": {key: state[key] for key in keys},
            "metrics": deepcopy(state["metrics"]), "events": deepcopy(state["events"]),
            "promotion_authorized": False}

def compare_scenarios(scenarios: dict[str, tuple[str, ...]],
                      seeds: tuple[int, ...] = (11, 23, 47)) -> dict[str, Any]:
    if not seeds:
        raise ValueError("at least one seed is required")
    rows = {}
    for name, actions in scenarios.items():
        if not name or not actions:
            raise ValueError("scenario names and action sequences must be non-empty")
        rows[name] = [run_scenario(actions, seed) for seed in seeds]
    summary = {}
    for name, results in rows.items():
        progress = [r["final"]["progress"] for r in results]
        verified = [r["final"]["verified_claims"] for r in results]
        uncertainty = [r["final"]["uncertainty"] for r in results]
        summary[name] = {"trials": len(results), "progress_mean": mean(progress),
            "progress_sd": pstdev(progress), "verified_claims_mean": mean(verified),
            "uncertainty_mean": mean(uncertainty),
            "resource_peak_mb": max(r["final"]["memory_mb"] for r in results)}
    return {"schema": "merlin-scenario-comparison/1",
            "environment": "deterministic_simulation", "paired_seeds": list(seeds),
            "summary": summary, "trial_results": rows,
            "causal_claims_supported": False, "promotion_authorized": False,
            "note": "Seeds are recorded but do not yet randomize this deterministic world."}

def replay_actions(actions: tuple[str, ...]) -> dict[str, Any]:
    return run_scenario(actions, seed=0)
