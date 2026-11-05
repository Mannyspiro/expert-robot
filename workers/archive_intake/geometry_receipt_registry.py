#!/usr/bin/env python3
"""Register a validated FreeCAD geometry receipt against a project artifact.

A geometry receipt records execution and artifact identity. It does not certify
engineering correctness, manufacturability, safety or simulation validity.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from canonical_registry import connect, query_artifacts
from cad_geometry_backend import canonical_sha

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def register_geometry_receipt(database: str | Path, project_id: str, receipt: dict) -> dict:
    if not isinstance(receipt, dict):
        raise ValueError("geometry receipt must be an object")
    required = ("contract_version", "job_id", "input_sha256", "backend_id",
                "backend_version", "status", "artifacts", "receipt_sha256")
    if any(key not in receipt for key in required):
        raise ValueError("geometry receipt is missing required fields")
    if receipt["contract_version"] != "1.0":
        raise ValueError("unsupported geometry receipt version")
    if receipt["status"] not in ("completed", "rejected", "failed"):
        raise ValueError("geometry receipt must have a terminal status")
    if not isinstance(receipt["input_sha256"], str) or not SHA256.fullmatch(receipt["input_sha256"]):
        raise ValueError("geometry receipt input digest must be lowercase SHA-256")
    if not isinstance(receipt["receipt_sha256"], str) or not SHA256.fullmatch(receipt["receipt_sha256"]):
        raise ValueError("geometry receipt digest must be lowercase SHA-256")
    if canonical_sha(receipt) != receipt["receipt_sha256"]:
        raise ValueError("geometry receipt canonical digest mismatch")
    if not isinstance(receipt["backend_id"], str) or not receipt["backend_id"].strip():
        raise ValueError("geometry backend identity is required")
    if not isinstance(receipt["backend_version"], str) or not receipt["backend_version"].strip():
        raise ValueError("geometry backend version is required")

    matches = query_artifacts(str(database), project_id, limit=500)
    if not any(row["sha256"] == receipt["input_sha256"] for row in matches):
        raise ValueError("input artifact is not registered to this project")

    receipt_id = "geometry:" + receipt["receipt_sha256"]
    encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    created_at = datetime.now(timezone.utc).isoformat()
    with connect(str(database)) as db:
        project = db.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone()
        if not project:
            raise ValueError("unknown project")
        existing = db.execute(
            "SELECT receipt_json FROM verification_receipts WHERE receipt_id=?", (receipt_id,)
        ).fetchone()
        if existing:
            if existing["receipt_json"] != encoded:
                raise ValueError("receipt ID collision with different receipt content")
            return {"receipt_id": receipt_id, "status": "already_registered"}
        db.execute(
            """INSERT INTO verification_receipts
               (receipt_id,artifact_sha256,verifier_id,verifier_version,result,evidence_class,receipt_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (receipt_id, receipt["input_sha256"], receipt["backend_id"],
             receipt["backend_version"], receipt["status"], "geometry_execution",
             encoded, created_at),
        )
    return {
        "receipt_id": receipt_id,
        "project_id": project_id,
        "artifact_sha256": receipt["input_sha256"],
        "result": receipt["status"],
        "evidence_class": "geometry_execution",
        "promotion_authorized": False,
        "engineering_correctness_asserted": False,
    }


def register_geometry_receipt_file(database: str | Path, project_id: str, receipt_path: str | Path) -> dict:
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    return register_geometry_receipt(database, project_id, receipt)
