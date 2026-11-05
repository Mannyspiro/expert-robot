"""Real, bounded local mathematical-discovery backends.

These functions adapt the repository's RK4 solver and provide an exact finite
search for cyclic translations. The search result is bounded evidence, never a
universal proof. The Ideonomy bridge is deliberately restricted to the
round-robin/event-queue analogy and emits a precise, independently checkable
group-theoretic claim rather than theorem-shaped prose.
"""
from __future__ import annotations

import platform
import sys
from typing import Any, Mapping

from merlin.linear_simulation import simulate_linear_ode

RK4_ENGINE = "merlin-rk4-linear-ode/1"
RK4_ENGINE_VERSION = "1"
COUNTEREXAMPLE_ENGINE = "merlin-finite-cyclic-translation-search/1"
COUNTEREXAMPLE_ENGINE_VERSION = "1"


def rk4_solver(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Run the actual in-repository RK4 integrator from a normalized spec."""
    p = spec.get("parameters")
    if not isinstance(p, Mapping):
        raise ValueError("RK4 parameters must be an object")
    result = simulate_linear_ode(
        p.get("matrix", []), p.get("initial_state", []),
        start=p.get("start", 0.0), stop=p.get("stop"),
        step=p.get("step"), input_vector=p.get("input_vector"),
        input_value=p.get("input_value", 0.0),
        max_steps=int(p.get("max_steps", 10000)),
    )
    return {
        "engine": RK4_ENGINE,
        "engine_version": RK4_ENGINE_VERSION,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": sys.platform,
        "result": result,
    }


def finite_cyclic_translation_search(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Exhaustively test x -> x+k on Z/nZ over explicit finite bounds."""
    if spec.get("search_domain") != "cyclic_translation_bijectivity":
        raise ValueError("unsupported finite-search domain")
    bounds = spec.get("bounds")
    if not isinstance(bounds, Mapping):
        raise ValueError("finite search requires explicit bounds")
    n_min, n_max = bounds.get("n_min"), bounds.get("n_max")
    k_min, k_max = bounds.get("k_min"), bounds.get("k_max")
    values = (n_min, n_max, k_min, k_max)
    if any(isinstance(v, bool) or not isinstance(v, int) for v in values):
        raise ValueError("all finite-search bounds must be integers")
    if n_min < 1 or n_max < n_min or n_max - n_min > 1000:
        raise ValueError("n bounds must be ordered and span at most 1000 values")
    if k_max < k_min or k_max - k_min > 10000:
        raise ValueError("k bounds must be ordered and span at most 10000 values")
    examined = 0
    for n in range(n_min, n_max + 1):
        for k in range(k_min, k_max + 1):
            images = [(x + k) % n for x in range(n)]
            examined += n
            if len(set(images)) != n:
                return {
                    "termination_status": "counterexample_found",
                    "counterexample": {"n": n, "k": k, "images": images},
                    "examined_points": examined,
                }
    return {
        "termination_status": "complete",
        "counterexample": None,
        "examined_points": examined,
    }


def round_robin_ideonomy_claim(proposal: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Translate only the event-queue + locality simplex into cyclic algebra."""
    ids = set(proposal.get("source_ids", []))
    if not {"event-queue", "cpu-locality"}.issubset(ids):
        return None
    theorem = (
        "Function.Bijective (fun x : ZMod n => x + k)"
    )
    lean_source = """import Mathlib

/-- Adding a fixed offset permutes the finite cyclic state space.
This is the algebraic basis for a round-robin queue's cyclic successor map. -/
theorem cyclicTranslation_bijective (n : Nat) (k : ZMod n) :
    Function.Bijective (fun x : ZMod n => x + k) := by
  constructor
  · intro x y h
    exact add_right_cancel h
  · intro y
    refine ⟨y - k, ?_⟩
    simp
"""
    return {
        "assumptions": [
            "The queue positions are represented by the additive cyclic group ZMod n.",
            "The transition adds one fixed offset k and does not mutate the modulus during a transition.",
        ],
        "falsifiable_statement": (
            "Within any tested finite range of n and k, a counterexample would be "
            "a collision in x -> x+k modulo n or a missing residue in its image."
        ),
        "formal_statement": theorem,
        "lean_source": lean_source,
        "source_identity": {
            "primitive_ids": sorted(ids),
            "mathematical_bridge": "round-robin queue position update is translation in a cyclic group",
            "source_kind": "Ideonomy functional analogy; not a proof premise",
        },
        "claim_kind": "mathematical_model_of_round_robin_state_transition",
        "epistemic_status": "proposed_unproved_conjecture",
        "lean_translation_eligible": True,
    }


def default_runtime_environment() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": sys.platform,
        "rk4_engine": RK4_ENGINE,
        "counterexample_engine": COUNTEREXAMPLE_ENGINE,
    }


__all__ = [
    "RK4_ENGINE", "RK4_ENGINE_VERSION", "COUNTEREXAMPLE_ENGINE",
    "COUNTEREXAMPLE_ENGINE_VERSION", "rk4_solver",
    "finite_cyclic_translation_search", "round_robin_ideonomy_claim",
    "default_runtime_environment",
]
