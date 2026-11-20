"""Optional, offline OpenMDAO scalar-unit normalization for observation checks.

This profile uses the pinned upstream converter, not an optimizer or a second
comparison engine. Uncertainty is an interval half-width, not a probability.
Temperatures are absolute readings; offsets apply to their centers and only
the absolute scale applies to half-widths. Temperature intervals crossing
absolute zero are rejected. Delta-temperature quantities are outside scope.
Existing scientific_loop.compare_observation behavior is unchanged.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib
from importlib import metadata
import math
from pathlib import Path
import sys
from typing import Sequence

from .scientific_loop import Observation, Prediction, compare_observation


OPENMDAO_VERSION = "3.45.2"
UPSTREAM_COMMIT = "64175aa55fb541355b2fb279a6bcfde01e17a878"
UPSTREAM_REPOSITORY = "https://github.com/OpenMDAO/OpenMDAO"
PINNED_SOURCE_SHA256 = {
    "units.py": "9a812f46a371f9d10b5b17e9a21e5024b1c753ebfcee42d0e628eca4dcf3ba92",
    "unit_library.ini": "8094fb7d3e8cb65a56311c2ea5ccfbc9c29cb8b4160f1486c39c19dd779a43d3",
}
_CANONICAL_UNITS = {
    "m": "m", "cm": "m", "mm": "m", "km": "m", "ft": "m", "inch": "m",
    "s": "s", "min": "s", "h": "s", "kg": "kg", "g": "kg",
    "N": "N", "kN": "N", "Pa": "Pa", "kPa": "Pa", "W": "W", "kW": "W",
    "K": "K", "degC": "K", "degF": "K", "degR": "K",
    "m/s": "m/s", "km/h": "m/s",
}


class OpenMDAOUnavailable(RuntimeError):
    """The optional exact-version/source backend is unavailable or unreviewed."""


def _backend():
    if sys.version_info < (3, 10):
        raise OpenMDAOUnavailable("OpenMDAO profile requires Python 3.10 or newer")
    try:
        version = metadata.version("openmdao")
    except metadata.PackageNotFoundError:
        raise OpenMDAOUnavailable("optional openmdao==3.45.2 is not installed") from None
    if version != OPENMDAO_VERSION:
        raise OpenMDAOUnavailable("installed OpenMDAO version is outside this pinned profile")
    units = importlib.import_module("openmdao.utils.units")
    directory = Path(units.__file__).parent
    for name, expected in PINNED_SOURCE_SHA256.items():
        path = directory / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise OpenMDAOUnavailable("installed OpenMDAO unit source differs from reviewed pin")
    return units, {
        "package": "openmdao", "version": version,
        "upstream_commit": UPSTREAM_COMMIT,
        "source_sha256": dict(PINNED_SOURCE_SHA256),
        "source_url": UPSTREAM_REPOSITORY + "/blob/" + UPSTREAM_COMMIT + "/openmdao/utils/units.py",
        "license": "Apache-2.0",
    }


def backend_status() -> dict:
    """Inspect local installation only; absence never installs or falls back."""
    try:
        _, provenance = _backend()
    except OpenMDAOUnavailable as exc:
        return {"status": "blocked_optional_dependency", "reason": str(exc),
                "qualification": False, "promotion_authority": False}
    return {"status": "available", "backend": provenance,
            "qualification": False, "promotion_authority": False}


def _finite(value, name, *, nonnegative=False):
    valid = not isinstance(value, bool) and isinstance(value, (int, float))
    try:
        valid = valid and math.isfinite(value) and (not nonnegative or value >= 0)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(name + " must be finite" + (" and nonnegative" if nonnegative else ""))
    return float(value)


def compare_with_openmdao(observation: Observation,
                         predictions: Sequence[Prediction]) -> dict:
    """Normalize allowlisted scalar units, then invoke Merlin's comparator once.

    At most32 measurements and64 predictions are accepted. Incompatible
    dimensions retain Merlin's incomparable_unit result. Unknown/custom unit
    expressions are rejected before reaching OpenMDAO's expression parser.
    Invalid inputs/backend faults are not silently downgraded to predictions.
    """
    if not isinstance(observation, Observation):
        raise ValueError("a canonical Observation is required")
    if len(observation.measurements) > 32 or not 1 <= len(predictions) <= 64:
        raise ValueError("bounded measurements and predictions required")
    for metric, value in observation.measurements.items():
        _finite(value, "measurement")
        _finite(observation.uncertainty.get(metric), "measurement uncertainty", nonnegative=True)
    observation.validate()
    if (len(observation.source_refs) > 32
            or any(not isinstance(ref, str) or len(ref) > 2048 for ref in observation.source_refs)):
        raise ValueError("bounded source references required")
    for prediction in predictions:
        if not isinstance(prediction, Prediction):
            raise ValueError("canonical Prediction records required")
        _finite(prediction.expected, "prediction expectation")
        _finite(prediction.tolerance, "prediction tolerance", nonnegative=True)
    unit_names = [observation.units[metric] for metric in observation.measurements]
    unit_names.extend(prediction.unit for prediction in predictions)
    if any(not isinstance(unit, str) or unit not in _CANONICAL_UNITS for unit in unit_names):
        raise ValueError("unit is outside the bounded scalar conversion profile")
    units, provenance = _backend()
    conversions = {
        unit: units.unit_conversion(unit, _CANONICAL_UNITS[unit])
        for unit in sorted(set(unit_names))
    }

    def normalize(value, width, unit):
        target = _CANONICAL_UNITS[unit]
        factor, offset = conversions[unit]
        # OpenMDAO defines conversion as (value + offset) * factor.
        center = _finite((value + offset) * factor, "converted center")
        half_width = _finite(abs(factor) * width, "converted half-width", nonnegative=True)
        low = _finite(center - half_width, "converted lower interval")
        _finite(center + half_width, "converted upper interval")
        if target == "K" and low < 0:
            raise ValueError("absolute-temperature interval cannot extend below zero kelvin")
        return center, half_width, target

    values, widths, normalized_units = {}, {}, {}
    for metric, value in observation.measurements.items():
        values[metric], widths[metric], normalized_units[metric] = normalize(
            value, observation.uncertainty[metric], observation.units[metric])
    normalized_predictions = []
    for prediction in predictions:
        expected, tolerance, unit = normalize(
            prediction.expected, prediction.tolerance, prediction.unit)
        normalized_predictions.append(replace(
            prediction, expected=expected, tolerance=tolerance, unit=unit))
    normalized = replace(observation, measurements=values, units=normalized_units, uncertainty=widths)
    assessment = compare_observation(normalized, normalized_predictions)
    assessment["unit_normalization"] = {
        "schema": "merlin-openmdao-scalar-normalization/1", "backend": provenance,
        "original_observation_units": {
            metric: observation.units[metric] for metric in observation.measurements},
        "original_prediction_units": [prediction.unit for prediction in predictions],
        "uncertainty_rule": "interval half-width scales by absolute factor; never add affine offset",
        "temperature_scope": "absolute readings with nonnegative Kelvin intervals; no delta quantities",
        "source_refs": list(observation.source_refs),
        "original_artifact_sha256": observation.artifact_sha256,
        "comparison_engine": "merlin.scientific_loop.compare_observation",
        "qualification": False, "promotion_authority": False,
    }
    return assessment


def run_synthetic_demo() -> dict:
    """Return a public-known-fixture receipt; no remote/data/optimizer calls."""
    observation = Observation(
        observation_id="synthetic-openmdao-room-temperature", question="Equivalent thermometer scales?",
        method="declared synthetic fixture", measurements={"temperature": 68.0},
        units={"temperature": "degF"}, uncertainty={"temperature": 1.8},
        conditions={"fixture": "public_known_fixture", "quantity": "absolute temperature"},
        source_refs=("synthetic:openmdao-temperature-v1",), observed_at="2026-11-18T00:00:00Z",
    )
    predictions = (Prediction("temperature", 20.0, 1.1, "degC"),)
    return {
        "schema": "merlin-openmdao-demo/1", "fixture_class": "synthetic_public_known_fixture",
        "baseline": compare_observation(observation, predictions),
        "normalized": compare_with_openmdao(observation, predictions),
        "qualification": False, "promotion_authority": False,
        "limits": "Fixed scalar-unit contract; no empirical calibration, optimizer, model efficacy or NASA approval.",
    }


__all__ = ["OpenMDAOUnavailable", "backend_status", "compare_with_openmdao", "run_synthetic_demo"]
