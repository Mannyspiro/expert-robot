"""Deterministic, review-labelled schematic and harness planning exports.

These are logical topology and route-proposal artifacts, not native CAD/EDA
schematics, fabrication files, or evidence of electrical qualification.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from merlin.engineering_ir import EngineeringProject, export_netlist, validate_project


def export_wiring_graph_dot(project: EngineeringProject, physical_netlist: dict[str, Any],
                            route_output: dict[str, Any] | None = None) -> str:
    errors = [issue for issue in validate_project(project) if issue.severity == "error"]
    if errors:
        raise ValueError("cannot export invalid project wiring graph")
    if physical_netlist.get("format") != "merlin-physical-netlist-v1":
        raise ValueError("unsupported physical netlist format")
    routes = {}
    if route_output:
        for net in route_output.get("nets", []):
            routes[net["name"]] = net
    lines = [
        "graph merlin_wiring {",
        '  graph [label="MERLIN LOGICAL WIRING GRAPH — NOT A RELEASE SCHEMATIC", labelloc="t"];',
        '  node [shape=box, style="rounded"];',
    ]
    for part in sorted(project.parts, key=lambda p: p.ref):
        for pin in sorted(part.pins, key=lambda p: p.number):
            endpoint = f"{part.ref}.{pin.number}"
            label = f"{endpoint}\\n{pin.name}"
            lines.append(f'  "{endpoint}" [label="{label}"];')
    for net in sorted(project.nets, key=lambda n: n.name):
        endpoints = sorted(net.endpoints)
        if len(endpoints) < 2:
            continue
        route_info = routes.get(net.name, {})
        route_status = route_info.get("status", "not_routed")
        for endpoint in endpoints[1:]:
            lines.append(
                f'  "{endpoints[0]}" -- "{endpoint}" '
                f'[label="{net.name} | {net.net_class} | {route_status}"];'
            )
    lines.append("}")
    return "\n".join(lines) + "\n"


def export_wiring_schedule_csv(project: EngineeringProject,
                               physical_netlist: dict[str, Any],
                               route_output: dict[str, Any] | None = None) -> str:
    """Export a review-only connection schedule; never infer missing wire specs."""
    if physical_netlist.get("format") != "merlin-physical-netlist-v1":
        raise ValueError("unsupported physical netlist format")
    route_by_name = {
        item["name"]: item for item in (route_output or {}).get("nets", [])
    }
    net_by_name = {net.name: net for net in project.nets}
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow([
        "net", "net_class", "endpoint_from", "endpoint_to",
        "nominal_voltage_v", "max_current_a", "route_status",
        "route_length_mm", "polyline_mm", "wire_spec_status",
    ])
    for item in physical_netlist.get("nets", []):
        net = net_by_name[item["name"]]
        endpoints = sorted(net.endpoints)
        routed = route_by_name.get(net.name, {})
        route_pairs = routed.get("routes", [])
        for index, endpoint in enumerate(endpoints[1:]):
            route = route_pairs[index] if index < len(route_pairs) else {}
            polyline = route.get("polyline_mm")
            writer.writerow([
                net.name, net.net_class, endpoints[0], endpoint,
                net.nominal_voltage_v, net.max_current_a,
                route.get("status", "not_routed"),
                route.get("length_mm"),
                json.dumps(polyline, separators=(",", ":")) if polyline is not None else "",
                "NOT_SPECIFIED",
            ])
    return stream.getvalue()


def export_schematic_manifest(project: EngineeringProject,
                              physical_netlist: dict[str, Any],
                              route_output: dict[str, Any] | None = None) -> dict[str, Any]:
    """Machine-readable logical schematic manifest tied to source project data."""
    if physical_netlist.get("format") != "merlin-physical-netlist-v1":
        raise ValueError("unsupported physical netlist format")
    return {
        "schema": "merlin-logical-schematic-manifest/0.1",
        "project": project.name,
        "units": "mm",
        "parts": [
            {"ref": part.ref, "name": part.name,
             "pins": [{"number": pin.number, "name": pin.name,
                       "position_mm": list(pin.position_mm) if pin.position_mm else None}
                      for pin in part.pins]}
            for part in sorted(project.parts, key=lambda p: p.ref)
        ],
        "nets": [
            {"name": net.name, "class": net.net_class,
             "endpoints": sorted(net.endpoints),
             "nominal_voltage_v": net.nominal_voltage_v,
             "max_current_a": net.max_current_a}
            for net in sorted(project.nets, key=lambda n: n.name)
        ],
        "route_proposals": (route_output or {}).get("nets", []),
        "artifact_status": "LOGICAL_SCHEMATIC_AND_ROUTE_PROPOSALS_NOT_RELEASE_DOCUMENTS",
        "wire_specification": "NOT_SPECIFIED",
        "limitations": [
            "No component symbols, footprints, manufacturer part numbers, protection devices or design-rule constraints are inferred.",
            "A graph diagram is a connectivity view, not an electrical schematic with validated circuit behavior.",
            "No wire gauge, insulation, ampacity, clearance, thermal or manufacturing qualification is implied.",
        ],
    }
