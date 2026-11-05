#!/usr/bin/env python3
"""Deterministic CAD assembly frame graph validation and transform resolution.

Transforms use column-vector convention: parent_from_component maps coordinates
expressed in a component's local frame into its immediate parent's frame.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from typing import Any

SHA256 = re.compile(r"^[0-9a-f]{64}$")
TOLERANCE = 1e-9


class AssemblyGraphError(ValueError):
    pass


def validate_transform(matrix: Any) -> list[list[float]]:
    if not isinstance(matrix, list) or len(matrix) != 4 or any(
        not isinstance(row, list) or len(row) != 4 for row in matrix
    ):
        raise AssemblyGraphError("transform must be a 4x4 matrix")
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
           for row in matrix for v in row):
        raise AssemblyGraphError("transform entries must be finite numbers")
    if any(abs(matrix[3][i] - (1.0 if i == 3 else 0.0)) > TOLERANCE for i in range(4)):
        raise AssemblyGraphError("transform must have homogeneous final row [0,0,0,1]")
    return [[float(v) for v in row] for row in matrix]


def multiply(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]


def _canonical_digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def resolve_assembly(document: dict) -> dict:
    if not isinstance(document, dict) or document.get("assembly_version") != "1.0":
        raise AssemblyGraphError("unsupported or malformed assembly document")
    assembly_id = document.get("assembly_id")
    if not isinstance(assembly_id, str) or not assembly_id.strip():
        raise AssemblyGraphError("assembly_id is required")
    units = document.get("units")
    if not isinstance(units, dict) or not units.get("length") or not units.get("angle"):
        raise AssemblyGraphError("assembly must declare length and angle units")
    components = document.get("components")
    if not isinstance(components, list) or not components:
        raise AssemblyGraphError("assembly requires at least one component")

    by_id = {}
    children = defaultdict(list)
    roots = []
    for component in components:
        if not isinstance(component, dict):
            raise AssemblyGraphError("component records must be objects")
        cid = component.get("component_id")
        if not isinstance(cid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", cid):
            raise AssemblyGraphError("invalid component_id")
        if cid in by_id:
            raise AssemblyGraphError("duplicate component_id: " + cid)
        artifact = component.get("artifact_sha256")
        if not isinstance(artifact, str) or not SHA256.fullmatch(artifact):
            raise AssemblyGraphError("component artifact_sha256 must be lowercase SHA-256")
        parent = component.get("parent_component_id")
        if parent is not None and (not isinstance(parent, str) or not parent.strip()):
            raise AssemblyGraphError("parent_component_id must be a non-empty ID or null")
        transform = validate_transform(component.get("parent_from_component"))
        normalized = {
            "component_id": cid,
            "parent_component_id": parent,
            "artifact_sha256": artifact,
            "parent_from_component": transform,
            "metadata": component.get("metadata", {}),
        }
        if not isinstance(normalized["metadata"], dict):
            raise AssemblyGraphError("component metadata must be an object")
        by_id[cid] = normalized
        if parent is None:
            roots.append(cid)
        else:
            children[parent].append(cid)

    if len(roots) != 1:
        raise AssemblyGraphError("assembly must contain exactly one root component")
    for cid, component in by_id.items():
        parent = component["parent_component_id"]
        if parent is not None and parent not in by_id:
            raise AssemblyGraphError(f"component {cid} references unknown parent {parent}")
        if parent == cid:
            raise AssemblyGraphError(f"component {cid} cannot parent itself")

    root_id = roots[0]
    resolved = {}
    visiting = set()

    def visit(cid: str) -> list[list[float]]:
        if cid in resolved:
            return resolved[cid]
        if cid in visiting:
            raise AssemblyGraphError("assembly contains a parent cycle")
        visiting.add(cid)
        component = by_id[cid]
        local = component["parent_from_component"]
        parent = component["parent_component_id"]
        root_from_component = local if parent is None else multiply(visit(parent), local)
        visiting.remove(cid)
        resolved[cid] = root_from_component
        return root_from_component

    # Resolve every node; this also rejects disconnected cycles that do not reach root.
    for cid in by_id:
        visit(cid)
    if len(resolved) != len(by_id):
        raise AssemblyGraphError("not all components are reachable from the root")

    ordered = []
    for cid in sorted(by_id):
        component = by_id[cid]
        ordered.append({
            **component,
            "root_from_component": resolved[cid],
        })
    result = {
        "assembly_version": "1.0",
        "assembly_id": assembly_id,
        "root_component_id": root_id,
        "units": units,
        "component_count": len(ordered),
        "components": ordered,
        "verification": "frame_graph_validated;geometry_interference_and_joint_constraints_not_checked",
    }
    result["assembly_sha256"] = _canonical_digest(result)
    return result


def transform_point(matrix: list[list[float]], point: list[float]) -> list[float]:
    matrix = validate_transform(matrix)
    if not isinstance(point, list) or len(point) != 3 or any(
        not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
        for v in point
    ):
        raise AssemblyGraphError("point must contain three finite coordinates")
    vector = [float(v) for v in point] + [1.0]
    output = [sum(matrix[i][j] * vector[j] for j in range(4)) for i in range(4)]
    if abs(output[3]) < TOLERANCE:
        raise AssemblyGraphError("point mapped to infinity")
    return [v / output[3] for v in output[:3]]
