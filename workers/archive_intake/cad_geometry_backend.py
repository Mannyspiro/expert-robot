#!/usr/bin/env python3
"""Fail-closed CAD geometry-kernel contract and artifact receipt validation.

This module deliberately does not shell out to a CAD executable. Concrete
FreeCAD/OpenCascade adapters must implement GeometryBackend and be configured
explicitly by the host application.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Protocol

SHA256 = re.compile(r"^[0-9a-f]{64}$")
SUPPORTED_INPUTS = {".step", ".stp", ".iges", ".igs", ".stl", ".obj", ".3mf"}
SUPPORTED_OPERATIONS = {"inspect", "tessellate", "validate_topology", "export_mesh"}


class GeometryContractError(ValueError):
    """Invalid geometry request, backend response or output artifact."""


class GeometryBackend(Protocol):
    backend_id: str
    backend_version: str

    def execute(self, request: dict, input_path: Path, output_dir: Path) -> dict: ...


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha(value: dict) -> str:
    payload = dict(value)
    payload.pop("receipt_sha256", None)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _inside(root: Path, candidate: Path) -> Path:
    root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GeometryContractError("path escapes its configured workspace") from exc
    if not resolved.is_file():
        raise GeometryContractError("expected a regular file")
    return resolved


def validate_request(request: dict, workspace: Path) -> tuple[dict, Path]:
    if not isinstance(request, dict):
        raise GeometryContractError("geometry request must be an object")
    required = (
        "contract_version", "job_id", "operation", "input_path",
        "input_sha256", "input_format", "units", "coordinate_frame",
        "requested_outputs",
    )
    if any(key not in request for key in required):
        raise GeometryContractError("geometry request is missing required fields")
    if request["contract_version"] != "1.0":
        raise GeometryContractError("unsupported geometry contract version")
    if not isinstance(request["job_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", request["job_id"]
    ):
        raise GeometryContractError("invalid job_id")
    if request["operation"] not in SUPPORTED_OPERATIONS:
        raise GeometryContractError("unsupported geometry operation")
    if not isinstance(request["input_format"], str) or request["input_format"].lower() not in {
        ext[1:] for ext in SUPPORTED_INPUTS
    }:
        raise GeometryContractError("unsupported geometry input format")
    if not isinstance(request["input_sha256"], str) or not SHA256.fullmatch(request["input_sha256"]):
        raise GeometryContractError("input_sha256 must be lowercase SHA-256")
    if not isinstance(request["units"], dict) or not request["units"].get("length") or not request["units"].get("angle"):
        raise GeometryContractError("explicit length and angle units are required")
    frame = request["coordinate_frame"]
    if not isinstance(frame, dict) or not all(frame.get(k) for k in ("frame_id", "handedness", "axis_convention")):
        raise GeometryContractError("coordinate frame must declare ID, handedness and axis convention")
    if frame["handedness"] not in ("right", "left"):
        raise GeometryContractError("coordinate frame handedness must be right or left")
    outputs = request["requested_outputs"]
    if not isinstance(outputs, list) or not outputs or any(
        x not in ("topology_report", "mesh", "bounding_box", "volume", "surface_area")
        for x in outputs
    ):
        raise GeometryContractError("requested_outputs contains an unsupported output")
    root = workspace.resolve(strict=True)
    candidate = root / request["input_path"]
    input_path = _inside(root, candidate)
    actual_format = input_path.suffix.lower().lstrip(".")
    if input_path.suffix.lower() not in SUPPORTED_INPUTS:
        raise GeometryContractError("input file extension does not match supported geometry formats")
    if request["input_format"].lower() != actual_format:
        raise GeometryContractError("declared input_format does not match the input file extension")
    mesh_parameters = request.get("mesh_parameters", {})
    if not isinstance(mesh_parameters, dict):
        raise GeometryContractError("mesh_parameters must be an object")
    for key in ("linear_deflection", "angular_deflection"):
        if key in mesh_parameters:
            try:
                value = float(mesh_parameters[key])
            except (TypeError, ValueError) as exc:
                raise GeometryContractError(f"{key} must be a finite positive number") from exc
            import math
            if not math.isfinite(value) or value <= 0:
                raise GeometryContractError(f"{key} must be a finite positive number")
    if ("mesh" in outputs or request["operation"] in ("tessellate", "export_mesh")):
        if any(key not in mesh_parameters for key in ("linear_deflection", "angular_deflection")):
            raise GeometryContractError("mesh jobs must explicitly set linear_deflection and angular_deflection")
    if sha256_file(input_path) != request["input_sha256"]:
        raise GeometryContractError("input file digest does not match request")
    return request, input_path


def validate_backend_receipt(
    request: dict, receipt: dict, output_dir: Path, backend_id: str, backend_version: str
) -> dict:
    if not isinstance(receipt, dict):
        raise GeometryContractError("backend receipt must be an object")
    if receipt.get("job_id") != request.get("job_id"):
        raise GeometryContractError("backend receipt job_id mismatch")
    if receipt.get("input_sha256") != request.get("input_sha256"):
        raise GeometryContractError("backend receipt input digest mismatch")
    if receipt.get("backend_id") != backend_id or receipt.get("backend_version") != backend_version:
        raise GeometryContractError("backend identity/version mismatch")
    if receipt.get("status") not in ("completed", "rejected", "failed"):
        raise GeometryContractError("backend must return an explicit terminal status")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, list):
        raise GeometryContractError("backend artifacts must be an array")
    root = output_dir.resolve(strict=True)
    validated = []
    seen = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            raise GeometryContractError("invalid output artifact record")
        relative = Path(artifact["path"])
        if relative.is_absolute() or ".." in relative.parts or str(relative) in ("", "."):
            raise GeometryContractError("output artifact path must be relative and traversal-free")
        path = _inside(root, root / relative)
        if str(relative) in seen:
            raise GeometryContractError("duplicate output artifact path")
        seen.add(str(relative))
        digest = artifact.get("sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise GeometryContractError("output artifact SHA-256 is invalid")
        actual = sha256_file(path)
        if actual != digest:
            raise GeometryContractError("output artifact digest mismatch")
        validated.append({"path": str(relative), "sha256": actual, "size_bytes": path.stat().st_size})
    if receipt["status"] == "completed" and not validated:
        raise GeometryContractError("completed geometry job must produce at least one artifact")
    normalized = {
        "contract_version": "1.0",
        "job_id": request["job_id"],
        "input_sha256": request["input_sha256"],
        "backend_id": backend_id,
        "backend_version": backend_version,
        "status": receipt["status"],
        "artifacts": validated,
        "metrics": receipt.get("metrics", {}),
        "limitations": receipt.get("limitations", []),
        "verification": "artifact_hashes_checked;geometry_correctness_not_independently_verified",
    }
    normalized["receipt_sha256"] = canonical_sha(normalized)
    return normalized


def execute_job(request: dict, workspace: Path, output_dir: Path, backend: GeometryBackend) -> dict:
    """Run only a caller-supplied backend object; there is no implicit executable lookup."""
    validated, input_path = validate_request(request, workspace)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve(strict=True)
    receipt = backend.execute(validated, input_path, output_dir)
    return validate_backend_receipt(
        validated, receipt, output_dir, backend.backend_id, backend.backend_version
    )
