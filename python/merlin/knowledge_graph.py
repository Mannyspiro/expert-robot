"""Typed, provenance-aware knowledge graph for Merlin.

The graph records assertions and relationships; it does not infer that a claim
is true merely because it is present or linked to evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")
NODE_TYPES = frozenset({
    "project", "module", "artifact", "source", "claim", "assumption",
    "equation", "theorem", "experiment", "dataset", "model", "simulation",
    "cad_model", "equation_atlas", "proof_receipt", "freecad_model",
    "freecad_assembly", "electrical_net", "simulation_result",
    "artifact_reference", "object_view", "media", "worker", "session", "review",
})
EDGE_TYPES = frozenset({
    "contains", "derived_from", "supports", "contradicts", "depends_on",
    "formalizes", "tests", "produces", "implements", "reviews", "uses",
})

@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: str
    label: str
    payload: dict[str, Any]
    evidence_class: str = "unreviewed"
    source_uri: str | None = None

@dataclass(frozen=True)
class GraphEdge:
    source_id: str
    relation: str
    target_id: str
    payload: dict[str, Any]

class MerlinKnowledgeGraph:
    def __init__(self, database: str | Path):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS graph_nodes(
              node_id TEXT PRIMARY KEY, node_type TEXT NOT NULL, label TEXT NOT NULL,
              payload_json TEXT NOT NULL, evidence_class TEXT NOT NULL,
              source_uri TEXT, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS graph_edges(
              source_id TEXT NOT NULL REFERENCES graph_nodes(node_id),
              relation TEXT NOT NULL, target_id TEXT NOT NULL REFERENCES graph_nodes(node_id),
              payload_json TEXT NOT NULL, created_at REAL NOT NULL,
              PRIMARY KEY(source_id, relation, target_id));
            CREATE INDEX IF NOT EXISTS graph_edges_target ON graph_edges(target_id);
            CREATE INDEX IF NOT EXISTS graph_nodes_type ON graph_nodes(node_type);
            """)

    def _connect(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _validate_id(value: str) -> None:
        if not _ID.fullmatch(value):
            raise ValueError("invalid graph identifier")

    def add_node(self, node: GraphNode) -> str:
        self._validate_id(node.node_id)
        if node.node_type not in NODE_TYPES:
            raise ValueError(f"unsupported node type: {node.node_type}")
        if not node.label.strip() or not node.evidence_class.strip():
            raise ValueError("label and evidence class are required")
        payload = json.dumps(node.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        with self._connect() as db:
            existing = db.execute(
                "SELECT node_type,label,payload_json,evidence_class,source_uri "
                "FROM graph_nodes WHERE node_id=?", (node.node_id,)
            ).fetchone()
            values = (node.node_type, node.label, payload, node.evidence_class, node.source_uri)
            if existing is not None:
                if tuple(existing) != values:
                    raise ValueError("graph node already exists with different content or provenance")
            else:
                db.execute("INSERT INTO graph_nodes VALUES(?,?,?,?,?,?,?)",
                           (node.node_id,node.node_type,node.label,payload,node.evidence_class,
                            node.source_uri,time.time()))
        return hashlib.sha256(payload.encode()).hexdigest()

    def add_edge(self, edge: GraphEdge) -> None:
        self._validate_id(edge.source_id); self._validate_id(edge.target_id)
        if edge.relation not in EDGE_TYPES:
            raise ValueError(f"unsupported relation: {edge.relation}")
        payload = json.dumps(edge.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        with self._connect() as db:
            existing = db.execute(
                "SELECT payload_json FROM graph_edges WHERE source_id=? AND relation=? AND target_id=?",
                (edge.source_id, edge.relation, edge.target_id),
            ).fetchone()
            if existing is not None:
                if existing[0] != payload:
                    raise ValueError("graph edge already exists with different payload")
                return
            db.execute("INSERT INTO graph_edges VALUES(?,?,?,?,?)",
                       (edge.source_id,edge.relation,edge.target_id,payload,time.time()))

    def get_node(self, node_id: str) -> GraphNode | None:
        with self._connect() as db:
            row = db.execute("SELECT node_id,node_type,label,payload_json,evidence_class,source_uri "
                             "FROM graph_nodes WHERE node_id=?", (node_id,)).fetchone()
        return GraphNode(row[0],row[1],row[2],json.loads(row[3]),row[4],row[5]) if row else None

    def neighbors(self, node_id: str, direction: str = "both") -> list[dict[str, Any]]:
        self._validate_id(node_id)
        if direction not in {"in", "out", "both"}:
            raise ValueError("direction must be in, out, or both")
        clauses, args = [], []
        if direction in {"out", "both"}:
            clauses.append("e.source_id=?"); args.append(node_id)
        if direction in {"in", "both"}:
            clauses.append("e.target_id=?"); args.append(node_id)
        sql = """SELECT e.source_id,e.relation,e.target_id,e.payload_json,
                        s.label,t.label FROM graph_edges e
                 JOIN graph_nodes s ON s.node_id=e.source_id
                 JOIN graph_nodes t ON t.node_id=e.target_id
                 WHERE """ + " OR ".join(clauses) + " ORDER BY e.source_id,e.relation,e.target_id"
        with self._connect() as db:
            rows = db.execute(sql, args).fetchall()
        return [{"source_id":r[0],"relation":r[1],"target_id":r[2],
                 "payload":json.loads(r[3]),"source_label":r[4],"target_label":r[5]} for r in rows]

    def export_snapshot(self) -> dict[str, Any]:
        with self._connect() as db:
            nodes = db.execute("SELECT node_id,node_type,label,payload_json,evidence_class,source_uri "
                               "FROM graph_nodes ORDER BY node_id").fetchall()
            edges = db.execute("SELECT source_id,relation,target_id,payload_json FROM graph_edges "
                               "ORDER BY source_id,relation,target_id").fetchall()
        body = {
            "schema_version":"1.0",
            "nodes":[{"node_id":r[0],"node_type":r[1],"label":r[2],
                      "payload":json.loads(r[3]),"evidence_class":r[4],"source_uri":r[5]} for r in nodes],
            "edges":[{"source_id":r[0],"relation":r[1],"target_id":r[2],
                      "payload":json.loads(r[3])} for r in edges],
            "epistemic_notice":"Graph membership and edge labels do not establish truth."
        }
        canonical = json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False)
        return {**body,"snapshot_sha256":hashlib.sha256(canonical.encode()).hexdigest()}
