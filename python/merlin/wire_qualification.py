"""Evidence-gated electrical, thermal and manufacturing assessment.

The calculations are transparent engineering estimates, not certification.
Missing authoritative inputs produce UNKNOWN/BLOCKED outcomes, never defaults.
The module deliberately does not infer conductor ampacity, insulation ratings,
clearance rules, bend radii, or standard applicability from wire gauge or voltage.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Any


@dataclass(frozen=True)
class ElectricalInputs:
    operating_voltage_v: float
    load_current_a: float
    circuit_loop_length_m: float
    conductor_resistance_ohm_per_m_at_reference: float
    conductor_reference_temperature_c: float
    resistance_temperature_coefficient_per_c: float
    manufacturer_ampacity_a: float
    ampacity_derating_factor: float
    maximum_voltage_drop_v: float
    insulation_voltage_rating_v: float
    minimum_required_clearance_mm: float
    measured_minimum_clearance_mm: float


@dataclass(frozen=True)
class ThermalInputs:
    ambient_temperature_c: float
    maximum_conductor_temperature_c: float
    lumped_thermal_resistance_k_per_w: float
    model_correlation_evidence_id: str


@dataclass(frozen=True)
class ManufacturingInputs:
    manufacturer_minimum_bend_radius_mm: float
    achieved_bend_radii_mm: tuple[float, ...]
    route_length_tolerance_mm: float
    available_length_slack_mm: float
    drawing_revision: str
    harness_process_evidence_id: str


_REQUIRED_EVIDENCE = (
    "component_datasheets",
    "wire_and_insulation_datasheet",
    "applicable_standard_and_product_class_review",
    "schematic_electrical_rules_check",
    "pcb_design_rules_check_or_not_applicable_justification",
    "insulation_coordination_and_clearance_review",
    "overcurrent_and_short_circuit_coordination",
    "protective_bonding_and_grounding_review",
    "thermal_model_correlation_or_test",
    "mechanical_tolerance_and_collision_review",
    "harness_workmanship_and_process_plan",
    "continuity_and_pinout_test",
    "insulation_resistance_and_dielectric_test",
    "independent_engineering_signoff",
)


def _finite_positive(value: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _finding(code: str, status: str, message: str, **metrics: Any) -> dict[str, Any]:
    return {"code": code, "status": status, "message": message, **metrics}


def _thermal_fixed_point(
    current_a: float,
    loop_length_m: float,
    resistance_ohm_per_m: float,
    reference_temp_c: float,
    alpha_per_c: float,
    ambient_c: float,
    thermal_resistance_k_per_w: float,
) -> tuple[float, float] | None:
    """Solve the stated lumped steady-state model by bounded fixed-point iteration."""
    temp = ambient_c
    for _ in range(500):
        resistance = resistance_ohm_per_m * (1.0 + alpha_per_c * (temp - reference_temp_c))
        if not math.isfinite(resistance) or resistance <= 0:
            return None
        power = current_a * current_a * loop_length_m * resistance
        next_temp = ambient_c + power * thermal_resistance_k_per_w
        if not math.isfinite(next_temp) or next_temp > 10000:
            return None
        if abs(next_temp - temp) < 1e-8:
            return next_temp, resistance
        temp = next_temp
    return None


def assess_electrical(inputs: ElectricalInputs) -> list[dict[str, Any]]:
    x = asdict(inputs)
    findings = []
    positive = (
        "operating_voltage_v", "load_current_a", "circuit_loop_length_m",
        "conductor_resistance_ohm_per_m_at_reference", "manufacturer_ampacity_a",
        "maximum_voltage_drop_v", "insulation_voltage_rating_v",
    )
    for key in positive:
        if not _finite_positive(x[key]):
            findings.append(_finding("ELECTRICAL_INPUT_INVALID", "BLOCKED",
                                     f"{key} must be a finite positive value."))
    for key in ("conductor_reference_temperature_c", "resistance_temperature_coefficient_per_c",
                "minimum_required_clearance_mm", "measured_minimum_clearance_mm"):
        if not math.isfinite(x[key]):
            findings.append(_finding("ELECTRICAL_INPUT_INVALID", "BLOCKED",
                                     f"{key} must be finite."))
    if not math.isfinite(inputs.ampacity_derating_factor) or not 0 < inputs.ampacity_derating_factor <= 1:
        findings.append(_finding("AMPACITY_DERATING_INVALID", "BLOCKED",
                                 "Derating factor must be in (0, 1] and sourced from applicable data."))
    if findings:
        return findings

    derated_ampacity = inputs.manufacturer_ampacity_a * inputs.ampacity_derating_factor
    findings.append(_finding(
        "CONDUCTOR_AMPACITY", "PASS" if inputs.load_current_a <= derated_ampacity else "FAIL",
        "Load current compared with manufacturer ampacity after supplied derating.",
        load_current_a=inputs.load_current_a, derated_ampacity_a=derated_ampacity,
    ))
    resistance = inputs.conductor_resistance_ohm_per_m_at_reference
    voltage_drop = inputs.load_current_a * resistance * inputs.circuit_loop_length_m
    findings.append(_finding(
        "DC_VOLTAGE_DROP_ESTIMATE",
        "PASS" if voltage_drop <= inputs.maximum_voltage_drop_v else "FAIL",
        "Resistive DC estimate using the supplied complete circuit-loop length; excludes contacts and dynamic effects.",
        estimated_voltage_drop_v=voltage_drop,
        maximum_voltage_drop_v=inputs.maximum_voltage_drop_v,
    ))
    findings.append(_finding(
        "INSULATION_VOLTAGE_RATING",
        "PASS" if inputs.operating_voltage_v <= inputs.insulation_voltage_rating_v else "FAIL",
        "Operating voltage compared with the supplied manufacturer insulation rating only.",
        operating_voltage_v=inputs.operating_voltage_v,
        insulation_voltage_rating_v=inputs.insulation_voltage_rating_v,
    ))
    findings.append(_finding(
        "CLEARANCE_INPUT_COMPARISON",
        "PASS" if inputs.measured_minimum_clearance_mm >= inputs.minimum_required_clearance_mm else "FAIL",
        "Compares a supplied measured clearance with a separately reviewed requirement; does not calculate a standards-based clearance.",
        measured_minimum_clearance_mm=inputs.measured_minimum_clearance_mm,
        reviewed_required_clearance_mm=inputs.minimum_required_clearance_mm,
    ))
    return findings


def assess_thermal(electrical: ElectricalInputs, thermal: ThermalInputs) -> list[dict[str, Any]]:
    if not thermal.model_correlation_evidence_id.strip():
        return [_finding("THERMAL_MODEL_UNCORRELATED", "BLOCKED",
                         "Thermal model needs a traceable correlation/test evidence identifier.")]
    values = (
        thermal.ambient_temperature_c, thermal.maximum_conductor_temperature_c,
        thermal.lumped_thermal_resistance_k_per_w,
        electrical.load_current_a, electrical.circuit_loop_length_m,
        electrical.conductor_resistance_ohm_per_m_at_reference,
        electrical.conductor_reference_temperature_c,
        electrical.resistance_temperature_coefficient_per_c,
    )
    if any(not math.isfinite(v) for v in values) or thermal.lumped_thermal_resistance_k_per_w <= 0:
        return [_finding("THERMAL_INPUT_INVALID", "BLOCKED",
                         "Thermal inputs must be finite and thermal resistance positive.")]
    result = _thermal_fixed_point(
        electrical.load_current_a, electrical.circuit_loop_length_m,
        electrical.conductor_resistance_ohm_per_m_at_reference,
        electrical.conductor_reference_temperature_c,
        electrical.resistance_temperature_coefficient_per_c,
        thermal.ambient_temperature_c, thermal.lumped_thermal_resistance_k_per_w,
    )
    if result is None:
        return [_finding("THERMAL_MODEL_DID_NOT_CONVERGE", "BLOCKED",
                         "Lumped steady-state model did not converge to a finite positive resistance.")]
    estimated_temp, resistance = result
    return [_finding(
        "LUMPED_STEADY_STATE_CONDUCTOR_TEMPERATURE",
        "PASS" if estimated_temp <= thermal.maximum_conductor_temperature_c else "FAIL",
        "First-order lumped estimate only; requires validated boundary conditions and correlation to representative test data.",
        estimated_conductor_temperature_c=estimated_temp,
        maximum_conductor_temperature_c=thermal.maximum_conductor_temperature_c,
        resistance_at_estimated_temperature_ohm_per_m=resistance,
        thermal_model_evidence_id=thermal.model_correlation_evidence_id,
    )]


def assess_manufacturing(route: dict[str, Any], inputs: ManufacturingInputs) -> list[dict[str, Any]]:
    if route.get("status") != "candidate_geometry_not_manufacturing_qualified":
        return [_finding("ROUTE_NOT_CANDIDATE", "BLOCKED",
                         "Manufacturing assessment requires a candidate route geometry.")]
    if not inputs.harness_process_evidence_id.strip() or not inputs.drawing_revision.strip():
        return [_finding("MANUFACTURING_TRACEABILITY_MISSING", "BLOCKED",
                         "A controlled drawing revision and harness process evidence are required.")]
    if not _finite_positive(inputs.manufacturer_minimum_bend_radius_mm):
        return [_finding("BEND_RADIUS_INPUT_INVALID", "BLOCKED",
                         "Manufacturer minimum bend radius must be a sourced positive value.")]
    if not math.isfinite(inputs.route_length_tolerance_mm) or inputs.route_length_tolerance_mm < 0:
        return [_finding("LENGTH_TOLERANCE_INVALID", "BLOCKED",
                         "Route length tolerance must be finite and nonnegative.")]
    if not math.isfinite(inputs.available_length_slack_mm) or inputs.available_length_slack_mm < 0:
        return [_finding("LENGTH_SLACK_INVALID", "BLOCKED",
                         "Available length slack must be finite and nonnegative.")]
    if not inputs.achieved_bend_radii_mm:
        return [_finding("BEND_GEOMETRY_UNVERIFIED", "BLOCKED",
                         "No achieved bend radii were supplied from swept cable geometry.")]
    if any(not _finite_positive(r) for r in inputs.achieved_bend_radii_mm):
        return [_finding("BEND_GEOMETRY_INVALID", "BLOCKED",
                         "All achieved bend radii must be finite and positive.")]
    minimum = min(inputs.achieved_bend_radii_mm)
    return [
        _finding(
            "BEND_RADIUS",
            "PASS" if minimum >= inputs.manufacturer_minimum_bend_radius_mm else "FAIL",
            "Compares swept-geometry bend radii against the manufacturer's stated minimum.",
            minimum_achieved_bend_radius_mm=minimum,
            manufacturer_minimum_bend_radius_mm=inputs.manufacturer_minimum_bend_radius_mm,
        ),
        _finding(
            "HARNESS_LENGTH_SLACK",
            "PASS" if inputs.available_length_slack_mm >= inputs.route_length_tolerance_mm else "FAIL",
            "Compares supplied installation slack with the declared route-length tolerance.",
            available_length_slack_mm=inputs.available_length_slack_mm,
            route_length_tolerance_mm=inputs.route_length_tolerance_mm,
        ),
        _finding("DRAWING_AND_PROCESS_TRACEABILITY", "REVIEW_REQUIRED",
                 "Traceability is present but workmanship, tooling, inspection and process acceptance require independent review.",
                 drawing_revision=inputs.drawing_revision,
                 harness_process_evidence_id=inputs.harness_process_evidence_id),
    ]


def build_qualification_report(
    route: dict[str, Any],
    electrical: ElectricalInputs | None,
    thermal: ThermalInputs | None,
    manufacturing: ManufacturingInputs | None,
    evidence: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Combine independent gate results. Never returns a certified/safe status."""
    findings: list[dict[str, Any]] = []
    if electrical is None:
        findings.append(_finding("ELECTRICAL_INPUTS_MISSING", "BLOCKED",
                                 "No authoritative conductor, circuit, insulation and clearance inputs supplied."))
    else:
        findings.extend(assess_electrical(electrical))
    if thermal is None or electrical is None:
        findings.append(_finding("THERMAL_INPUTS_MISSING", "BLOCKED",
                                 "Thermal model inputs and correlated evidence are required."))
    else:
        findings.extend(assess_thermal(electrical, thermal))
    if manufacturing is None:
        findings.append(_finding("MANUFACTURING_INPUTS_MISSING", "BLOCKED",
                                 "Swept bend geometry, tolerance and controlled manufacturing inputs are required."))
    else:
        for net in route.get("nets", []):
            for candidate in net.get("routes", []):
                findings.extend(assess_manufacturing(candidate, manufacturing))
    supplied = evidence or {}
    evidence_status = {}
    for requirement in _REQUIRED_EVIDENCE:
        item = supplied.get(requirement, {})
        verified = (
            item.get("status") == "verified"
            and bool(item.get("artifact_sha256"))
            and len(item.get("artifact_sha256", "")) == 64
            and bool(item.get("reviewer"))
        )
        evidence_status[requirement] = "verified" if verified else "missing_or_unverified"
        if not verified:
            findings.append(_finding("REQUIRED_EVIDENCE_" + requirement.upper(),
                                     "BLOCKED",
                                     f"Required independent evidence is missing or unverified: {requirement}."))
    states = {item["status"] for item in findings}
    overall = "BLOCKED" if "BLOCKED" in states else (
        "FAIL" if "FAIL" in states else (
            "REVIEW_REQUIRED" if "REVIEW_REQUIRED" in states else "EVIDENCE_COMPLETE_PENDING_AUTHORITY"
        )
    )
    report = {
        "schema": "merlin-wire-qualification-report/0.1",
        "route_format": route.get("format"),
        "route_status": route.get("status"),
        "overall_status": overall,
        "qualified_for_energized_use": False,
        "qualified_for_manufacture": False,
        "promotion_authorized": False,
        "findings": findings,
        "required_evidence": evidence_status,
        "limitations": [
            "This report is an engineering screening and evidence-gap tool, not a certification or declaration of safety.",
            "Ampacity, insulation rating, required clearance and bend-radius limits must come from applicable authoritative manufacturer data and standards.",
            "The lumped thermal model is not a substitute for validated finite-element, CFD, or representative physical testing where required.",
            "No short-circuit coordination, arc-flash, dielectric withstand, creepage derivation, EMC, vibration, flammability, or regulatory conformity is established by this report.",
            "A route polyline is not a swept cable solid; bend-radius and collision evidence must come from the CAD harness model.",
        ],
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False)
    report["report_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return report
