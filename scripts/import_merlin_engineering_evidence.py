#!/usr/bin/env python3
"""Import a bounded, hash-checked FreeCAD/ngspice evidence bundle into Merlin.

This registers artifacts and graph objects as unreviewed execution evidence.
It does not create Lean receipts, assert scientific truth, or authorize promotion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import mimetypes
from pathlib import Path
from typing import Any

from merlin.event_outbox import MerlinEventOutbox
from merlin.hud_activity import PHASES
from merlin.knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.telemetry import normalize_event


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def require_digest(path: Path, expected: str, label: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch: {actual} != {expected}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--artifact-id", required=True, type=int)
    parser.add_argument("--artifact-sha256", required=True)
    args = parser.parse_args()

    if len(args.source_commit) != 40 or any(c not in "0123456789abcdef" for c in args.source_commit):
        raise ValueError("source commit must be a full lowercase Git SHA")
    if len(args.artifact_sha256) != 64 or any(c not in "0123456789abcdef" for c in args.artifact_sha256):
        raise ValueError("source artifact SHA-256 is malformed")

    root = args.evidence_dir.resolve()
    required = [
        "manifest.json", "freecad-mesh.json", "freecad-registration.json",
        "merlin_project.FCStd", "merlin_project.step", "assembly.scad",
        "merlin_netlist.json", "divider.cir", "ngspice-result.json",
        "engineering-ir.json", "canonical-registry/merlin.sqlite3",
        "canonical-graph.sqlite3",
    ]
    for relative in required:
        candidate = (root / relative).resolve()
        if root not in candidate.parents or not candidate.is_file():
            raise ValueError(f"required evidence file missing or unsafe: {relative}")

    manifest = read_json(root / "manifest.json")
    registration = read_json(root / "freecad-registration.json")
    mesh_path = root / "freecad-mesh.json"
    fcstd_path = root / "merlin_project.FCStd"
    step_path = root / "merlin_project.step"
    netlist_path = root / "merlin_netlist.json"
    circuit_path = root / "divider.cir"
    result_path = root / "ngspice-result.json"

    if manifest.get("schema") != "merlin-engineering-integration/2":
        raise ValueError("unsupported engineering evidence manifest")
    if manifest.get("authority") != "qualification-only" or manifest.get("promotion_authority") is not False:
        raise ValueError("evidence manifest authority boundary is invalid")
    if manifest.get("freecad_runtime") != "executed":
        raise ValueError("FreeCAD runtime execution is not established")
    if manifest.get("ngspice_returncode") != 0 or manifest.get("ngspice_measurement_status") != "PASS":
        raise ValueError("ngspice execution did not pass")
    expected = float(manifest.get("ngspice_expected_mid_voltage_v", math.nan))
    measured = float(manifest.get("ngspice_measured_mid_voltage_v", math.nan))
    if not math.isfinite(expected) or not math.isfinite(measured) or not math.isclose(expected, measured, rel_tol=0.0, abs_tol=1e-6):
        raise ValueError("ngspice MID measurement does not match its declared tolerance")

    require_digest(mesh_path, manifest["freecad_mesh_sha256"], "FreeCAD mesh")
    require_digest(fcstd_path, manifest["freecad_fcstd_sha256"], "FreeCAD document")
    require_digest(step_path, manifest["freecad_step_sha256"], "STEP assembly")
    require_digest(result_path, manifest["ngspice_result_sha256"], "ngspice result")
    require_digest(circuit_path, manifest["spice_netlist_sha256"], "SPICE netlist")
    if registration.get("schema") != "merlin-freecad-registration/1":
        raise ValueError("FreeCAD registration schema mismatch")
    if registration.get("artifact_sha256") != manifest["freecad_mesh_sha256"] or registration.get("artifact_verified") is not True:
        raise ValueError("FreeCAD registration does not bind the mesh digest")

    # Independently re-check the source run's own registry and graph snapshot.
    source_registry = MerlinRegistry(root / "canonical-registry")
    if not source_registry.verify_artifact(manifest["freecad_mesh_sha256"]):
        raise ValueError("source registry cannot verify the FreeCAD mesh blob")
    source_graph = MerlinKnowledgeGraph(root / "canonical-graph.sqlite3")
    source_cad = source_graph.get_node(registration["cad_node_id"])
    source_mesh_artifact = source_graph.get_node(registration["artifact_node_id"])
    if source_cad is None or source_mesh_artifact is None:
        raise ValueError("source graph is missing the registered CAD or artifact node")

    mesh = read_json(mesh_path)
    netlist_data = read_json(netlist_path)
    spice_result = read_json(result_path)
    project_id = "merlin-engineering-smoke"
    source_uri = f"https://github.com/Mannyspiro/expert-robot/actions/runs/{args.run_id}"
    data_dir = args.data_dir.resolve()
    registry = MerlinRegistry(data_dir / "registry")
    graph = MerlinKnowledgeGraph(data_dir / "knowledge-graph.sqlite3")
    registry.register_project(
        project_id,
        "Merlin Engineering Smoke",
        version="0.1.0",
        metadata={
            "source_repository": "Mannyspiro/expert-robot",
            "source_commit": args.source_commit,
            "source_workflow_run_id": args.run_id,
            "source_artifact_id": args.artifact_id,
            "source_artifact_sha256": args.artifact_sha256,
            "authority": "qualification-only",
            "evidence_class": "unreviewed_execution_evidence",
            "promotion_authority": False,
        },
    )

    logical_files = [
        ("cad/freecad-import-smoke.json", mesh_path, "application/vnd.merlin.freecad-mesh+json"),
        ("cad/merlin_project.FCStd", fcstd_path, "application/x-freecad-document"),
        ("cad/merlin_project.step", step_path, "model/step"),
        ("cad/assembly.scad", root / "assembly.scad", "application/x-openscad"),
        ("electrical/merlin_netlist.json", netlist_path, "application/json"),
        ("electrical/divider.cir", circuit_path, "text/plain"),
        ("simulation/ngspice-result.json", result_path, "application/json"),
        ("engineering/engineering-ir.json", root / "engineering-ir.json", "application/json"),
        ("evidence/freecad-registration.json", root / "freecad-registration.json", "application/json"),
        ("evidence/manifest.json", root / "manifest.json", "application/json"),
        ("evidence/freecad_document_export.FCMacro", root / "freecad_document_export.FCMacro", "text/x-python"),
        ("evidence/merlin_import.FCMacro", root / "merlin_import.FCMacro", "text/x-python"),
    ]
    digests: dict[str, str] = {}
    for logical_path, source_path, media_type in logical_files:
        if not source_path.is_file():
            raise ValueError(f"evidence file missing: {source_path.name}")
        content = source_path.read_bytes()
        digest = registry.put_artifact(project_id, logical_path, content, media_type)
        if hashlib.sha256(content).hexdigest() != digest or not registry.verify_artifact(digest):
            raise RuntimeError(f"target registry failed to verify {logical_path}")
        digests[logical_path] = digest

    project_node = "project:" + project_id
    source_node = "source:expert-robot:" + args.source_commit[:16]
    cad_node = registration["cad_node_id"]
    mesh_artifact_node = registration["artifact_node_id"]
    netlist_digest = digests["electrical/merlin_netlist.json"]
    result_digest = digests["simulation/ngspice-result.json"]
    netlist_node = "electrical:netlist:" + netlist_digest[:16]
    simulation_node = "simulation:ngspice:" + result_digest[:16]

    graph.add_node(GraphNode(
        project_node, "project", "Merlin Engineering Smoke",
        {
            "project_id": project_id,
            "source_repository": "Mannyspiro/expert-robot",
            "source_commit": args.source_commit,
            "source_workflow_run_id": args.run_id,
            "source_artifact_id": args.artifact_id,
            "authority": "qualification-only",
            "promotion_authority": False,
        }, "unreviewed_execution_evidence", source_uri,
    ))
    graph.add_node(GraphNode(
        source_node, "source", "Expert Robot source commit " + args.source_commit[:12],
        {
            "repository": "Mannyspiro/expert-robot",
            "commit": args.source_commit,
            "workflow_run_id": args.run_id,
            "artifact_id": args.artifact_id,
            "artifact_sha256": args.artifact_sha256,
            "workflow": "Merlin Engineering Integration",
        }, "unreviewed_execution_evidence", source_uri,
    ))

    cad_payload = dict(source_cad.payload)
    cad_payload.update({
        "project_id": project_id,
        "artifact_path": "cad/freecad-import-smoke.json",
        "artifact_sha256": digests["cad/freecad-import-smoke.json"],
        "format": "freecad-step-mesh",
        "source_commit": args.source_commit,
        "source_run_id": args.run_id,
    })
    graph.add_node(GraphNode(
        cad_node, "freecad_assembly", source_cad.label, cad_payload,
        "unreviewed_execution_evidence", source_uri,
    ))
    mesh_payload = dict(source_mesh_artifact.payload)
    mesh_payload.update({
        "project_id": project_id,
        "logical_path": "cad/freecad-import-smoke.json",
        "sha256": digests["cad/freecad-import-smoke.json"],
        "size_bytes": len(mesh_path.read_bytes()),
    })
    graph.add_node(GraphNode(
        mesh_artifact_node, "artifact", "FreeCAD imported mesh",
        mesh_payload, "unreviewed_execution_evidence", source_uri,
    ))

    parts = netlist_data.get("parts", [])
    components = [
        {
            "id": part.get("ref", "P" + str(index + 1)),
            "ref": part.get("ref", "P" + str(index + 1)),
            "name": part.get("name", part.get("ref", "Part")),
            "x": 110 + (index % 4) * 125,
            "y": 85 + (index // 4) * 100,
            "pins": [pin.get("number") for pin in part.get("pins", [])],
        }
        for index, part in enumerate(parts)
    ]
    nets = [
        {
            "name": net.get("name", "net"),
            "endpoints": list(net.get("endpoints", [])),
            "voltage_v": net.get("nominal_voltage_v"),
            "net_class": net.get("net_class"),
        }
        for net in netlist_data.get("nets", [])
    ]
    graph.add_node(GraphNode(
        netlist_node, "electrical_net", "Resistor-divider wiring",
        {
            "project_id": project_id,
            "artifact_path": "electrical/merlin_netlist.json",
            "netlist": {
                "components": components,
                "nets": nets,
                "engine": "ngspice",
                "status": "PASS",
                "analysis_result": {
                    "engine": "ngspice",
                    "status": "PASS",
                    "measurements": [{
                        "node": "MID",
                        "expected_voltage_v": expected,
                        "measured_voltage_v": measured,
                        "units": "V",
                    }],
                },
            },
            "source_commit": args.source_commit,
            "source_run_id": args.run_id,
        }, "unreviewed_execution_evidence", source_uri,
    ))
    graph.add_node(GraphNode(
        "artifact:" + netlist_digest[:32], "artifact", "Merlin electrical netlist",
        {
            "project_id": project_id,
            "logical_path": "electrical/merlin_netlist.json",
            "sha256": netlist_digest,
            "size_bytes": (root / "merlin_netlist.json").stat().st_size,
        }, "unreviewed_execution_evidence", source_uri,
    ))

    log = str(spice_result.get("log", ""))
    engine = "ngspice 42" if "ngspice-42" in log else "ngspice"
    graph.add_node(GraphNode(
        simulation_node, "simulation_result", "ngspice MID operating-point result",
        {
            "project_id": project_id,
            "artifact_path": "simulation/ngspice-result.json",
            "engine": engine,
            "status": "PASS",
            "series": [{
                "name": "MID operating-point voltage (V)",
                "points": [{"x": 0, "y": measured}],
            }],
            "metrics": {
                "analysis": "operating_point",
                "expected_mid_voltage_v": expected,
                "measured_mid_voltage_v": measured,
                "returncode": int(spice_result.get("returncode", -1)),
                "wall_seconds": float(spice_result.get("wall_seconds", 0.0)),
            },
            "source_commit": args.source_commit,
            "source_run_id": args.run_id,
        }, "unreviewed_execution_evidence", source_uri,
    ))
    graph.add_node(GraphNode(
        "artifact:" + result_digest[:32], "artifact", "ngspice execution result",
        {
            "project_id": project_id,
            "logical_path": "simulation/ngspice-result.json",
            "sha256": result_digest,
            "size_bytes": result_path.stat().st_size,
        }, "unreviewed_execution_evidence", source_uri,
    ))

    for logical_path, digest in digests.items():
        if logical_path in {
            "cad/freecad-import-smoke.json",
            "electrical/merlin_netlist.json",
            "simulation/ngspice-result.json",
        }:
            continue
        node_id = "artifact:" + digest[:32]
        graph.add_node(GraphNode(
            node_id, "artifact", logical_path,
            {
                "project_id": project_id,
                "logical_path": logical_path,
                "sha256": digest,
                "size_bytes": (root / next(
                    source.name for lp, source, _media in logical_files if lp == logical_path
                )).stat().st_size,
            }, "unreviewed_execution_evidence", source_uri,
        ))

    graph.add_edge(GraphEdge(source_node, "produces", project_node, {"run_id": args.run_id}))
    graph.add_edge(GraphEdge(project_node, "contains", cad_node, {}))
    graph.add_edge(GraphEdge(project_node, "contains", netlist_node, {}))
    graph.add_edge(GraphEdge(project_node, "contains", simulation_node, {}))
    graph.add_edge(GraphEdge(cad_node, "produces", mesh_artifact_node, {}))
    graph.add_edge(GraphEdge(netlist_node, "uses", "artifact:" + netlist_digest[:32], {}))
    graph.add_edge(GraphEdge(simulation_node, "produces", "artifact:" + result_digest[:32], {}))
    graph.add_edge(GraphEdge(simulation_node, "uses", "artifact:" + netlist_digest[:32], {}))

    outbox = MerlinEventOutbox(data_dir / "event-outbox.sqlite3")
    common = {
        "run_id": f"expert-robot-{args.run_id}",
        "task_id": "merlin-engineering-smoke",
        "evidence_refs": ["sha256:" + manifest["freecad_mesh_sha256"],
                          "sha256:" + manifest["ngspice_result_sha256"]],
    }
    events = [
        normalize_event({
            **common, "source": "runtime", "kind": "artifact.registered",
            "payload": {"summary": "Imported and hash-checked FreeCAD assembly, STEP and geometry artifacts."},
        }),
        normalize_event({
            **common, "source": "simulation", "kind": "experiment.completed",
            "payload": {"summary": "ngspice operating-point run returned MID = 2.500000 V.",
                        "status": "PASS", "analysis": "operating_point"},
        }),
        normalize_event({
            **common, "source": "runtime", "kind": "task.completed",
            "payload": {"summary": "Imported reproducible FreeCAD + ngspice evidence; independent CACE signer not asserted.",
                        "status": "completed"},
        }),
    ]
    for event in events:
        outbox.enqueue("merlin-import:" + event["event_id"], "merlin.telemetry." + event["kind"], event)

    snapshot = graph.export_snapshot()
    result = {
        "schema": "merlin-engineering-evidence-import/1",
        "status": "pass",
        "project_id": project_id,
        "source_commit": args.source_commit,
        "source_workflow_run_id": args.run_id,
        "source_artifact_id": args.artifact_id,
        "source_artifact_sha256": args.artifact_sha256,
        "artifact_count": len(digests),
        "artifact_digests": digests,
        "graph_node_count": len(snapshot["nodes"]),
        "graph_edge_count": len(snapshot["edges"]),
        "graph_snapshot_sha256": snapshot["snapshot_sha256"],
        "evidence_class": "unreviewed_execution_evidence",
        "independent_cace_verification": False,
        "promotion_authority": False,
        "outbox_events_enqueued": len(events),
    }
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
