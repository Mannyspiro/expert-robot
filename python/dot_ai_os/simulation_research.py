"""Bounded offline virtual DC experiments using Merlin's canonical Engineering IR.

Exact rational arithmetic describes this ideal model only. Results are simulated
observations, never physical safety certification, independent CACE evidence or
formal proof. No subprocess, network, hardware, signer or promotion is invoked.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import importlib
import math
from pathlib import Path
import platform
import re
from typing import Any

from merlin.engineering_ir import (
    EngineeringProject, Net, Part, Pin, export_netlist, export_openscad,
    export_spice_netlist, validate_project,
)
from merlin.project_registry import MerlinRegistry
from .bridge import canonical, digest

VERSION = "dot-virtual-dc/1"
MAX_PARTS = 24
MAX_NETS = 14
LIMITATIONS = (
    "Ideal linear DC model: constant resistors, one ideal ground-referenced voltage source.",
    "No device tolerances, temperature drift, source impedance, parasitics, dynamics or physical measurements.",
    "CAD output is the canonical box-assembly preview; wiring/SPICE exports are research artifacts.",
    "Model ratings are metadata checks only; no physical safety, fabrication or energization authorization.",
    "No independent CACE verification, formal proof, automatic adoption, capability promotion or deployment.",
)


@dataclass(frozen=True)
class CircuitCandidate:
    candidate_id: str
    component_specs: dict[str, dict[str, str]]


@dataclass(frozen=True)
class CircuitObjective:
    ground_net: str
    measured_net: str
    target_voltage_v: str
    tolerance_v: str
    maximum_total_power_w: str


def _name(value: Any, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value) is None:
        raise ValueError(f"{label} must be a bounded ASCII identifier")
    return value


def _decimal(value: Any, label: str, minimum: Fraction, maximum: Fraction) -> Fraction:
    # Restrict size before Fraction parsing; no expressions, SPICE suffix ambiguity
    # or adversarially large integer/exponent operations enter the solver.
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{1,7}(?:\.[0-9]{1,6})?", value) is None:
        raise ValueError(f"{label} needs a bounded nonnegative decimal SI value")
    number = Fraction(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} is outside the virtual experiment range")
    return number


def _numeric(value: Any, label: str) -> None:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite real number")


def _project(project: EngineeringProject) -> dict[str, str]:
    if not isinstance(project, EngineeringProject):
        raise ValueError("canonical EngineeringProject is required")
    if not 2 <= len(project.parts) <= MAX_PARTS or not 2 <= len(project.nets) <= MAX_NETS:
        raise ValueError("virtual experiment needs 2..24 parts and 2..14 nets")
    if (not isinstance(project.name, str) or not 1 <= len(project.name) <= 150
            or any(ord(c) < 32 or ord(c) == 127 for c in project.name)):
        raise ValueError("project name must be bounded single-line text")
    if not isinstance(project.metadata, dict) or len(project.metadata) > 20 or any(
            not isinstance(k, str) or not isinstance(v, str) or len(k) > 100 or len(v) > 1000
            for k, v in project.metadata.items()):
        raise ValueError("project metadata must be bounded text")
    for part in project.parts:
        if not isinstance(part, Part) or len(part.pins) != 2:
            raise ValueError("every simulated canonical Part requires exactly two pins")
        _name(part.ref, "part reference")
        if not isinstance(part.name, str) or not 1 <= len(part.name) <= 150 or any(
                ord(c) < 32 or ord(c) == 127 for c in part.name):
            raise ValueError("part name must be bounded single-line text")
        for label, values in (("size_mm", part.size_mm), ("position_mm", part.position_mm)):
            if not isinstance(values, tuple) or len(values) != 3:
                raise ValueError("part geometry must be a three-tuple")
            for value in values:
                _numeric(value, label)
        for pin in part.pins:
            if not isinstance(pin, Pin) or not isinstance(pin.number, str) or re.fullmatch(r"[0-9]{1,3}", pin.number) is None:
                raise ValueError("canonical pin numbers must be bounded numeric identifiers")
            if not isinstance(pin.name, str) or not 1 <= len(pin.name) <= 150 or any(
                    ord(c) < 32 or ord(c) == 127 for c in pin.name):
                raise ValueError("pin name must be bounded single-line text")
            for rating in (pin.max_voltage_v, pin.max_current_a):
                if rating is not None:
                    _numeric(rating, "pin rating")
            for geometry in (pin.position_mm, pin.direction):
                if geometry is not None:
                    if not isinstance(geometry, tuple) or len(geometry) != 3:
                        raise ValueError("pin geometry must be a three-tuple")
                    for value in geometry:
                        _numeric(value, "pin geometry")
    endpoint_to_net = {}
    for net in project.nets:
        if not isinstance(net, Net):
            raise ValueError("canonical Net records required")
        _name(net.name, "net name")
        if not isinstance(net.endpoints, tuple) or not 1 <= len(net.endpoints) <= 2 * MAX_PARTS:
            raise ValueError("bounded explicit endpoint tuples required")
        for value in (net.nominal_voltage_v, net.max_current_a):
            if value is not None:
                _numeric(value, "net rating")
        for endpoint in net.endpoints:
            if not isinstance(endpoint, str):
                raise ValueError("net endpoint must be text")
            endpoint_to_net[endpoint] = net.name
    issues = validate_project(project)
    if any(issue.severity == "error" for issue in issues):
        raise ValueError("canonical Engineering IR validation failed: " +
                         ",".join(sorted({issue.code for issue in issues if issue.severity == "error"})))
    return endpoint_to_net


def _solve(matrix: list[list[Fraction]], right: list[Fraction]) -> list[Fraction]:
    count = len(right)
    rows = [list(row) + [value] for row, value in zip(matrix, right)]
    # Preserve exact arithmetic, but eliminate only below each pivot. Updating
    # already-eliminated columns or zero-multiplier rows adds Fraction work only.
    for column in range(count):
        pivot = next((i for i in range(column, count) if rows[i][column]), None)
        if pivot is None:
            raise ValueError("floating or unconstrained resistor-network component")
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        for i in range(column + 1, count):
            multiplier = rows[i][column]
            if not multiplier:
                continue
            multiplier /= divisor
            rows[i][column] = Fraction(0)
            for j in range(column + 1, count + 1):
                rows[i][j] -= multiplier * rows[column][j]
    solution = [Fraction(0) for _ in range(count)]
    for i in range(count - 1, -1, -1):
        value = rows[i][-1]
        for j in range(i + 1, count):
            if rows[i][j]:
                value -= rows[i][j] * solution[j]
        solution[i] = value / rows[i][i]
    return solution


def _simulate(project: EngineeringProject, candidate: CircuitCandidate,
              objective: CircuitObjective, endpoints: dict[str, str]) -> dict[str, Any]:
    _name(candidate.candidate_id, "candidate ID")
    specs = candidate.component_specs
    if not isinstance(specs, dict) or set(specs) != {part.ref for part in project.parts}:
        raise ValueError("explicit component specs must cover every project part exactly")
    nodes = {net.name for net in project.nets}
    if objective.ground_net not in nodes or objective.measured_net not in nodes:
        raise ValueError("objective references unknown ground or measured net")
    components = []
    for part in sorted(project.parts, key=lambda p: p.ref):
        spec = specs[part.ref]
        if (not isinstance(spec, dict) or set(spec) != {"kind", "value"}
                or not isinstance(spec["kind"], str) or spec["kind"] not in {"R", "V"}):
            raise ValueError("only explicitly typed R and V component specs are supported")
        kind = spec["kind"]
        value = _decimal(spec["value"], part.ref, Fraction(100) if kind == "R" else Fraction(0),
                         Fraction(1000000) if kind == "R" else Fraction(12))
        terminals = [f"{part.ref}.{pin.number}" for pin in part.pins]
        if any(terminal not in endpoints for terminal in terminals):
            raise ValueError("every simulated pin must be connected")
        a, b = [endpoints[terminal] for terminal in terminals]
        if a == b:
            raise ValueError("two-terminal component is shorted onto one net")
        components.append((part.ref, kind, value, a, b))
    sources = [component for component in components if component[1] == "V"]
    if len(sources) != 1 or sources[0][4] != objective.ground_net:
        raise ValueError("exactly one ideal source with second terminal on declared ground required")
    source = sources[0]
    resistors = [component for component in components if component[1] == "R"]
    fixed = {objective.ground_net: Fraction(0), source[3]: source[2]}
    unknown = sorted(nodes - set(fixed))
    indices = {node: i for i, node in enumerate(unknown)}
    matrix = [[Fraction(0) for _ in unknown] for _ in unknown]
    right = [Fraction(0) for _ in unknown]
    for _ref, _kind, resistance, a, b in resistors:
        conductance = 1 / resistance
        for node, other in ((a, b), (b, a)):
            if node not in indices:
                continue
            row = indices[node]
            matrix[row][row] += conductance
            if other in indices:
                matrix[row][indices[other]] -= conductance
            else:
                right[row] += conductance * fixed[other]
    voltages = {**fixed, **dict(zip(unknown, _solve(matrix, right)))}
    currents = {}
    powers = {}
    residuals = {node: Fraction(0) for node in nodes}
    for ref, _kind, resistance, a, b in resistors:
        current = (voltages[a] - voltages[b]) / resistance
        currents[ref] = current
        powers[ref] = current * current * resistance
        residuals[a] += current
        residuals[b] -= current
    currents[source[0]] = -residuals[source[3]]
    residuals[source[3]] += currents[source[0]]
    residuals[objective.ground_net] -= currents[source[0]]
    total_power = sum(powers.values(), Fraction(0))
    power_residual = total_power + source[2] * currents[source[0]]
    if any(residuals.values()) or power_residual:
        raise RuntimeError("internal KCL/power residual mismatch")
    rating_flags = []
    for part in sorted(project.parts, key=lambda p: p.ref):
        for pin in part.pins:
            voltage = voltages[endpoints[f"{part.ref}.{pin.number}"]]
            exceeded = []
            if pin.max_voltage_v is not None and abs(voltage) > Fraction(str(pin.max_voltage_v)):
                exceeded.append("pin_voltage_rating")
            if pin.max_current_a is not None and abs(currents[part.ref]) > Fraction(str(pin.max_current_a)):
                exceeded.append("pin_current_rating")
            if exceeded:
                rating_flags.append({"endpoint": f"{part.ref}.{pin.number}", "exceeded": exceeded})
    netlist = export_spice_netlist(project, specs, ground_net=objective.ground_net,
                                  measure_nets=(objective.measured_net,))
    return {"candidate_id": candidate.candidate_id,
            "node_voltage_v": {node: str(voltages[node]) for node in sorted(voltages)},
            "branch_current_a_declared_pin_order": {ref: str(currents[ref]) for ref in sorted(currents)},
            "terminal_order_by_part": {part.ref: [pin.number for pin in part.pins]
                                       for part in sorted(project.parts, key=lambda p: p.ref)},
            "resistor_power_w": {ref: str(powers[ref]) for ref in sorted(powers)},
            "total_resistor_power_w": str(total_power),
            "maximum_kcl_residual_a": str(max(abs(x) for x in residuals.values())),
            "power_balance_residual_w": str(power_residual),
            "modeled_rating_flags": rating_flags,
            "spice_netlist": netlist, "spice_netlist_sha256": digest(netlist.encode()),
            "status": "simulated", "qualification": False, "promotion_authority": False}


def compare_virtual_circuits(project: EngineeringProject, baseline: CircuitCandidate,
                             candidates: tuple[CircuitCandidate, ...], objective: CircuitObjective,
                             *, source_commit: str, registry: MerlinRegistry | None = None,
                             project_id: str = "dot-ai-os") -> dict[str, Any]:
    """Compare bounded candidates against one preregistered ideal-model objective.

    Candidates preserve topology, source value and component kinds. Ranking first
    prefers candidates satisfying voltage/power/metadata checks, then smaller
    voltage error, then lower ideal-model dissipation. Selection requests review;
    it never installs a change or changes canonical evidence/qualification state.
    """
    if not isinstance(source_commit, str) or re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ValueError("full declared source commit required")
    if not isinstance(objective, CircuitObjective):
        raise ValueError("typed CircuitObjective required")
    _name(objective.ground_net, "ground net")
    _name(objective.measured_net, "measured net")
    if not isinstance(baseline, CircuitCandidate) or not isinstance(candidates, tuple) or not 1 <= len(candidates) <= 4:
        raise ValueError("typed baseline and 1..4 candidate tuple required")
    all_candidates = (baseline,) + candidates
    if any(not isinstance(candidate, CircuitCandidate) for candidate in all_candidates):
        raise ValueError("typed CircuitCandidate records required")
    ids = [_name(candidate.candidate_id, "candidate ID") for candidate in all_candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("candidate IDs must be unique")
    if any(not isinstance(candidate.component_specs, dict) or not candidate.component_specs
           or len(candidate.component_specs) > MAX_PARTS
           or any(not isinstance(spec, dict) for spec in candidate.component_specs.values())
           for candidate in all_candidates):
        raise ValueError("bounded explicit component specification objects required")
    target = _decimal(objective.target_voltage_v, "target voltage", Fraction(0), Fraction(12))
    tolerance = _decimal(objective.tolerance_v, "voltage tolerance", Fraction(0), Fraction(12))
    max_power = _decimal(objective.maximum_total_power_w, "maximum power", Fraction(1, 1000000), Fraction(1))
    endpoints = _project(project)
    request = {"schema": "dot-virtual-dc-request/1", "project": asdict(project),
               "baseline": asdict(baseline), "candidates": [asdict(c) for c in candidates],
               "objective": asdict(objective), "declared_source_commit": source_commit}
    if len(canonical(request)) > 64000:
        raise ValueError("experiment exceeds 64 KiB input ceiling")
    baseline_kinds = {ref: spec.get("kind") for ref, spec in baseline.component_specs.items()}
    baseline_sources = {ref: spec for ref, spec in baseline.component_specs.items() if spec.get("kind") == "V"}
    for candidate in candidates:
        if (not isinstance(candidate.component_specs, dict)
                or any(not isinstance(spec, dict) for spec in candidate.component_specs.values())
                or {ref: spec.get("kind") for ref, spec in candidate.component_specs.items()} != baseline_kinds
                or {ref: spec for ref, spec in candidate.component_specs.items() if spec.get("kind") == "V"} != baseline_sources):
            raise ValueError("candidate must preserve source values, topology and component kinds")
    results = []
    for candidate in all_candidates:
        observation = _simulate(project, candidate, objective, endpoints)
        error = abs(Fraction(observation["node_voltage_v"][objective.measured_net]) - target)
        observation["absolute_target_error_v"] = str(error)
        observation["within_declared_model_constraints"] = (
            error <= tolerance and Fraction(observation["total_resistor_power_w"]) <= max_power
            and not observation["modeled_rating_flags"])
        results.append(observation)
    order = sorted(results, key=lambda item: (
        not item["within_declared_model_constraints"], Fraction(item["absolute_target_error_v"]),
        Fraction(item["total_resistor_power_w"]), item["candidate_id"] != baseline.candidate_id,
        item["candidate_id"]))
    selected = order[0]["candidate_id"] if order[0]["within_declared_model_constraints"] else None
    ir_module = importlib.import_module("merlin.engineering_ir")
    report = {"schema": "dot-virtual-dc-comparison/1", "request_id": digest(canonical(request)),
              "request": request, "tool_version": VERSION,
              "tool_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "engineering_ir_source_sha256": hashlib.sha256(Path(ir_module.__file__).read_bytes()).hexdigest(),
              "python_version": platform.python_version(), "precision": "exact rational arithmetic",
              "results": results, "ranked_candidate_ids": [item["candidate_id"] for item in order],
              "selected_for_followup": selected, "decision": "review_required" if selected else "no_candidate_meets_model_constraints",
              "wiring_netlist": export_netlist(project), "cad_preview_openscad": export_openscad(project),
              "limitations": list(LIMITATIONS), "epistemic_status": "simulated",
              "independent_cace_status": "not_run", "physical_safety_certification": False,
              "formal_proof": False, "qualification": False, "promotion_authority": False}
    if registry is not None:
        base = "experiments/virtual-dc/" + report["request_id"]
        raw = canonical(report)
        path = base + "/reports/" + digest(raw) + ".json"
        registry.put_artifact(project_id, path, raw, "application/json")
        report["artifact_ref"] = registry.artifact_ref(project_id, path)
    return report


def divider_project() -> EngineeringProject:
    """Deterministic virtual fixture, never a wiring/build instruction."""
    pins = (Pin("1", "terminal_one", max_voltage_v=12, max_current_a=0.1),
            Pin("2", "terminal_two", max_voltage_v=12, max_current_a=0.1))
    return EngineeringProject("Virtual divider research", "mm",
        (Part("V1", "Ideal simulated source", pins), Part("R1", "Virtual upper resistor", pins),
         Part("R2", "Virtual lower resistor", pins)),
        (Net("VIN", ("V1.1", "R1.1")), Net("OUT", ("R1.2", "R2.1")),
         Net("GND", ("V1.2", "R2.2"))))


def virtual_circuit_demo(arguments: dict[str, Any]) -> dict[str, Any]:
    """Fixed dict-only private-host operation; no imports/paths/code from callers.

    The source pin identifies the inspected Engineering IR contracts, while the
    report also records the actual executing module and Engineering IR hashes.
    This operation does not access a registry or ingest private context.
    """
    if (type(arguments) is not dict or not set(arguments) <= {"operation"}
            or arguments.get("operation", "demo") != "demo"):
        raise ValueError("only the fixed virtual circuit demo operation is available")
    def divider(name: str, resistance: str) -> CircuitCandidate:
        return CircuitCandidate(name, {"V1": {"kind": "V", "value": "5"},
            "R1": {"kind": "R", "value": resistance}, "R2": {"kind": "R", "value": resistance}})
    report = compare_virtual_circuits(divider_project(), divider("baseline", "1000"),
        (divider("lower_power", "9000"),), CircuitObjective("GND", "OUT", "2.5", "0.01", "0.1"),
        source_commit="703b21e3639c239484e851bebdb1a60c755d4924")
    if len(canonical(report)) > 48000:
        raise RuntimeError("fixed virtual circuit report exceeds reviewed transport ceiling")
    return report
