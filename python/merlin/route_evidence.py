"""Content-addressed evidence bridge for Merlin CAD/wiring route proposals.

Receipts bind project, assembly/frame graph, route output, router version, and
source revision. They are provenance records, not electrical or manufacturing
qualification and never carry promotion authority.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import re
from typing import Any

from merlin.cad_assembly import CADAssembly
from merlin.engineering_ir import EngineeringProject
from merlin.engineering_project_store import project_hash
from merlin.hypothesis_ledger import Evidence, HypothesisLedger

ROUTER_VERSION = "merlin-wire-routing/0.1.0"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def create_route_evidence_receipt(
    project: EngineeringProject,
    assembly: CADAssembly,
    route_output: dict[str, Any],
    *,
    code_revision: str,
) -> dict[str, Any]:
    """Create a deterministic receipt for one geometry-proposal output."""
    if not _SHA40.fullmatch(code_revision):
        raise ValueError("code_revision must be a lowercase 40-character Git SHA")
    if route_output.get("format") != "merlin-wire-route-proposals-v0.1":
        raise ValueError("unsupported route output format")
    if route_output.get("status") != "GEOMETRY_PROPOSAL_ONLY_NOT_ELECTRICAL_OR_MANUFACTURING_APPROVAL":
        raise ValueError("route output must retain the non-qualification status")
    assembly_doc = asdict(assembly)
    frames_doc = assembly_doc.get("frames", [])
    payload = {
        "schema": "merlin-engineering-route-evidence/0.1",
        "project": project.name,
        "assembly": assembly.name,
        "project_sha256": project_hash(project),
        "assembly_sha256": _digest(assembly_doc),
        "frame_graph_sha256": _digest(frames_doc),
        "route_output_sha256": _digest(route_output),
        "router_version": ROUTER_VERSION,
        "code_revision": code_revision,
        "evidence_scope": "synthetic_3d_route_geometry_proposal",
        "qualification_status": "not_qualified",
        "promotion_authority": False,
        "limitations": [
            "Receipt proves content identity and provenance only.",
            "No electrical, thermal, mechanical, regulatory, or manufacturing qualification is implied.",
        ],
    }
    payload["receipt_sha256"] = _digest(payload)
    return payload


def verify_route_evidence_receipt(
    receipt: dict[str, Any],
    project: EngineeringProject,
    assembly: CADAssembly,
    route_output: dict[str, Any],
) -> bool:
    """Recompute all bound hashes; reject tampering and authority expansion."""
    if not isinstance(receipt, dict):
        return False
    if receipt.get("schema") != "merlin-engineering-route-evidence/0.1":
        return False
    if receipt.get("promotion_authority") is not False:
        return False
    if receipt.get("qualification_status") != "not_qualified":
        return False
    supplied_hash = receipt.get("receipt_sha256")
    if not isinstance(supplied_hash, str) or not _SHA256.fullmatch(supplied_hash):
        return False
    expected = create_route_evidence_receipt(
        project, assembly, route_output, code_revision=receipt.get("code_revision", "")
    )
    return receipt == expected


def record_route_evidence(
    ledger: HypothesisLedger,
    hypothesis_id: str,
    receipt: dict[str, Any],
    *,
    source_url: str = "",
) -> Evidence:
    """Add geometry-proposal evidence to CACE/Merlin's ledger without promotion."""
    if not isinstance(receipt, dict):
        raise ValueError("receipt must be an object")
    supplied_hash = receipt.get("receipt_sha256")
    payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if receipt.get("promotion_authority") is not False:
        raise ValueError("route evidence cannot carry promotion authority")
    if receipt.get("qualification_status") != "not_qualified":
        raise ValueError("route evidence must remain not qualified")
    if not isinstance(supplied_hash, str) or supplied_hash != _digest(payload):
        raise ValueError("route evidence receipt digest mismatch")
    if not _SHA40.fullmatch(str(receipt.get("code_revision", ""))):
        raise ValueError("route evidence has an invalid source revision")
    description = (
        f"Merlin 3D wiring geometry proposal; router {receipt['router_version']}; "
        f"project {receipt['project_sha256']}; assembly {receipt['assembly_sha256']}; "
        f"route output {receipt['route_output_sha256']}; source {receipt['code_revision']}. "
        "Synthetic geometry evidence only; not electrically or manufacturing qualified."
    )
    return ledger.add_evidence(
        hypothesis_id,
        "experiment",
        description,
        source_url=source_url,
        artifact_hash=supplied_hash,
    )
