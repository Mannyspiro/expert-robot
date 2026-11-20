"""Known physical conversion oracles against the actual optional OpenMDAO package."""
from __future__ import annotations

from importlib import metadata
import math
import unittest
from unittest.mock import patch

from merlin import openmdao_measurement as adapter
from merlin.scientific_loop import Observation, Prediction, compare_observation


def observation(value=100.0, width=2.0, unit="cm"):
    return Observation("synthetic-units", "Equivalent physical intervals?", "synthetic fixed fixture",
        {"x": value}, {"x": unit}, {"x": width}, {"fixture": "public_known_fixture"},
        ("synthetic:unit-oracle-v1",), "2026-11-18T00:00:00Z")


class OptionalBackendTests(unittest.TestCase):
    def test_missing_package_is_explicit_without_affecting_existing_comparator(self):
        with patch.object(adapter.metadata, "version", side_effect=metadata.PackageNotFoundError):
            self.assertEqual(adapter.backend_status()["status"], "blocked_optional_dependency")
            with self.assertRaises(adapter.OpenMDAOUnavailable):
                adapter.compare_with_openmdao(observation(), (Prediction("x", 1.0, .03, "m"),))
        baseline = compare_observation(observation(), (Prediction("x", 1.0, .03, "m"),))
        self.assertEqual(baseline["comparisons"][0]["result"], "incomparable_unit")

    def test_wrong_version_is_not_accepted(self):
        with patch.object(adapter.metadata, "version", return_value="0.0.0"):
            self.assertEqual(adapter.backend_status()["status"], "blocked_optional_dependency")


@unittest.skipUnless(adapter.backend_status()["status"] == "available", "pinned OpenMDAO optional profile absent")
class ActualOpenMDAOTests(unittest.TestCase):
    def compare(self, value, width, unit, expected, tolerance, prediction_unit):
        return adapter.compare_with_openmdao(observation(value, width, unit),
            (Prediction("x", expected, tolerance, prediction_unit),))

    def test_equivalent_length_and_interval_scale(self):
        result = self.compare(100, 2, "cm", 1, .03, "m")
        self.assertEqual(result["overall"], "consistent_with_prediction")
        self.assertEqual(result["comparisons"][0]["measured_interval"], [.98, 1.02])
        self.assertEqual(result["comparisons"][0]["unit"], "m")

    def test_affine_fahrenheit_and_celsius_uncertainty_has_no_offset(self):
        result = self.compare(68, 1.8, "degF", 20, 1.1, "degC")
        interval = result["comparisons"][0]["measured_interval"]
        self.assertAlmostEqual(interval[0], 292.15, places=10)
        self.assertAlmostEqual(interval[1], 294.15, places=10)
        self.assertEqual(result["overall"], "consistent_with_prediction")

    def test_zero_celsius_is_273_point_15_kelvin(self):
        result = self.compare(0, .1, "degC", 273.15, .2, "K")
        self.assertEqual(result["overall"], "consistent_with_prediction")

    def test_incompatible_dimensions_remain_incomparable(self):
        result = self.compare(100, 2, "cm", 1, .03, "s")
        self.assertEqual(result["overall"], "inconclusive")
        self.assertEqual(result["comparisons"][0]["result"], "incomparable_unit")

    def test_contradiction_and_overlap_reuse_existing_interval_rules(self):
        self.assertEqual(self.compare(200, 1, "cm", 1, .03, "m")["overall"], "contradicted")
        self.assertEqual(self.compare(100, 10, "cm", 1, .03, "m")["overall"], "inconclusive")

    def test_finite_values_widths_and_overflow_are_rejected(self):
        for value, width in ((math.nan, 1), (math.inf, 1), (True, 1), (1, -1), (1, math.inf)):
            with self.subTest(value=value, width=width), self.assertRaises(ValueError):
                self.compare(value, width, "m", 1, .1, "m")
        with self.assertRaises(ValueError):
            self.compare(1e308, 1, "km", 1, .1, "m")
        with self.assertRaises(ValueError):
            self.compare(10 ** 10000, 1, "m", 1, .1, "m")
        with self.assertRaises(ValueError):
            self.compare(1, .1, "m", math.nan, .1, "s")

    def test_below_absolute_zero_and_crossing_intervals_are_rejected(self):
        for value, width, unit in ((-300, 0, "degC"), (0, 1, "K"), (-459.67, 1, "degF")):
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                self.compare(value, width, unit, 273, 1, "K")
        with self.assertRaises(ValueError):
            self.compare(273, 1, "K", -300, 0, "degC")

    def test_unknown_unit_expressions_and_oversized_batches_are_rejected(self):
        for unit in ("unknown", "m**(10**10)", "__import__('os')", "delta_degC", ["m"]):
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                self.compare(1, .1, unit, 1, .1, "m")
        with self.assertRaises(ValueError):
            adapter.compare_with_openmdao(observation(), (Prediction("x", 1, .1, "m"),) * 65)

    def test_source_integrity_and_canonical_engine_identity(self):
        result = self.compare(100, 2, "cm", 1, .03, "m")
        provenance = result["unit_normalization"]
        self.assertEqual(provenance["backend"]["version"], "3.45.2")
        self.assertEqual(provenance["backend"]["source_sha256"], adapter.PINNED_SOURCE_SHA256)
        self.assertFalse(provenance["qualification"])
        with patch.dict(adapter.PINNED_SOURCE_SHA256, {"units.py": "0" * 64}):
            self.assertEqual(adapter.backend_status()["status"], "blocked_optional_dependency")

    def test_unobserved_metric_and_single_existing_comparator_call(self):
        with patch.object(adapter, "compare_observation", wraps=compare_observation) as compare:
            result = adapter.compare_with_openmdao(observation(),
                (Prediction("x", 1, .03, "m"), Prediction("y", 1, .1, "s")))
        self.assertEqual(compare.call_count, 1)
        self.assertEqual(result["comparisons"][1]["result"], "unobserved")

    def test_demo_exposes_useful_baseline_disagreement_without_promotion(self):
        report = adapter.run_synthetic_demo()
        self.assertEqual(report["baseline"]["overall"], "inconclusive")
        self.assertEqual(report["normalized"]["overall"], "consistent_with_prediction")
        self.assertFalse(report["promotion_authority"])


if __name__ == "__main__":
    unittest.main()
