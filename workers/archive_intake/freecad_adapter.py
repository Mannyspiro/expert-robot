#!/usr/bin/env python3
"""Optional FreeCAD geometry adapter for Merlin's explicit backend contract.

This adapter imports FreeCAD modules only when explicitly constructed inside a
FreeCAD Python runtime. It never installs FreeCAD, discovers executables, or
launches subprocesses. The host must supply the already-imported App, Import,
Part, MeshPart and Mesh modules.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from cad_geometry_backend import GeometryContractError, sha256_file


class FreeCADUnavailable(RuntimeError):
    """The caller did not provide a usable FreeCAD runtime."""


def _finite(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise GeometryContractError("FreeCAD returned a non-finite geometry value")
    return number


def _topology_status(operation: str, all_shapes_valid: bool) -> str:
    """A topology-validation operation passes only when every imported shape is valid."""
    if operation == "validate_topology" and not all_shapes_valid:
        return "failed"
    return "completed"


def _placement_matrix(placement: Any) -> list[list[float]]:
    matrix = placement.toMatrix()
    values = matrix.A
    if len(values) != 16:
        raise GeometryContractError("FreeCAD placement did not return 16 matrix values")
    return [[_finite(values[row * 4 + col]) for col in range(4)] for row in range(4)]


class FreeCADBackend:
    """GeometryBackend implementation using caller-injected FreeCAD modules.

    Tested only by inspection in this repository; actual FreeCAD execution is
    intentionally not claimed. API differences must be qualified against the
    exact FreeCAD build before production use.
    """

    backend_id = "freecad"
    
    def __init__(
        self,
        *,
        app: Any,
        importer: Any,
        part: Any,
        mesh_part: Any,
        mesh: Any,
        backend_version: str,
    ) -> None:
        required = (app, importer, part, mesh_part, mesh)
        if any(module is None for module in required):
            raise FreeCADUnavailable("all FreeCAD runtime modules must be explicitly supplied")
        if not isinstance(backend_version, str) or not backend_version.strip():
            raise FreeCADUnavailable("an exact FreeCAD build/version string is required")
        if not callable(getattr(importer, "insert", None)):
            raise FreeCADUnavailable("FreeCAD Import module lacks insert()")
        self.app = app
        self.importer = importer
        self.part = part
        self.mesh_part = mesh_part
        self.mesh = mesh
        self.backend_version = backend_version

    @classmethod
    def from_freecad_runtime(cls, backend_version: str) -> "FreeCADBackend":
        """Explicit opt-in factory; call only from FreeCAD's own Python runtime."""
        try:
            import FreeCAD as App
            import Import
            import Part
            import Mesh
            import MeshPart
        except ImportError as exc:
            raise FreeCADUnavailable(
                "FreeCAD runtime unavailable; run this factory inside a compatible FreeCAD Python"
            ) from exc
        return cls(
            app=App, importer=Import, part=Part, mesh_part=MeshPart,
            mesh=Mesh, backend_version=backend_version,
        )

    def execute(self, request: dict, input_path: Path, output_dir: Path) -> dict:
        if sha256_file(input_path) != request["input_sha256"]:
            raise GeometryContractError("input changed after request validation")
        document = None
        artifacts = []
        metrics = {"object_count": 0, "shape_count": 0}
        limitations = [
            "FreeCAD import and tessellation are backend operations, not independent proof of design correctness",
            "assembly hierarchy is reported from document object groups where exposed; source-format semantics may differ",
            "unit conversion and coordinate-frame conversion are not inferred; source units/frame must be established by the caller",
            "topology validity is limited to FreeCAD Shape validity checks",
        ]
        try:
            document = self.app.newDocument("Merlin_" + request["job_id"].replace("-", "_"))
            self.importer.insert(str(input_path), document.Name)
            document.recompute()
            objects = [
                obj for obj in document.Objects
                if getattr(obj, "Shape", None) is not None
                and not getattr(obj, "Shape").isNull()
            ]
            metrics["object_count"] = len(document.Objects)
            metrics["shape_count"] = len(objects)
            if not objects:
                raise GeometryContractError("FreeCAD import produced no non-null shapes")

            topology = []
            bounds = []
            total_volume = 0.0
            total_area = 0.0
            for obj in objects:
                shape = obj.Shape
                valid = bool(shape.isValid())
                solids = len(getattr(shape, "Solids", []))
                shells = len(getattr(shape, "Shells", []))
                faces = len(getattr(shape, "Faces", []))
                edges = len(getattr(shape, "Edges", []))
                vertices = len(getattr(shape, "Vertexes", []))
                box = shape.BoundBox
                item = {
                    "object_name": str(getattr(obj, "Name", "")),
                    "label": str(getattr(obj, "Label", "")),
                    "shape_valid": valid,
                    "solid_count": solids,
                    "shell_count": shells,
                    "face_count": faces,
                    "edge_count": edges,
                    "vertex_count": vertices,
                    "placement": _placement_matrix(obj.Placement),
                    "bounding_box": {
                        "xmin": _finite(box.XMin), "ymin": _finite(box.YMin),
                        "zmin": _finite(box.ZMin), "xmax": _finite(box.XMax),
                        "ymax": _finite(box.YMax), "zmax": _finite(box.ZMax),
                    },
                }
                topology.append(item)
                bounds.append(item["bounding_box"])
                total_volume += _finite(shape.Volume)
                total_area += _finite(shape.Area)

            requested = set(request["requested_outputs"])
            all_shapes_valid = all(x["shape_valid"] for x in topology)
            metrics["all_shapes_valid"] = all_shapes_valid
            if "topology_report" in requested or request["operation"] == "validate_topology":
                path = output_dir / "topology-report.json"
                path.write_text(json.dumps({
                    "backend": self.backend_id,
                    "backend_version": self.backend_version,
                    "input_sha256": request["input_sha256"],
                    "objects": topology,
                    "all_shapes_valid": all_shapes_valid,
                }, sort_keys=True, indent=2) + "\n", encoding="utf-8")
                artifacts.append({"path": path.name, "sha256": sha256_file(path)})

            if "bounding_box" in requested:
                path = output_dir / "bounding-boxes.json"
                path.write_text(json.dumps(bounds, sort_keys=True, indent=2) + "\n", encoding="utf-8")
                artifacts.append({"path": path.name, "sha256": sha256_file(path)})

            if "volume" in requested:
                path = output_dir / "volume.json"
                path.write_text(json.dumps({"sum_of_shape_volumes": total_volume}, sort_keys=True) + "\n", encoding="utf-8")
                artifacts.append({"path": path.name, "sha256": sha256_file(path)})

            if "surface_area" in requested:
                path = output_dir / "surface-area.json"
                path.write_text(json.dumps({"sum_of_shape_areas": total_area}, sort_keys=True) + "\n", encoding="utf-8")
                artifacts.append({"path": path.name, "sha256": sha256_file(path)})

            if "mesh" in requested or request["operation"] in ("tessellate", "export_mesh"):
                params = request.get("mesh_parameters", {})
                linear = _finite(params.get("linear_deflection", 0.1))
                angular = _finite(params.get("angular_deflection", 0.5))
                if linear <= 0 or angular <= 0:
                    raise GeometryContractError("mesh deflection parameters must be positive")
                mesh_objects = []
                for index, obj in enumerate(objects):
                    mesh_obj = self.mesh_part.meshFromShape(
                        Shape=obj.Shape,
                        LinearDeflection=linear,
                        AngularDeflection=angular,
                        Relative=False,
                    )
                    if mesh_obj is None or getattr(mesh_obj, "CountFacets", lambda: 0)() <= 0:
                        raise GeometryContractError("FreeCAD tessellation returned an empty mesh")
                    mesh_path = output_dir / f"shape-{index:04d}.stl"
                    self.mesh.export([mesh_obj], str(mesh_path))
                    artifacts.append({"path": mesh_path.name, "sha256": sha256_file(mesh_path)})
                    mesh_objects.append(mesh_path.name)
                metrics["mesh_files"] = len(mesh_objects)
                metrics["mesh_parameters"] = {
                    "linear_deflection": linear,
                    "angular_deflection": angular,
                    "relative": False,
                }

            return {
                "job_id": request["job_id"],
                "input_sha256": request["input_sha256"],
                "backend_id": self.backend_id,
                "backend_version": self.backend_version,
                "status": _topology_status(request["operation"], all_shapes_valid),
                "artifacts": artifacts,
                "metrics": metrics,
                "limitations": limitations,
            }
        except Exception:
            # Preserve failure semantics for the contract validator; no partial
            # artifact set is represented as a successful job.
            raise
        finally:
            if document is not None:
                try:
                    self.app.closeDocument(document.Name)
                except Exception:
                    pass


