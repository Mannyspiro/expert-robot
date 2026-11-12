"""Append-only bootstrap for Merlin's canonical research and learning graph.

The bootstrap records source snapshots and versioned graph nodes. Re-running
against the same commit is idempotent; bootstrapping a newer commit adds a new
version and preserves all prior artifacts and graph history.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .event_outbox import MerlinEventOutbox
from .hypothesis_ledger import HypothesisLedger
from .knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph
from .project_registry import MerlinRegistry


DEFAULT_REPOSITORY = "Mannyspiro/expert-robot"
CATALOG_RELATIVE_PATH = Path("docs/research/merlin-mathematical-idea-catalog.v1.json")
BACKLOG_RELATIVE_PATH = Path("docs/merlin/MERLIN_MATH_LESSON_BACKLOG_V1.json")
_SOURCE_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _read_json(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    if not path.is_file() or path.is_symlink():
        raise ValueError(label + " must be a regular file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(label + " must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(label + " root must be an object")
    return raw, value


def _required_text(value: Any, label: str, maximum: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(label + " must be non-empty bounded text")
    return value.strip()


def bootstrap_merlin(
    *,
    root: str | Path,
    source_commit: str,
    repository: str = DEFAULT_REPOSITORY,
    project_id: str = "merlin",
    project_name: str = "Merlin",
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    """Initialize persistent Merlin stores and seed versioned canonical graph data.

    No files are deleted or replaced. Each source revision receives immutable
    artifact paths and versioned graph node IDs. This operation records catalog
    facts and lesson blueprints only; it does not mark claims verified, publish
    lessons, create approvals, or grant promotion/execution authority.
    """
    if not isinstance(source_commit, str) or not _SOURCE_COMMIT.fullmatch(source_commit):
        raise ValueError("source_commit must be a lowercase 40-character Git SHA")
    repository = _required_text(repository, "repository", 200)
    if repository.count("/") != 1:
        raise ValueError("repository must be owner/name")
    project_id = _required_text(project_id, "project_id", 120)
    project_name = _required_text(project_name, "project_name", 200)
    if not isinstance(root, (str, Path)) or not str(root).strip():
        raise ValueError("persistent data root is required")

    repo_root = (
        Path(repository_root).resolve()
        if repository_root is not None
        else Path(__file__).resolve().parents[2]
    )
    root_path = Path(root).expanduser().resolve()
    root_path.mkdir(parents=True, exist_ok=True)
    if not root_path.is_dir():
        raise ValueError("persistent data root must be a directory")

    catalog_raw, catalog = _read_json(repo_root / CATALOG_RELATIVE_PATH, "idea catalog")
    backlog_raw, backlog = _read_json(repo_root / BACKLOG_RELATIVE_PATH, "lesson backlog")
    ideas = catalog.get("ideas")
    blueprints = backlog.get("blueprints")
    if not isinstance(ideas, list) or not ideas:
        raise ValueError("idea catalog must contain a non-empty ideas list")
    if not isinstance(blueprints, list):
        raise ValueError("lesson backlog must contain a blueprints list")

    idea_by_id: dict[str, dict[str, Any]] = {}
    for idea in ideas:
        if not isinstance(idea, dict):
            raise ValueError("idea catalog entries must be objects")
        idea_id = _required_text(idea.get("id"), "idea.id", 160)
        _required_text(idea.get("title"), idea_id + ".title", 500)
        _required_text(idea.get("kind"), idea_id + ".kind", 120)
        _required_text(idea.get("status"), idea_id + ".status", 120)
        if idea_id in idea_by_id:
            raise ValueError("idea catalog IDs must be unique")
        learning = idea.get("learning")
        if learning is not None and not isinstance(learning, dict):
            raise ValueError(idea_id + ".learning must be an object when present")
        learning = learning or {}
        prerequisites = learning.get("prerequisites", [])
        dimensions = learning.get("dimensions", [])
        if not isinstance(prerequisites, list) or any(
            not isinstance(item, str) or not item.strip() for item in prerequisites
        ) or len(set(prerequisites)) != len(prerequisites):
            raise ValueError(idea_id + ".learning.prerequisites is invalid")
        if not isinstance(dimensions, list) or any(
            not isinstance(item, str) or not item.strip() for item in dimensions
        ):
            raise ValueError(idea_id + ".learning.dimensions is invalid")
        idea_by_id[idea_id] = idea

    for idea_id, idea in idea_by_id.items():
        learning = idea.get("learning") or {}
        unknown = set(learning.get("prerequisites", [])) - set(idea_by_id)
        if unknown:
            raise ValueError(idea_id + " has unknown canonical prerequisites: " + ", ".join(sorted(unknown)))

    blueprint_ids: set[str] = set()
    blueprint_ideas: set[str] = set()
    for blueprint in blueprints:
        if not isinstance(blueprint, dict):
            raise ValueError("lesson blueprint entries must be objects")
        blueprint_id = _required_text(blueprint.get("blueprint_id"), "blueprint_id", 200)
        idea_id = _required_text(blueprint.get("idea_id"), blueprint_id + ".idea_id", 160)
        _required_text(blueprint.get("title"), blueprint_id + ".title", 500)
        if blueprint_id in blueprint_ids:
            raise ValueError("lesson blueprint IDs must be unique")
        if idea_id not in idea_by_id:
            raise ValueError(blueprint_id + " references an unknown canonical idea")
        blueprint_ids.add(blueprint_id)
        if idea_id in blueprint_ideas:
            raise ValueError("each canonical idea may have at most one active blueprint")
        blueprint_ideas.add(idea_id)

    candidate_ideas = {
        idea_id for idea_id, idea in idea_by_id.items()
        if not isinstance((idea.get("learning") or {}).get("lesson_id"), str)
        or not (idea.get("learning") or {}).get("lesson_id", "").strip()
    }
    if blueprint_ideas != candidate_ideas:
        missing = sorted(candidate_ideas - blueprint_ideas)
        extra = sorted(blueprint_ideas - candidate_ideas)
        raise ValueError(
            "lesson blueprint coverage does not match unpublished catalog ideas; "
            + "missing=" + ",".join(missing) + "; extra=" + ",".join(extra)
        )
    declared_count = backlog.get("blueprint_count")
    if declared_count is not None and declared_count != len(blueprints):
        raise ValueError("lesson backlog blueprint_count does not match its entries")

    source_commit_short = source_commit[:12]
    catalog_sha = hashlib.sha256(catalog_raw).hexdigest()
    backlog_sha = hashlib.sha256(backlog_raw).hexdigest()
    registry = MerlinRegistry(root_path / "registry")
    registry.register_project(
        project_id,
        project_name,
        version="0.1.0",
        metadata={
            "source_repository": repository,
            "source_commit": source_commit,
            "idea_catalog_sha256": catalog_sha,
            "lesson_backlog_sha256": backlog_sha,
            "promotion_authority": False,
        },
    )
    catalog_logical_path = (
        "source/" + source_commit + "/" + CATALOG_RELATIVE_PATH.as_posix()
    )
    backlog_logical_path = (
        "source/" + source_commit + "/" + BACKLOG_RELATIVE_PATH.as_posix()
    )
    catalog_digest = registry.put_artifact(
        project_id, catalog_logical_path, catalog_raw, "application/json"
    )
    backlog_digest = registry.put_artifact(
        project_id, backlog_logical_path, backlog_raw, "application/json"
    )
    if not registry.verify_artifact(catalog_digest) or not registry.verify_artifact(backlog_digest):
        raise RuntimeError("canonical source artifact failed registry digest verification")

    graph = MerlinKnowledgeGraph(root_path / "knowledge-graph.sqlite3")
    project_node_id = "project:" + project_id
    catalog_node_id = "artifact:idea-catalog:" + source_commit_short
    backlog_node_id = "artifact:lesson-backlog:" + source_commit_short
    catalog_uri = "github://" + repository + "/" + source_commit + "/" + CATALOG_RELATIVE_PATH.as_posix()
    backlog_uri = "github://" + repository + "/" + source_commit + "/" + BACKLOG_RELATIVE_PATH.as_posix()

    graph.add_node(GraphNode(
        project_node_id,
        "project",
        project_name,
        {"project_id": project_id, "source_repository": repository},
        evidence_class="project_metadata",
    ))
    graph.add_node(GraphNode(
        catalog_node_id,
        "artifact",
        "Canonical mathematical idea catalog",
        {
            "sha256": catalog_digest,
            "source_commit": source_commit,
            "logical_path": catalog_logical_path,
            "size_bytes": len(catalog_raw),
            "idea_count": len(ideas),
        },
        evidence_class="source_artifact",
        source_uri=catalog_uri,
    ))
    graph.add_node(GraphNode(
        backlog_node_id,
        "artifact",
        "Review-gated mathematical lesson blueprint backlog",
        {
            "sha256": backlog_digest,
            "source_commit": source_commit,
            "logical_path": backlog_logical_path,
            "size_bytes": len(backlog_raw),
            "blueprint_count": len(blueprints),
        },
        evidence_class="source_artifact",
        source_uri=backlog_uri,
    ))
    graph.add_edge(GraphEdge(project_node_id, "contains", catalog_node_id, {"source_commit": source_commit}))
    graph.add_edge(GraphEdge(project_node_id, "contains", backlog_node_id, {"source_commit": source_commit}))

    idea_node_ids: dict[str, str] = {}
    for idea_id, idea in idea_by_id.items():
        node_id = "idea:" + idea_id + ":" + source_commit_short
        idea_node_ids[idea_id] = node_id
        learning = idea.get("learning") or {}
        payload = {
            "idea_id": idea_id,
            "kind": idea["kind"],
            "catalog_status": idea["status"],
            "claim": idea.get("claim", ""),
            "definitions": idea.get("definitions", []),
            "assumptions": idea.get("assumptions", []),
            "objections": idea.get("objections", []),
            "prerequisite_idea_ids": learning.get("prerequisites", []),
            "skill_dimensions": learning.get("dimensions", []),
            "lesson_id": learning.get("lesson_id"),
            "source_repository": repository,
            "source_commit": source_commit,
            "promotion_authority": False,
        }
        graph.add_node(GraphNode(
            node_id,
            "claim",
            idea["title"],
            payload,
            evidence_class=idea["status"],
            source_uri=catalog_uri,
        ))
        graph.add_edge(GraphEdge(project_node_id, "contains", node_id, {"source_commit": source_commit}))
        graph.add_edge(GraphEdge(node_id, "derived_from", catalog_node_id, {"catalog_sha256": catalog_sha}))
        for prerequisite_id in learning.get("prerequisites", []):
            graph.add_edge(GraphEdge(
                node_id,
                "depends_on",
                idea_node_ids.get(prerequisite_id, "idea:" + prerequisite_id + ":" + source_commit_short),
                {"prerequisite_idea_id": prerequisite_id},
            ))

    for blueprint in blueprints:
        blueprint_id = blueprint["blueprint_id"]
        idea_id = blueprint["idea_id"]
        node_id = "lesson-blueprint:" + blueprint_id + ":" + source_commit_short
        graph.add_node(GraphNode(
            node_id,
            "artifact",
            "Lesson blueprint: " + blueprint["title"],
            {
                "blueprint_id": blueprint_id,
                "idea_id": idea_id,
                "catalog_status": blueprint.get("catalog_status"),
                "delivery_state": blueprint.get("delivery_state"),
                "publication_gate": blueprint.get("publication_gate"),
                "pathways": blueprint.get("pathways", []),
                "skill_dimensions": blueprint.get("skill_dimensions", []),
                "review_required": blueprint.get("review_required", True),
                "source_commit": source_commit,
                "published_lesson": False,
                "promotion_authority": False,
            },
            evidence_class=str(blueprint.get("delivery_state") or "unreviewed"),
            source_uri=backlog_uri,
        ))
        graph.add_edge(GraphEdge(project_node_id, "contains", node_id, {"source_commit": source_commit}))
        graph.add_edge(GraphEdge(node_id, "derived_from", idea_node_ids[idea_id], {"idea_id": idea_id}))
        graph.add_edge(GraphEdge(node_id, "derived_from", backlog_node_id, {"backlog_sha256": backlog_sha}))

    # Initialize append-only runtime stores without enqueuing or executing work.
    ledger = HypothesisLedger(root_path / "hypotheses.sqlite3")
    outbox = MerlinEventOutbox(root_path / "outbox.sqlite3")
    snapshot = graph.export_snapshot()

    return {
        "schema": "merlin-persistent-bootstrap/1",
        "project_id": project_id,
        "source_repository": repository,
        "source_commit": source_commit,
        "source_artifacts": {
            "idea_catalog": {
                "sha256": catalog_sha,
                "registry_digest": catalog_digest,
                "logical_path": catalog_logical_path,
                "registry_verified": registry.verify_artifact(catalog_digest),
            },
            "lesson_backlog": {
                "sha256": backlog_sha,
                "registry_digest": backlog_digest,
                "logical_path": backlog_logical_path,
                "registry_verified": registry.verify_artifact(backlog_digest),
            },
        },
        "counts": {
            "canonical_ideas": len(idea_by_id),
            "review_gated_blueprints": len(blueprints),
            "graph_nodes": len(snapshot["nodes"]),
            "graph_edges": len(snapshot["edges"]),
        },
        "stores": {
            "registry": str(registry.db_path),
            "knowledge_graph": str(graph.path),
            "hypotheses": str(ledger.path),
            "outbox": str(outbox.path),
        },
        "epistemic_status": "source_catalog_and_candidate_blueprints_recorded_not_verified",
        "cace_verification": "unavailable_until_real_transport_and_trust_pins_are_configured",
        "promotion_authority": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize Merlin's persistent registry and knowledge graph.")
    parser.add_argument("--root", required=True, help="Persistent data directory; no existing files are deleted.")
    parser.add_argument("--source-commit", required=True, help="Exact lowercase 40-character source commit.")
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--project-id", default="merlin")
    parser.add_argument("--project-name", default="Merlin")
    args = parser.parse_args(argv)
    report = bootstrap_merlin(
        root=args.root,
        source_commit=args.source_commit,
        repository=args.repository,
        project_id=args.project_id,
        project_name=args.project_name,
    )
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["bootstrap_merlin", "main"]
