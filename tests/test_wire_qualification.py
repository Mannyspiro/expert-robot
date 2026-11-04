import unittest

from merlin.wire_qualification import (
    ElectricalInputs, ManufacturingInputs, ThermalInputs,
    assess_electrical, assess_thermal, build_qualification_report,
)


def electrical():
    return ElectricalInputs(
        operating_voltage_v=24.0, load_current_a=2.0,
        circuit_loop_length_m=2.0,
        conductor_resistance_ohm_per_m_at_reference=0.02,
        conductor_reference_temperature_c=20.0,
        resistance_temperature_coefficient_per_c=0.00393,
        manufacturer_ampacity_a=5.0, ampacity_derating_factor=0.8,
        maximum_voltage_drop_v=1.2, insulation_voltage_rating_v=60.0,
        minimum_required_clearance_mm=2.0, measured_minimum_clearance_mm=3.0,
    )


def route():
    return {
        "format": "merlin-wire-route-proposals-v0.1",
        "status": "GEOMETRY_PROPOSAL_ONLY_NOT_ELECTRICAL_OR_MANUFACTURING_APPROVAL",
        "nets": [{"routes": [{
            "status": "candidate_geometry_not_manufacturing_qualified",
            "polyline_mm": [[0, 0, 0], [10, 0, 0]],
            "length_mm": 10.0,
        }]}],
    }


class WireQualificationTests(unittest.TestCase):
    def test_ampacity_and_voltage_drop_are_explicit_calculations(self):
        findings = assess_electrical(electrical())
        by_code = {item["code"]: item for item in findings}
        self.assertEqual(by_code["CONDUCTOR_AMPACITY"]["status"], "PASS")
        self.assertAlmostEqual(by_code["DC_VOLTAGE_DROP_ESTIMATE"]["estimated_voltage_drop_v"], 0.08)
        self.assertEqual(by_code["INSULATION_VOLTAGE_RATING"]["status"], "PASS")

    def test_overloaded_conductor_fails(self):
        x = electrical()
        from dataclasses import replace
        result = assess_electrical(replace(x, load_current_a=5.0))
        self.assertEqual(next(i for i in result if i["code"] == "CONDUCTOR_AMPACITY")["status"], "FAIL")

    def test_clearance_comparison_does_not_infer_standard(self):
        from dataclasses import replace
        result = assess_electrical(replace(electrical(), measured_minimum_clearance_mm=1.0))
        item = next(i for i in result if i["code"] == "CLEARANCE_INPUT_COMPARISON")
        self.assertEqual(item["status"], "FAIL")
        self.assertIn("does not calculate", item["message"])

    def test_thermal_lumped_model_converges_and_limits(self):
        thermal = ThermalInputs(25.0, 90.0, 4.0, "thermal-test-001")
        result = assess_thermal(electrical(), thermal)[0]
        self.assertEqual(result["status"], "PASS")
        self.assertLess(result["estimated_conductor_temperature_c"], 90.0)

    def test_missing_thermal_correlation_blocks(self):
        thermal = ThermalInputs(25.0, 90.0, 4.0, "")
        self.assertEqual(assess_thermal(electrical(), thermal)[0]["status"], "BLOCKED")

    def test_manufacturing_gate_requires_swept_bend_geometry(self):
        from merlin.wire_qualification import assess_manufacturing
        x = ManufacturingInputs(10.0, (), 5.0, 8.0, "DWG-REV-A", "process-plan-001")
        result = assess_manufacturing(route()["nets"][0]["routes"][0], x)
        self.assertEqual(result[0]["code"], "BEND_GEOMETRY_UNVERIFIED")
        self.assertEqual(result[0]["status"], "BLOCKED")

    def test_missing_authoritative_data_blocks_release(self):
        report = build_qualification_report(route(), None, None, None)
        self.assertEqual(report["overall_status"], "BLOCKED")
        self.assertFalse(report["qualified_for_energized_use"])
        self.assertFalse(report["qualified_for_manufacture"])
        self.assertFalse(report["promotion_authorized"])
        self.assertGreaterEqual(len(report["required_evidence"]), 10)

    def test_complete_screening_still_does_not_self_certify(self):
        from merlin.wire_qualification import assess_manufacturing
        manufacturing = ManufacturingInputs(10.0, (12.0, 14.0), 5.0, 8.0,
                                             "DWG-REV-A", "process-plan-001")
        result = assess_manufacturing(route()["nets"][0]["routes"][0], manufacturing)
        self.assertEqual(result[0]["status"], "PASS")
        report = build_qualification_report(
            route(), electrical(), ThermalInputs(25.0, 90.0, 4.0, "thermal-test-001"),
            manufacturing,
        )
        self.assertNotEqual(report["overall_status"], "EVIDENCE_COMPLETE_PENDING_AUTHORITY")
        self.assertFalse(report["qualified_for_manufacture"])


if __name__ == "__main__":
    unittest.main()