def build_assembly_graph(
    document: Any,
    *,
    assembly_id: str,
    assembly_artifact_sha256: str,
    artifact_sha256_for_object: Any,
    parent_from_component_for_object: Any,
    length_unit: str,
    angle_unit: str,
) -> dict:
    """Export a FreeCAD document's explicit Group hierarchy as Merlin frame graph.

    Placement semantics differ across FreeCAD object types and importers. Rather
    than silently treating global Placement as parent-relative, the caller must
    provide a resolver that returns the exact parent_from_component matrix for
    each object. Likewise, every component must be bound to a registered
    artifact digest by the caller.
    """
    import re
    from cad_assembly_graph import resolve_assembly

    if not re.fullmatch(r"[0-9a-f]{64}", assembly_artifact_sha256):
        raise GeometryContractError("assembly artifact digest must be lowercase SHA-256")
    if not callable(artifact_sha256_for_object) or not callable(parent_from_component_for_object):
        raise GeometryContractError("artifact and parent-relative placement resolvers are required")
    if not isinstance(length_unit, str) or not length_unit.strip():
        raise GeometryContractError("length unit must be explicit")
    if not isinstance(angle_unit, str) or not angle_unit.strip():
        raise GeometryContractError("angle unit must be explicit")

    objects = list(getattr(document, "Objects", []))
    by_identity = {id(obj): obj for obj in objects}
    if len(by_identity) != len(objects):
        raise GeometryContractError("document contains repeated object references")

    # Only objects with non-null shapes become physical component nodes.
    physical = {}
    for obj in objects:
        shape = getattr(obj, "Shape", None)
        if shape is not None and not getattr(shape, "isNull", lambda: False)():
            name = str(getattr(obj, "Name", ""))
            if not name:
                raise GeometryContractError("component object has no stable Name")
            if name in physical:
                raise GeometryContractError("component object names must be unique")
            physical[name] = obj

    if not physical:
        raise GeometryContractError("document contains no physical component shapes")

    parent_by_name = {name: None for name in physical}
    for container in objects:
        container_name = str(getattr(container, "Name", ""))
        if container_name not in physical:
            continue
        for child in getattr(container, "Group", []) or []:
            child_name = str(getattr(child, "Name", ""))
            if child_name not in physical:
                continue
            if parent_by_name[child_name] is not None:
                raise GeometryContractError("component is assigned to multiple assembly parents")
            parent_by_name[child_name] = container_name

    nodes = [{
        "component_id": "assembly-root",
        "parent_component_id": None,
        "artifact_sha256": assembly_artifact_sha256,
        "parent_from_component": [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "metadata": {"kind": "synthetic_assembly_root"},
    }]
    for name in sorted(physical):
        obj = physical[name]
        parent_name = parent_by_name[name]
        digest = artifact_sha256_for_object(obj)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise GeometryContractError("every component must resolve to a registered SHA-256 artifact")
        matrix = parent_from_component_for_object(obj, physical.get(parent_name))
        if not isinstance(matrix, list):
            matrix = [list(row) for row in matrix]
        nodes.append({
            "component_id": name,
            "parent_component_id": parent_name or "assembly-root",
            "artifact_sha256": digest,
            "parent_from_component": matrix,
            "metadata": {
                "label": str(getattr(obj, "Label", name)),
                "freecad_type": str(getattr(obj, "TypeId", "")),
            },
        })

    graph = {
        "assembly_version": "1.0",
        "assembly_id": assembly_id,
        "units": {"length": length_unit, "angle": angle_unit},
        "components": nodes,
    }
    resolve_assembly(graph)
    return graph
