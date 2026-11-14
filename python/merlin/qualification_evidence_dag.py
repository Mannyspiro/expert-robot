"""Deterministic, read-only qualification evidence DAG projection.

This module validates and hashes supplied evidence projections. It does not
retrieve evidence, verify signatures, qualify capabilities, or grant authority.
Canonical records remain owned by MerlinRegistry, GitHub, CACE, OCI and Lean.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
import time
from pathlib import Path
from collections import defaultdict, deque
from typing import Any, Iterable, Mapping

from .artifact_ref import ArtifactRef


SCHEMA = "merlin-qualification-evidence-dag/1"
AUTHORITY = "read-only-projection"
NODE_TYPES = frozenset({
    "source_commit", "artifact_version", "workflow_run", "cace_attestation",
    "trust_root", "verification_receipt", "oci_execution",
    "protected_orchestrator", "lean_compile",
})
RELATIONS = frozenset({
    "derived_from", "built_by", "attests", "verifies", "executes", "qualifies",
})
STATUSES = frozenset({"qualified", "unqualified", "stale", "revoked", "blocked"})
_STATUS_RANK = {
    "qualified": 0, "unqualified": 1, "blocked": 2, "stale": 3, "revoked": 4,
}
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: Any) -> bytes:
    """Return the single canonical UTF-8 JSON representation used by v1."""
    _validate_json_value(value)
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("value is not canonical JSON data") from exc


def _validate_json_value(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite number at {path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"object key must be a string at {path}")
            _validate_json_value(item, f"{path}.{key}")
        return
    raise ValueError(f"unsupported JSON value at {path}: {type(value).__name__}")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_digest(value: Any, field: str) -> None:
    if not isinstance(value, str) or not _HEX_64.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


def _require_text(identity: Mapping[str, Any], field: str) -> None:
    value = identity.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"identity.{field} must be a non-empty string")


def _require_positive_int(identity: Mapping[str, Any], field: str) -> None:
    value = identity.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"identity.{field} must be a positive integer")


def _validate_identity(node_type: str, identity: Mapping[str, Any]) -> None:
    """Validate the stable minimum identity for each evidence node type."""
    if not isinstance(node_type, str) or node_type not in NODE_TYPES:
        raise ValueError("unknown evidence node type")
    if not isinstance(identity, Mapping) or not identity:
        raise ValueError("node identity must be a non-empty object")
    _validate_json_value(dict(identity), "$.identity")

    if node_type == "source_commit":
        _require_text(identity, "repository")
        if not isinstance(identity.get("commit"), str) or not _HEX_40.fullmatch(identity["commit"]):
            raise ValueError("identity.commit must be a full lowercase Git commit SHA")
    elif node_type == "artifact_version":
        _require_text(identity, "project_id")
        _require_text(identity, "logical_path")
        path = identity["logical_path"]
        if (path.startswith("/") or "\\" in path or "\x00" in path
                or any(part in {"", ".", ".."} for part in path.split("/"))):
            raise ValueError("identity.logical_path must be normalized and traversal-free")
        _require_positive_int(identity, "version")
        _require_digest(identity.get("digest"), "identity.digest")
        size = identity.get("size_bytes")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("identity.size_bytes must be a non-negative integer")
    elif node_type == "workflow_run":
        _require_text(identity, "repository")
        _require_text(identity, "workflow_id")
        _require_positive_int(identity, "run_id")
        _require_positive_int(identity, "attempt")
        if not isinstance(identity.get("head_sha"), str) or not _HEX_40.fullmatch(identity["head_sha"]):
            raise ValueError("identity.head_sha must be a full lowercase Git commit SHA")
        _require_text(identity, "conclusion")
        _require_digest(identity.get("artifact_digest"), "identity.artifact_digest")
    elif node_type == "cace_attestation":
        _require_digest(identity.get("statement_sha256"), "identity.statement_sha256")
        for field in ("verifier_id", "key_id", "purpose", "source_repo", "artifact_id",
                      "artifact_kind", "artifact_schema"):
            _require_text(identity, field)
        if not isinstance(identity.get("source_commit"), str) or not _HEX_40.fullmatch(identity["source_commit"]):
            raise ValueError("identity.source_commit must be a full lowercase Git commit SHA")
        if not isinstance(identity.get("artifact_ref"), dict):
            raise ValueError("identity.artifact_ref must be an object")
        ArtifactRef.from_mapping(identity["artifact_ref"])
    elif node_type == "trust_root":
        for field in ("authority_id", "version"):
            _require_text(identity, field)
        _require_digest(identity.get("root_sha256"), "identity.root_sha256")
    elif node_type == "verification_receipt":
        _require_digest(identity.get("receipt_sha256"), "identity.receipt_sha256")
        _require_text(identity, "verifier_id")
        if not isinstance(identity.get("artifact_ref"), dict):
            raise ValueError("identity.artifact_ref must be an object")
        ArtifactRef.from_mapping(identity["artifact_ref"])
    elif node_type == "oci_execution":
        for field in ("execution_id", "runner_profile"):
            _require_text(identity, field)
        if not isinstance(identity.get("task_ref"), dict):
            raise ValueError("identity.task_ref must be an ArtifactRef object")
        ArtifactRef.from_mapping(identity["task_ref"])
        if not isinstance(identity.get("input_refs"), list):
            raise ValueError("identity.input_refs must be an array")
        for artifact_ref in identity["input_refs"]:
            if not isinstance(artifact_ref, dict):
                raise ValueError("each identity.input_refs item must be an ArtifactRef object")
            ArtifactRef.from_mapping(artifact_ref)
    elif node_type == "protected_orchestrator":
        _require_text(identity, "repository")
        _require_text(identity, "workflow_id")
        _require_positive_int(identity, "run_id")
        _require_positive_int(identity, "attempt")
        _require_text(identity, "execution_id")
        _require_digest(identity.get("execution_receipt_sha256"), "identity.execution_receipt_sha256")
    elif node_type == "lean_compile":
        for field in ("module", "lean_version", "mathlib_revision", "result"):
            _require_text(identity, field)
        _require_digest(identity.get("source_sha256"), "identity.source_sha256")


def node_id_for(node_type: str, identity: Mapping[str, Any]) -> str:
    """Derive the stable node ID from the complete type and identity."""
    _validate_identity(node_type, identity)
    payload = {"node_type": node_type, "identity": dict(identity)}
    return "sha256:" + _sha256(canonical_json(payload))


def make_node(
    node_type: str, identity: Mapping[str, Any], record_sha256: str,
    evidence_class: str, status: str,
) -> dict[str, Any]:
    """Build a fully identified node; record_sha256 must come from its verifier."""
    _require_digest(record_sha256, "record_sha256")
    if not isinstance(evidence_class, str) or not evidence_class or len(evidence_class) > 128:
        raise ValueError("evidence_class must be a non-empty string of at most 128 characters")
    if not isinstance(status, str) or status not in STATUSES:
        raise ValueError("unknown evidence status")
    return {
        "node_id": node_id_for(node_type, identity),
        "node_type": node_type,
        "identity": dict(identity),
        "record_sha256": record_sha256,
        "evidence_class": evidence_class,
        "status": status,
    }


def _validate_node(node: Any) -> dict[str, Any]:
    required = {"node_id", "node_type", "identity", "record_sha256", "evidence_class", "status"}
    if not isinstance(node, dict) or set(node) != required:
        raise ValueError("node must contain exactly the v1 node fields")
    expected_id = node_id_for(node["node_type"], node["identity"])
    if node["node_id"] != expected_id:
        raise ValueError("node_id does not match the complete node identity")
    _require_digest(node["record_sha256"], "record_sha256")
    if not isinstance(node["evidence_class"], str) or not node["evidence_class"] or len(node["evidence_class"]) > 128:
        raise ValueError("evidence_class must be a non-empty string of at most 128 characters")
    if not isinstance(node["status"], str) or node["status"] not in STATUSES:
        raise ValueError("unknown evidence status")
    return dict(node)


def _validate_edge(edge: Any) -> dict[str, str]:
    required = {"dependent_node_id", "prerequisite_node_id", "relation"}
    if not isinstance(edge, dict) or set(edge) != required:
        raise ValueError("edge must contain exactly the v1 edge fields")
    for field in ("dependent_node_id", "prerequisite_node_id"):
        value = edge[field]
        if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
            raise ValueError(f"{field} must be a node SHA-256 identity")
    if not isinstance(edge["relation"], str) or edge["relation"] not in RELATIONS:
        raise ValueError("unknown evidence edge relation")
    if edge["dependent_node_id"] == edge["prerequisite_node_id"]:
        raise ValueError("self-dependency is not allowed")
    return dict(edge)


def _topological_order(nodes: list[dict[str, Any]], edges: list[dict[str, str]]) -> list[str]:
    """Return prerequisite-first order; reject every directed cycle."""
    node_ids = {node["node_id"] for node in nodes}
    indegree = {node_id: 0 for node_id in node_ids}
    dependents: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        dependent = edge["dependent_node_id"]
        prerequisite = edge["prerequisite_node_id"]
        if dependent not in node_ids or prerequisite not in node_ids:
            raise ValueError("edge references an unknown node")
        if dependent in dependents[prerequisite]:
            # Distinct relation labels for the same pair are permitted; the
            # adjacency is unique for cycle detection and status propagation.
            continue
        dependents[prerequisite].add(dependent)
        indegree[dependent] += 1

    ready = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    ordered: list[str] = []
    while ready:
        prerequisite = ready.popleft()
        ordered.append(prerequisite)
        for dependent in sorted(dependents[prerequisite]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    if len(ordered) != len(node_ids):
        raise ValueError("evidence dependency graph contains a cycle")
    return ordered


def build_snapshot(
    nodes: Iterable[Mapping[str, Any]], edges: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate, deterministically sort, and hash a v1 evidence snapshot."""
    validated_nodes = [_validate_node(dict(node)) for node in nodes]
    validated_edges = [_validate_edge(dict(edge)) for edge in edges]
    node_ids = [node["node_id"] for node in validated_nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("duplicate evidence node identity")
    edge_keys = [
        (edge["dependent_node_id"], edge["prerequisite_node_id"], edge["relation"])
        for edge in validated_edges
    ]
    if len(edge_keys) != len(set(edge_keys)):
        raise ValueError("duplicate evidence edge")
    _topological_order(validated_nodes, validated_edges)
    validated_nodes.sort(key=lambda node: node["node_id"])
    validated_edges.sort(key=lambda edge: (
        edge["dependent_node_id"], edge["prerequisite_node_id"], edge["relation"],
    ))
    snapshot = {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "nodes": validated_nodes,
        "edges": validated_edges,
    }
    snapshot["snapshot_sha256"] = _sha256(canonical_json(snapshot))
    return snapshot


def validate_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Revalidate a snapshot envelope and its digest; return canonical form."""
    if not isinstance(snapshot, Mapping):
        raise ValueError("snapshot must be an object")
    if set(snapshot) != {"schema", "authority", "nodes", "edges", "snapshot_sha256"}:
        raise ValueError("snapshot must contain exactly the v1 envelope fields")
    if snapshot["schema"] != SCHEMA or snapshot["authority"] != AUTHORITY:
        raise ValueError("unsupported qualification evidence snapshot")
    if not isinstance(snapshot["nodes"], list) or not isinstance(snapshot["edges"], list):
        raise ValueError("snapshot nodes and edges must be arrays")
    rebuilt = build_snapshot(snapshot["nodes"], snapshot["edges"])
    _require_digest(snapshot["snapshot_sha256"], "snapshot_sha256")
    if rebuilt["snapshot_sha256"] != snapshot["snapshot_sha256"]:
        raise ValueError("snapshot SHA-256 does not match canonical contents")
    return rebuilt


def prerequisite_first_order(snapshot: Mapping[str, Any]) -> list[str]:
    validated = validate_snapshot(snapshot)
    return _topological_order(validated["nodes"], validated["edges"])


def transitive_dependents(
    snapshot: Mapping[str, Any], changed_node_ids: Iterable[str],
) -> list[str]:
    """Return only downstream dependents invalidated by changed prerequisites."""
    validated = validate_snapshot(snapshot)
    known = {node["node_id"] for node in validated["nodes"]}
    seeds = set(changed_node_ids)
    if not seeds or not seeds.issubset(known):
        raise ValueError("changed node IDs must be a non-empty subset of the snapshot")
    reverse: dict[str, set[str]] = defaultdict(set)
    for edge in validated["edges"]:
        reverse[edge["prerequisite_node_id"]].add(edge["dependent_node_id"])
    invalidated: set[str] = set()
    pending = deque(sorted(seeds))
    while pending:
        prerequisite = pending.popleft()
        for dependent in sorted(reverse[prerequisite]):
            if dependent not in seeds and dependent not in invalidated:
                invalidated.add(dependent)
                pending.append(dependent)
    return sorted(invalidated)


def derive_statuses(snapshot: Mapping[str, Any]) -> dict[str, str]:
    """Propagate prerequisite failures without allowing graph connectivity to qualify."""
    validated = validate_snapshot(snapshot)
    nodes = {node["node_id"]: node for node in validated["nodes"]}
    prerequisites: dict[str, set[str]] = defaultdict(set)
    for edge in validated["edges"]:
        prerequisites[edge["dependent_node_id"]].add(edge["prerequisite_node_id"])
    statuses: dict[str, str] = {}
    for node_id in _topological_order(validated["nodes"], validated["edges"]):
        own = nodes[node_id]["status"]
        dependency_statuses = [statuses[item] for item in prerequisites[node_id]]
        statuses[node_id] = max([own, *dependency_statuses], key=_STATUS_RANK.__getitem__)
    return statuses


class SnapshotHistory:
    """Append-only snapshot history stored inside an existing MerlinRegistry DB.

    This is a persistence adapter for the DAG projection, not a second registry.
    The supplied database must already contain MerlinRegistry's project and
    artifact-version tables.
    """

    def __init__(self, registry_db_path: str | Path):
        self.db_path = Path(registry_db_path)
        if not self.db_path.is_file():
            raise FileNotFoundError("an existing MerlinRegistry database is required")
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path), timeout=30)
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def _initialize(self) -> None:
        db = self._connect()
        try:
            required = {
                row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if not {"projects", "artifact_versions"}.issubset(required):
                raise ValueError("snapshot history must share the canonical MerlinRegistry database")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS qualification_evidence_snapshots(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_sha256 TEXT NOT NULL UNIQUE,
                    snapshot_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS qualification_evidence_snapshots_no_update
                  BEFORE UPDATE ON qualification_evidence_snapshots
                  BEGIN SELECT RAISE(ABORT, 'qualification evidence snapshots are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS qualification_evidence_snapshots_no_delete
                  BEFORE DELETE ON qualification_evidence_snapshots
                  BEGIN SELECT RAISE(ABORT, 'qualification evidence snapshots are append-only'); END;
            """)
        finally:
            db.close()

    def append(self, snapshot: Mapping[str, Any]) -> int:
        """Atomically append a validated snapshot; exact replay is idempotent."""
        validated = validate_snapshot(snapshot)
        snapshot_sha256 = validated["snapshot_sha256"]
        snapshot_json = canonical_json(validated).decode("utf-8")
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT sequence, snapshot_json FROM qualification_evidence_snapshots "
                "WHERE snapshot_sha256=?",
                (snapshot_sha256,),
            ).fetchone()
            if existing is not None:
                if existing[1] != snapshot_json:
                    raise RuntimeError("snapshot digest collision or stored-byte substitution")
                db.commit()
                return int(existing[0])
            cursor = db.execute(
                "INSERT INTO qualification_evidence_snapshots "
                "(snapshot_sha256, snapshot_json, created_at) VALUES (?, ?, ?)",
                (snapshot_sha256, snapshot_json, time.time()),
            )
            sequence = int(cursor.lastrowid)
            db.commit()
            return sequence
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, snapshot_sha256: str) -> dict[str, Any]:
        """Load and revalidate one immutable snapshot by its digest."""
        _require_digest(snapshot_sha256, "snapshot_sha256")
        db = self._connect()
        try:
            row = db.execute(
                "SELECT snapshot_json FROM qualification_evidence_snapshots "
                "WHERE snapshot_sha256=?",
                (snapshot_sha256,),
            ).fetchone()
        finally:
            db.close()
        if row is None:
            raise KeyError(snapshot_sha256)
        try:
            decoded = json.loads(row[0])
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("stored qualification snapshot is not valid JSON") from exc
        validated = validate_snapshot(decoded)
        if canonical_json(validated).decode("utf-8") != row[0]:
            raise RuntimeError("stored qualification snapshot is not canonical")
        if validated["snapshot_sha256"] != snapshot_sha256:
            raise RuntimeError("stored qualification snapshot digest mismatch")
        return validated

    def get_by_sequence(self, sequence: int) -> dict[str, Any]:
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError("snapshot sequence must be a positive integer")
        db = self._connect()
        try:
            row = db.execute(
                "SELECT snapshot_sha256 FROM qualification_evidence_snapshots WHERE sequence=?",
                (sequence,),
            ).fetchone()
        finally:
            db.close()
        if row is None:
            raise KeyError(sequence)
        return self.get(row[0])

    @staticmethod
    def verify_backup(backup_path: str | Path) -> dict[str, Any]:
        """Verify Registry schema and every stored DAG snapshot in a backup."""
        path = Path(backup_path)
        if not path.is_file() or path.is_symlink():
            raise ValueError("backup must be a regular, non-symlink file")
        db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        try:
            tables = {
                row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            required = {
                "projects", "artifact_versions", "qualification_evidence_snapshots",
            }
            if not required.issubset(tables):
                raise ValueError("backup is missing canonical MerlinRegistry or evidence history tables")
            trigger_rows = {
                row[0]: row[1] for row in db.execute(
                    "SELECT name, sql FROM sqlite_master WHERE type='trigger'"
                )
            }
            expected_triggers = {
                "qualification_evidence_snapshots_no_update": (
                    "CREATE TRIGGER qualification_evidence_snapshots_no_update "
                    "BEFORE UPDATE ON qualification_evidence_snapshots "
                    "BEGIN SELECT RAISE(ABORT, 'qualification evidence snapshots are append-only'); END"
                ),
                "qualification_evidence_snapshots_no_delete": (
                    "CREATE TRIGGER qualification_evidence_snapshots_no_delete "
                    "BEFORE DELETE ON qualification_evidence_snapshots "
                    "BEGIN SELECT RAISE(ABORT, 'qualification evidence snapshots are append-only'); END"
                ),
            }
            for name, expected_sql in expected_triggers.items():
                actual_sql = trigger_rows.get(name)
                if not isinstance(actual_sql, str):
                    raise ValueError("backup is missing append-only evidence history guards")
                normalize_sql = lambda value: re.sub(r"\\s+", " ", value).strip().rstrip(";").casefold()
                if normalize_sql(actual_sql) != normalize_sql(expected_sql):
                    raise ValueError("backup append-only evidence trigger definition mismatch")
            rows = db.execute(
                "SELECT sequence, snapshot_sha256, snapshot_json "
                "FROM qualification_evidence_snapshots ORDER BY sequence"
            ).fetchall()
            verified = 0
            for sequence, digest, payload in rows:
                try:
                    snapshot = validate_snapshot(json.loads(payload))
                except (TypeError, json.JSONDecodeError, ValueError) as exc:
                    raise ValueError(
                        f"backup contains invalid snapshot at sequence {sequence}"
                    ) from exc
                if snapshot["snapshot_sha256"] != digest:
                    raise ValueError(
                        f"backup snapshot digest mismatch at sequence {sequence}"
                    )
                if canonical_json(snapshot).decode("utf-8") != payload:
                    raise ValueError(
                        f"backup snapshot is not canonical at sequence {sequence}"
                    )
                verified += 1
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError("SQLite backup integrity check failed")
        finally:
            db.close()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return {"sha256": digest, "snapshot_count": verified, "integrity": "ok"}

    def backup_to(self, destination: str | Path) -> dict[str, Any]:
        """Create and verify a consistent, non-overwriting SQLite backup.

        The temporary file is created in the destination directory so the final
        hard-link publication is atomic and cannot replace an existing backup.
        """
        target = Path(destination)
        parent = target.parent
        if not parent.is_dir():
            raise FileNotFoundError("backup destination directory must already exist")
        if target.exists() or target.is_symlink():
            raise FileExistsError("backup destination already exists")
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=str(parent),
        )
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            source = self._connect()
            destination_db = sqlite3.connect(str(temporary), timeout=30)
            try:
                source.backup(destination_db)
                destination_db.commit()
            finally:
                destination_db.close()
                source.close()
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
            verified = self.verify_backup(temporary)
            os.link(temporary, target)
            temporary.unlink()
            directory_fd = os.open(str(parent), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return {"path": str(target), **verified}
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def list_history(self, limit: int = 100) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10000:
            raise ValueError("history limit must be an integer from 1 to 10000")
        db = self._connect()
        try:
            rows = db.execute(
                "SELECT sequence, snapshot_sha256, created_at "
                "FROM qualification_evidence_snapshots ORDER BY sequence LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            db.close()
        return [
            {"sequence": int(row[0]), "snapshot_sha256": row[1], "created_at": row[2]}
            for row in rows
        ]
