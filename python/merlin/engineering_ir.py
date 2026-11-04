"""Typed engineering intermediate representation for Merlin CAD and wiring.

This module is deliberately deterministic and offline. It validates a shared
project model and exports a simple OpenSCAD assembly plus a wiring netlist.
It is not a substitute for electrical code review, simulation, ERC/DRC, or
qualified engineering sign-off.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Pin:
    number: str
    name: str
    max_voltage_v: float | None = None
    max_current_a: float | None = None
    position_mm: tuple[float, float, float] | None = None
    direction: tuple[float, float, float] | None = None


@dataclass(frozen=True)
class Part:
    ref: str
    name: str
    pins: tuple[Pin, ...]
    size_mm: tuple[float, float, float] = (10.0, 10.0, 3.0)
    position_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    model: str = "box"


@dataclass(frozen=True)
class Net:
    name: str
    endpoints: tuple[str, ...]
    nominal_voltage_v: float | None = None
    max_current_a: float | None = None
    net_class: str = "signal"


@dataclass(frozen=True)
class EngineeringProject:
    name: str
    units: str
    parts: tuple[Part, ...]
    nets: tuple[Net, ...]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    message: str


def _finite_positive(value: float | None) -> bool:
    return value is not None and value > 0 and value < float("inf")


def _pin_index(project: EngineeringProject) -> dict[str, Pin]:
    return {
        f"{part.ref}.{pin.number}": pin
        for part in project.parts
        for pin in part.pins
    }


def validate_project(project: EngineeringProject) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    if project.units != "mm":
        issues.append(ValidationIssue("UNIT_UNSUPPORTED", "error",
                                      "Engineering geometry must use millimetres (mm)."))
    refs = [part.ref for part in project.parts]
    if len(refs) != len(set(refs)):
        issues.append(ValidationIssue("DUPLICATE_REFERENCE", "error",
                                      "Part reference designators must be unique."))
    for part in project.parts:
        if not part.ref.strip() or not part.name.strip():
            issues.append(ValidationIssue("PART_IDENTITY_MISSING", "error",
                                          "Every part needs a reference and name."))
        if part.model not in {"box"}:
            issues.append(ValidationIssue("MODEL_UNSUPPORTED", "error",
                                          f"{part.ref}: only the deterministic box model is currently supported."))
        if len(part.size_mm) != 3 or any(not _finite_positive(v) for v in part.size_mm):
            issues.append(ValidationIssue("INVALID_PART_SIZE", "error",
                                          f"{part.ref}: size must contain three positive finite dimensions."))
        if len(part.position_mm) != 3 or any(not (-1e6 < v < 1e6) for v in part.position_mm):
            issues.append(ValidationIssue("INVALID_PART_POSITION", "error",
                                          f"{part.ref}: position must contain three finite coordinates within +/-1e6 mm."))
        numbers = [pin.number for pin in part.pins]
        if len(numbers) != len(set(numbers)):
            issues.append(ValidationIssue("DUPLICATE_PIN", "error",
                                          f"{part.ref}: pin numbers must be unique."))
        for pin in part.pins:
            if not pin.number.strip() or not pin.name.strip():
                issues.append(ValidationIssue("PIN_IDENTITY_MISSING", "error",
                                              f"{part.ref}: every pin needs a number and name."))
            if pin.max_voltage_v is not None and not _finite_positive(pin.max_voltage_v):
                issues.append(ValidationIssue("INVALID_PIN_VOLTAGE_RATING", "error",
                                              f"{part.ref}.{pin.number}: voltage rating must be positive."))
            if pin.max_current_a is not None and not _finite_positive(pin.max_current_a):
                issues.append(ValidationIssue("INVALID_PIN_CURRENT_RATING", "error",
                                              f"{part.ref}.{pin.number}: current rating must be positive."))
            if pin.position_mm is not None:
                if len(pin.position_mm) != 3 or any(not (-1e6 < v < 1e6) for v in pin.position_mm):
                    issues.append(ValidationIssue("INVALID_PIN_POSITION", "error",
                                                  f"{part.ref}.{pin.number}: pin position must contain three finite coordinates."))
            if pin.direction is not None:
                if len(pin.direction) != 3 or any(not (-1.000001 <= v <= 1.000001) for v in pin.direction):
                    issues.append(ValidationIssue("INVALID_PIN_DIRECTION", "error",
                                                  f"{part.ref}.{pin.number}: pin direction must be a unit vector."))
                elif abs(sum(v * v for v in pin.direction) - 1.0) > 1e-5:
                    issues.append(ValidationIssue("INVALID_PIN_DIRECTION", "error",
                                                  f"{part.ref}.{pin.number}: pin direction must be normalized."))
    known = _pin_index(project)
    net_names = [net.name for net in project.nets]
    if len(net_names) != len(set(net_names)):
        issues.append(ValidationIssue("DUPLICATE_NET", "error",
                                      "Net names must be unique."))
    assigned: dict[str, str] = {}
    for net in project.nets:
        if not net.name.strip():
            issues.append(ValidationIssue("NET_NAME_MISSING", "error", "Every net needs a name."))
        if len(net.endpoints) < 2:
            issues.append(ValidationIssue("FLOATING_NET", "warning",
                                          f"{net.name}: fewer than two endpoints are connected."))
        if net.nominal_voltage_v is not None and not (-1e4 < net.nominal_voltage_v < 1e4):
            issues.append(ValidationIssue("INVALID_NET_VOLTAGE", "error",
                                          f"{net.name}: nominal voltage is outside the supported range."))
        if net.max_current_a is not None and not _finite_positive(net.max_current_a):
            issues.append(ValidationIssue("INVALID_NET_CURRENT", "error",
                                          f"{net.name}: maximum current must be positive."))
        for endpoint in net.endpoints:
            if endpoint not in known:
                issues.append(ValidationIssue("UNKNOWN_ENDPOINT", "error",
                                              f"{net.name}: endpoint {endpoint} does not exist."))
                continue
            if endpoint in assigned:
                issues.append(ValidationIssue("PIN_ON_MULTIPLE_NETS", "error",
                                              f"{endpoint} is assigned to both {assigned[endpoint]} and {net.name}."))
            assigned[endpoint] = net.name
            pin = known[endpoint]
            if net.nominal_voltage_v is not None and pin.max_voltage_v is not None:
                if abs(net.nominal_voltage_v) > pin.max_voltage_v:
                    issues.append(ValidationIssue("PIN_VOLTAGE_EXCEEDED", "error",
                                                  f"{endpoint}: {net.name} voltage exceeds the pin rating."))
            if net.max_current_a is not None and pin.max_current_a is not None:
                if net.max_current_a > pin.max_current_a:
                    issues.append(ValidationIssue("PIN_CURRENT_EXCEEDED", "error",
                                                  f"{endpoint}: {net.name} current exceeds the pin rating."))
    return tuple(issues)


def export_netlist(project: EngineeringProject) -> dict:
    issues = validate_project(project)
    if any(issue.severity == "error" for issue in issues):
        raise ValueError("cannot export an invalid engineering project")
    return {
        "format": "merlin-netlist-v1",
        "project": project.name,
        "units": project.units,
        "nets": [
            {"name": net.name, "endpoints": list(net.endpoints),
             "nominal_voltage_v": net.nominal_voltage_v,
             "max_current_a": net.max_current_a, "net_class": net.net_class}
            for net in project.nets
        ],
        "parts": [
            {"ref": part.ref, "name": part.name,
             "pins": [asdict(pin) for pin in part.pins]}
            for part in project.parts
        ],
        "validation": [asdict(issue) for issue in issues],
    }


def export_openscad(project: EngineeringProject) -> str:
    issues = validate_project(project)
    if any(issue.severity == "error" for issue in issues):
        raise ValueError("cannot export an invalid engineering project")
    lines = [
        "// Generated by Merlin Engineering IR v1",
        "// Units: millimetres. Validate dimensions before fabrication.",
        "$fn = 32;",
        "module part_box(size) { cube(size, center=true); }",
    ]
    for part in project.parts:
        x, y, z = part.position_mm
        sx, sy, sz = part.size_mm
        lines.append(
            f"translate([{x}, {y}, {z}]) part_box([{sx}, {sy}, {sz}]); // {part.ref}: {part.name}"
        )
    return "\n".join(lines) + "\n"


def write_exports(project: EngineeringProject, directory: str | Path) -> tuple[Path, Path]:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    netlist_path = target / "merlin_netlist.json"
    scad_path = target / "merlin_assembly.scad"
    netlist_path.write_text(json.dumps(export_netlist(project), indent=2), encoding="utf-8")
    scad_path.write_text(export_openscad(project), encoding="utf-8")
    return netlist_path, scad_path
