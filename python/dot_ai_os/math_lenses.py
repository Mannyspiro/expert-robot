"""Bounded reference lenses, aligned with Merlin's continuum/simplex contracts.

These compute declared mathematical models, not probability, physical synergy,
field existence, independent verification or permission to act.
"""
from __future__ import annotations

import math
from typing import Any

LENSES = ("simplex", "n_ality", "continuum", "fuzzy_logic")
CANONICAL_CONTRACT = "cpp/include/expert_robot/math/continuum_simplex.hpp"


def _finite(x: Any) -> float:
    if type(x) not in (int, float) or abs(x) > 1e12 or not math.isfinite(x):
        raise ValueError("bounded finite real required")
    return float(x)


def _unit(x: Any) -> float:
    value = _finite(x)
    if not 0 <= value <= 1:
        raise ValueError("value must lie in [0,1]")
    return value


def simplex_weights(values: tuple[float, ...]) -> tuple[float, ...]:
    """Validate a point of the standard simplex; never silently normalize."""
    if type(values) is not tuple or not 2 <= len(values) <= 16:
        raise ValueError("2..16 simplex coordinates required")
    result = tuple(_unit(x) for x in values)
    if not math.isclose(math.fsum(result), 1.0, rel_tol=0, abs_tol=1e-12):
        raise ValueError("simplex coordinates must sum to one")
    return result


def convex_blend(vertices: tuple[tuple[float, ...], ...], weights: tuple[float, ...]) -> tuple[float, ...]:
    """Affine blend; does not certify affine independence or physical semantics."""
    w = simplex_weights(weights)
    if (type(vertices) is not tuple or len(vertices) != len(w)
            or any(type(row) is not tuple for row in vertices)
            or not 1 <= len(vertices[0]) <= 12
            or any(len(row) != len(vertices[0]) for row in vertices)):
        raise ValueError("bounded equally dimensioned vertices required")
    v = tuple(tuple(_finite(x) for x in row) for row in vertices)
    return tuple(math.fsum(w[i] * v[i][j] for i in range(len(w))) for j in range(len(v[0])))


def n_ality_signature(geometric_dimension: int, state_dimension: int,
                     logical_channels: int, temporal_parameters: int) -> dict[str, int]:
    fields = {"geometric_dimension": geometric_dimension, "state_dimension": state_dimension,
              "logical_channels": logical_channels, "temporal_parameters": temporal_parameters}
    for name, value in fields.items():
        minimum = 0 if name in {"geometric_dimension", "temporal_parameters"} else 1
        if type(value) is not int or not minimum <= value <= 16:
            raise ValueError("independent bounded n-ality axes required")
    return fields


def continuum_interpolate(samples: tuple[tuple[float, tuple[float, ...]], ...], t: float) -> tuple[float, ...]:
    """Evaluate a declared piecewise-linear field on [0,1], no extrapolation."""
    parameter = _unit(t)
    if type(samples) is not tuple or not 2 <= len(samples) <= 128:
        raise ValueError("2..128 explicit continuum samples required")
    rows = []
    for sample in samples:
        if type(sample) is not tuple or len(sample) != 2 or type(sample[1]) is not tuple or not 1 <= len(sample[1]) <= 12:
            raise ValueError("sample is (parameter, state tuple)")
        rows.append((_unit(sample[0]), tuple(_finite(x) for x in sample[1])))
    if (rows[0][0] != 0 or rows[-1][0] != 1
            or any(len(row[1]) != len(rows[0][1]) for row in rows)
            or any(b[0] <= a[0] for a, b in zip(rows, rows[1:]))):
        raise ValueError("consistent state dimensions and strictly ordered endpoint samples required")
    for a, b in zip(rows, rows[1:]):
        if a[0] <= parameter <= b[0]:
            local = (parameter - a[0]) / (b[0] - a[0])
            return convex_blend((a[1], b[1]), (1 - local, local))
    raise ValueError("parameter outside sample domain")


def fuzzy_membership(value: float, low: float, high: float) -> float:
    """Declared increasing ramp; thresholds/units must be supplied by the model."""
    x, lo, hi = _finite(value), _finite(low), _finite(high)
    if hi <= lo:
        raise ValueError("strictly ordered membership thresholds required")
    return min(1.0, max(0.0, (x - lo) / (hi - lo)))


def fuzzy_combine(values: tuple[float, ...], operator: str) -> float:
    """Explicit min t-norm / max t-conorm, not probabilities or gate overrides."""
    if type(values) is not tuple or not 1 <= len(values) <= 32 or not isinstance(operator, str) or operator not in {"and_min", "or_max"}:
        raise ValueError("bounded memberships and explicit supported fuzzy operator required")
    memberships = tuple(_unit(x) for x in values)
    return min(memberships) if operator == "and_min" else max(memberships)


def representation_checks(checks: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Always assess every lens without forcing an irrelevant representation."""
    if type(checks) is not dict or set(checks) != set(LENSES):
        raise ValueError("all four representation lenses must be considered")
    for value in checks.values():
        if (type(value) is not dict or set(value) != {"decision", "reason", "invariant_or_test", "limits"}
                or value["decision"] not in {"applied", "not_applicable", "deferred"}
                or any(not isinstance(x, str) or not x.strip() or len(x) > 1500 for x in value.values())):
            raise ValueError("explicit lens applicability, invariant/test and limits required")
    return {key: dict(checks[key]) for key in LENSES}


def mathematical_lenses_demo(arguments: dict[str, Any]) -> dict[str, Any]:
    if type(arguments) is not dict or arguments:
        raise ValueError("fixed mathematical lens demonstration accepts no arguments")
    return {"schema": "merlin-mathematical-lenses/1", "canonical_contract": CANONICAL_CONTRACT,
        "simplex": {"weights": simplex_weights((0.25, 0.5, 0.25)),
                    "blended_state": convex_blend(((0., 0.), (1., 0.), (0., 1.)), (0.25, 0.5, 0.25))},
        "n_ality": n_ality_signature(2, 2, 3, 1),
        "continuum": {"parameter": 0.25, "piecewise_linear_state": continuum_interpolate(((0., (0., 2.)), (1., (2., 0.))), 0.25)},
        "fuzzy_logic": {"memberships": (0.25, 0.75), "and_min": fuzzy_combine((0.25, 0.75), "and_min"),
                        "or_max": fuzzy_combine((0.25, 0.75), "or_max"), "semantics": "membership degrees, not probabilities"},
        "limits": ["reference computations, not proof or physical validation", "n-ality axes have independent meanings",
                   "continuum is the declared interpolant, not a PDE existence theorem", "fuzzy scores cannot override authorization, validation or qualification gates"],
        "qualification": False, "promotion_authority": False}
