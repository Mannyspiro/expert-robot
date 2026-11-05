#!/usr/bin/env python3
"""Local end-to-end smoke test for Merlin's archive/registry integrations.

Uses only Python's standard library, temporary files and a temporary SQLite DB.
No network calls, GitHub Actions, Hermes endpoint, Avrea provider or CACE runtime.
"""
from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from avrea_dispatch import canonical_sha, record_approval, submit
from cad_mcfc_model import inverse_affine, multiply, transform_point, validate_wiring
from canonical_registry import (
    attach_intake, initialize, query_artifact, query_artifacts,
    query_projects, register_project,
)
from engineering_registry import store_wiring
from hermes_event import build_event
from hermes_outbox import acknowledge, claim, enqueue, retry
from merlin_archive_intake import intake_archive
from register_inventory import register_manifest
from research_graph import export_graph


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="merlin-smoke-") as tmp:
        root = Path(tmp)
        db = root / "registry.sqlite3"
        archive = root / "sample.zip"
        extracted = root / "intake"
        initialize(db)

        # 1. Safe intake, manifest registration and project attachment.
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("README.md", "# Merlin fixture\n")
            zf.writestr("data/sample.json", json.dumps({"fixture": True}))
        manifest = intake_archive(archive, extracted)
        manifest_path = extracted / "merlin-intake-manifest.json"
        registered = register_manifest(manifest_path, db)
        check(registered["status"] == "registered", "archive manifest registration failed")
        register_project(db, "merlin-smoke", "Merlin smoke fixture")
        attach_intake(db, "merlin-smoke", manifest["intake_id"])
        check(query_projects(db)[0]["project_id"] == "merlin-smoke", "project query failed")
        artifacts = query_artifacts(db, "merlin-smoke")
        check(len(artifacts) == 2, "project artifact query did not return both files")
        sample_sha = next(x["sha256"] for x in artifacts if x["path"] == "README.md")
        check(len(query_artifact(db, sample_sha)["occurrences"]) == 1, "artifact-by-SHA query failed")

        # 2. Hermes deterministic event, idempotent enqueue, retry and acknowledgement.
        event = build_event(manifest, "merlin-smoke")
        check(build_event(manifest, "merlin-smoke")["event_id"] == event["event_id"],
              "Hermes event ID is not deterministic")
        enqueue(db, event)
        enqueue(db, event)
        lease = claim(db, "smoke-worker", lease_seconds=30)
        check(lease is not None and lease["event_id"] == event["event_id"], "Hermes lease failed")
        retry(db, event["event_id"], "smoke-worker", "fixture retry")
        lease = claim(db, "smoke-worker", lease_seconds=30)
        check(lease is not None, "Hermes retry was not claimable")
        ack = acknowledge(db, event["event_id"], "smoke-worker",
                          {"event_id": event["event_id"], "status": "accepted"})
        check(ack["state"] == "acked", "Hermes acknowledgement failed")
        check(acknowledge(db, event["event_id"], "smoke-worker",
                          {"event_id": event["event_id"], "status": "accepted"})["idempotent"],
              "Hermes duplicate acknowledgement was not idempotent")

        # 3. Avrea gate: persist explicit fixture approval; no provider means no execution.
        task = {
            "contract_version": "1.0",
            "task_id": "merlin-smoke-task",
            "approval_id": "merlin-smoke-approval",
            "capability_allowlist": ["local_fixture_validation"],
            "resource_budget": {"cpu_seconds": 30, "memory_mb": 256, "output_bytes": 1048576},
            "timeout_seconds": 30,
            "network_access": "none",
            "result_manifest_required": True,
        }
        task["task_contract_sha256"] = canonical_sha(task)
        approval = {
            "approval_id": task["approval_id"],
            "task_contract_sha256": task["task_contract_sha256"],
            "approved_by": "local-smoke-fixture",
            "approval_source": "non-production-test-fixture",
            "approved_at": "2026-11-04T00:00:00Z",
            "status": "approved",
            "approval_note": "Fixture only; not an operator authorization.",
        }
        policy = {
            "allowed_capabilities": ["local_fixture_validation"],
            "resource_maxima": {"cpu_seconds": 60, "memory_mb": 512, "output_bytes": 2097152},
            "max_timeout_seconds": 60,
        }
        record_approval(db, approval)
        task_result = submit(db, task, approval, policy, provider=None)
        check(task_result["state"] == "approved_waiting_for_provider",
              "Avrea task must wait when no provider is configured")

        # 4. CAD frame algebra and wiring graph persistence.
        translation = [[1, 0, 0, 4], [0, 1, 0, -2], [0, 0, 1, 3], [0, 0, 0, 1]]
        point = transform_point(translation, [1, 2, 3])
        check(point == [5.0, 0.0, 6.0], "CAD point transform incorrect")
        identity = multiply(translation, inverse_affine(translation))
        check(all(abs(identity[i][j] - (1 if i == j else 0)) < 1e-9
                  for i in range(4) for j in range(4)), "CAD inverse composition failed")
        connections = [
            {"connection_id": "wire-1", "from_node": "J1", "from_pin": "1",
             "to_node": "R1", "to_pin": "1", "net_name": "VCC"},
            {"connection_id": "wire-2", "from_node": "R1", "from_pin": "2",
             "to_node": "U1", "to_pin": "3", "net_name": "VCC"},
        ]
        check("VCC" in validate_wiring(connections)["nets"], "wiring validation failed")
        store_wiring(db, "merlin-smoke", connections)

        # 5. Derived research graph must have no dangling edges.
        graph = export_graph(db, "merlin-smoke")
        node_ids = {node["id"] for node in graph["nodes"]}
        check(all(edge["from"] in node_ids and edge["to"] in node_ids
                  for edge in graph["edges"]), "research graph contains dangling edges")
        check(any(node["type"] == "ElectricalNet" for node in graph["nodes"]),
              "research graph omitted electrical net")
        graph_path = root / "research-graph.json"
        graph_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n")

        print(json.dumps({
            "status": "passed",
            "database": "temporary SQLite fixture",
            "archive_files": len(artifacts),
            "hermes": "enqueue/retry/lease/ack passed",
            "avrea": "approval gate passed; provider not invoked",
            "cad_mcfc": "transform/inverse/wiring passed",
            "research_graph": {"nodes": len(graph["nodes"]), "edges": len(graph["edges"])},
            "live_services_invoked": [],
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
