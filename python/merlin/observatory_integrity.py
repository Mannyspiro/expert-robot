"""Read-only integrity verification for Merlin's persisted evidence store."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def verify_theorem_dag(dag: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if dag.get("schema") != "merlin-theorem-dependency-dag-v1":
        return ["unsupported theorem DAG schema"]
    supplied = dag.get("dag_sha256")
    payload = {key: value for key, value in dag.items() if key != "dag_sha256"}
    if not _digest(supplied) or sha256_text(canonical_json(payload)) != supplied:
        errors.append("theorem DAG digest mismatch")
    nodes = dag.get("nodes")
    edges = dag.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return errors + ["theorem DAG nodes and edges must be lists"]
    ids = [node.get("id") for node in nodes if isinstance(node, dict)]
    if len(ids) != len(nodes) or any(not isinstance(item, str) or not item for item in ids):
        errors.append("theorem DAG contains malformed nodes")
        return errors
    if len(ids) != len(set(ids)):
        errors.append("theorem DAG contains duplicate node IDs")
    known = set(ids)
    expected_edges = set()
    for node in nodes:
        deps = node.get("dependencies", [])
        if not isinstance(deps, list):
            errors.append(f"invalid dependencies for {node['id']}")
            continue
        for dep in deps:
            if dep not in known:
                errors.append(f"dangling theorem dependency: {node['id']} -> {dep}")
            expected_edges.add((node["id"], dep))
    actual_edges = set()
    for edge in edges:
        if not isinstance(edge, dict) or not isinstance(edge.get("theorem"), str) or not isinstance(edge.get("depends_on"), str):
            errors.append("malformed theorem DAG edge")
            continue
        actual_edges.add((edge["theorem"], edge["depends_on"]))
    if actual_edges != expected_edges:
        errors.append("theorem DAG edge list does not match node dependencies")
    if dag.get("node_count") != len(nodes) or dag.get("edge_count") != len(edges):
        errors.append("theorem DAG node/edge counts do not match contents")
    order = dag.get("topological_order_dependencies_first")
    if not isinstance(order, list) or len(order) != len(ids) or set(order) != known:
        errors.append("theorem DAG topological order is not a permutation of node IDs")
    elif not errors:
        positions = {name: index for index, name in enumerate(order)}
        for theorem, dependency in expected_edges:
            if positions[dependency] >= positions[theorem]:
                errors.append(f"invalid topological order for {theorem} depends on {dependency}")
    return errors


def verify_database(database_path: str | Path, theorem_dag: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify all persisted evidence tables without mutating the database.

    Engineering IR revision hashes are external references: this database does
    not store canonical project artifacts, so their preimages cannot be checked here.
    """
    errors: list[str] = []
    counts = {"observations": 0, "benchmark_receipts": 0, "cross_domain_links": 0}
    db_uri = Path(database_path).resolve().as_uri() + "?mode=ro"
    try:
        db = sqlite3.connect(db_uri, uri=True)
    except sqlite3.Error as exc:
        return {"ok": False, "counts": counts, "errors": [f"database open failed: {exc}"],
                "engineering_revision_hashes": "external references; preimages not stored"}
    try:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"observations", "benchmark_receipts", "cross_domain_links"}
        if not required.issubset(tables):
            errors.append("missing evidence tables: " + ", ".join(sorted(required - tables)))
            return {"ok": False, "counts": counts, "errors": errors,
                    "engineering_revision_hashes": "external references; preimages not stored"}

        previous = "0" * 64
        rows = db.execute("SELECT payload,payload_sha256,previous_sha256,chain_sha256 FROM observations ORDER BY seq").fetchall()
        counts["observations"] = len(rows)
        for index, (payload, payload_hash, stored_previous, stored_chain) in enumerate(rows, 1):
            actual_payload = sha256_text(payload)
            actual_chain = sha256_text(previous + actual_payload)
            if actual_payload != payload_hash:
                errors.append(f"observation {index}: payload digest mismatch")
            if stored_previous != previous:
                errors.append(f"observation {index}: previous-chain digest mismatch")
            if actual_chain != stored_chain:
                errors.append(f"observation {index}: chain digest mismatch")
            previous = stored_chain

        receipt_hashes: set[str] = set()
        receipt_rows = db.execute("SELECT receipt_sha256,source_commit,payload FROM benchmark_receipts").fetchall()
        counts["benchmark_receipts"] = len(receipt_rows)
        for stored_hash, stored_commit, raw in receipt_rows:
            try:
                receipt = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                errors.append(f"benchmark receipt {stored_hash}: invalid JSON")
                continue
            supplied = receipt.get("receipt_sha256") if isinstance(receipt, dict) else None
            payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"} if isinstance(receipt, dict) else {}
            actual = sha256_text(canonical_json(payload))
            if canonical_json(receipt) != raw:
                errors.append(f"benchmark receipt {stored_hash}: payload is not canonical JSON")
            if supplied != stored_hash or actual != stored_hash:
                errors.append(f"benchmark receipt {stored_hash}: digest mismatch")
            if receipt.get("source_commit") != stored_commit or not re.fullmatch(r"[0-9a-f]{40}", str(stored_commit)):
                errors.append(f"benchmark receipt {stored_hash}: source commit mismatch")
            if receipt.get("schema") != "merlin-cross-domain-benchmark-receipt-v1" or not isinstance(receipt.get("domains"), dict):
                errors.append(f"benchmark receipt {stored_hash}: invalid schema/domains")
            else:
                receipt_hashes.add(stored_hash)

        link_rows = db.execute("SELECT link_id,payload,payload_sha256 FROM cross_domain_links").fetchall()
        counts["cross_domain_links"] = len(link_rows)
        for link_id, raw, stored_hash in link_rows:
            try:
                link = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                errors.append(f"cross-domain link {link_id}: invalid JSON")
                continue
            actual = sha256_text(raw)
            if canonical_json(link) != raw:
                errors.append(f"cross-domain link {link_id}: payload is not canonical JSON")
            if actual != stored_hash or actual != link_id:
                errors.append(f"cross-domain link {link_id}: digest mismatch")
            if not isinstance(link, dict):
                errors.append(f"cross-domain link {link_id}: payload must be an object")
                continue
            for field in ("theorem_id", "object_view_id", "engineering_project_id", "relation"):
                if not isinstance(link.get(field), str) or not link[field].strip():
                    errors.append(f"cross-domain link {link_id}: invalid {field}")
            for field in ("engineering_revision_sha256", "evidence_receipt_sha256"):
                if not _digest(link.get(field)):
                    errors.append(f"cross-domain link {link_id}: invalid {field}")
            if link.get("evidence_receipt_sha256") not in receipt_hashes:
                errors.append(f"cross-domain link {link_id}: dangling benchmark receipt reference")

        if theorem_dag is not None:
            errors.extend(verify_theorem_dag(theorem_dag))
    except sqlite3.Error as exc:
        errors.append(f"database verification error: {exc}")
    finally:
        db.close()
    return {
        "ok": not errors,
        "counts": counts,
        "errors": errors,
        "engineering_revision_hashes": "external references; preimages not stored",
        "theorem_dag_checked": theorem_dag is not None,
    }
