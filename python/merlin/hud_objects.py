"""Typed, provenance-preserving view models for domain objects in the HUD.

These descriptors are presentation contracts, not proof or simulation engines.
They retain references to canonical artifacts and never promote evidence.
"""
from __future__ import annotations

from typing import Any, Mapping

WORKSPACE_TYPES = {
    "equation": ("equation", "Equation atlas"),
    "equation_atlas": ("equation", "Equation atlas"),
    "theorem": ("lean_proof", "Lean proof"),
    "proof_receipt": ("lean_proof", "Lean proof receipt"),
    "cad_model": ("freecad", "FreeCAD model"),
    "freecad_model": ("freecad", "FreeCAD model"),
    "freecad_assembly": ("freecad", "FreeCAD assembly"),
    "electrical_net": ("electrical", "Electrical net"),
    "experiment": ("simulation", "Experiment"),
    "simulation": ("simulation", "Simulation"),
    "simulation_result": ("simulation", "Simulation result"),
}


def render_descriptor(node: Any, artifact: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a safe typed workspace descriptor from one canonical graph node."""
    node_type = getattr(node, "node_type", None)
    workspace, title = WORKSPACE_TYPES.get(node_type, ("object", "Research object"))
    payload = getattr(node, "payload", {})
    if not isinstance(payload, dict):
        payload = {}
    source_uri = getattr(node, "source_uri", None)
    descriptor = {
        "schema": "merlin-hud-workspace/1",
        "workspace": workspace,
        "title": title,
        "node_id": getattr(node, "node_id", None),
        "label": getattr(node, "label", "Object"),
        "evidence_class": getattr(node, "evidence_class", "unreviewed"),
        "source_uri": source_uri,
        "artifact": dict(artifact) if artifact is not None else None,
        "payload": payload,
        "capabilities": {
            "read_only": True,
            "editable": False,
            "independent_verification_required": workspace == "lean_proof",
            "simulation_is_not_runtime": workspace == "simulation",
        },
    }
    if workspace == "equation":
        descriptor["representation"] = {
            key: payload[key] for key in (
                "latex", "expression", "equation", "formula",
                "coordinate_system", "variables", "transformations",
            ) if key in payload
        }
    elif workspace == "lean_proof":
        descriptor["proof"] = {
            key: payload[key] for key in (
                "declaration", "theorem", "statement", "assumptions",
                "axiom_dependencies", "contains_sorry", "kernel_checked",
                "receipt_sha256", "commit_sha",
            ) if key in payload
        }
    elif workspace == "freecad":
        descriptor["cad"] = {
            key: payload[key] for key in (
                "format", "document", "object_name", "assembly", "parts",
                "instances", "geometry", "size_mm", "position_mm",
                "units", "artifact_path", "export_format",
            ) if key in payload
        }
    elif workspace == "electrical":
        descriptor["netlist"] = {
            key: payload[key] for key in (
                "netlist", "nodes", "components", "connections",
                "units", "artifact_path", "engine", "status", "analysis",
                "analysis_result", "measurements", "metrics", "solver_receipt", "log",
            ) if key in payload
        }
    elif workspace == "simulation":
        descriptor["simulation"] = {
            key: payload[key] for key in (
                "engine", "parameters", "seed", "samples", "series",
                "metrics", "units", "artifact_path", "status",
            ) if key in payload
        }
    return descriptor


__all__ = ["WORKSPACE_TYPES", "render_descriptor"]
