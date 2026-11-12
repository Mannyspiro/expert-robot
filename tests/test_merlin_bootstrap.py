from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from merlin.bootstrap import bootstrap_merlin
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_records_all_ideas_and_review_gated_blueprints_idempotently():
    with TemporaryDirectory() as directory:
        root = Path(directory) / "merlin-data"
        first = bootstrap_merlin(
            root=root,
            source_commit="a" * 40,
            repository_root=REPOSITORY_ROOT,
        )
        graph = MerlinKnowledgeGraph(root / "knowledge-graph.sqlite3")
        first_snapshot = graph.export_snapshot()

        assert first["counts"]["canonical_ideas"] == 57
        assert first["counts"]["review_gated_blueprints"] == 36
        assert first["promotion_authority"] is False
        assert first["cace_verification"].startswith("unavailable")
        assert first["source_artifacts"]["idea_catalog"]["registry_verified"] is True
        assert first["source_artifacts"]["lesson_backlog"]["registry_verified"] is True

        node_ids = {node["node_id"] for node in first_snapshot["nodes"]}
        assert "idea:MATH-REP-001:aaaaaaaaaaaa" in node_ids
        assert "lesson-blueprint:lesson-math-rep-001-v1:aaaaaaaaaaaa" in node_ids
        assert "project:merlin" in node_ids

        registry = MerlinRegistry(root / "registry")
        assert registry.verify_artifact(first["source_artifacts"]["idea_catalog"]["registry_digest"])
        assert registry.verify_artifact(first["source_artifacts"]["lesson_backlog"]["registry_digest"])

        repeated = bootstrap_merlin(
            root=root,
            source_commit="a" * 40,
            repository_root=REPOSITORY_ROOT,
        )
        repeated_snapshot = graph.export_snapshot()
        assert repeated["counts"] == first["counts"]
        assert repeated_snapshot["snapshot_sha256"] == first_snapshot["snapshot_sha256"]


def test_bootstrap_new_source_commit_appends_versioned_nodes_without_deleting_old_data():
    with TemporaryDirectory() as directory:
        root = Path(directory) / "merlin-data"
        old = bootstrap_merlin(
            root=root,
            source_commit="a" * 40,
            repository_root=REPOSITORY_ROOT,
        )
        old_graph = MerlinKnowledgeGraph(root / "knowledge-graph.sqlite3")
        old_snapshot = old_graph.export_snapshot()
        old_node_ids = {node["node_id"] for node in old_snapshot["nodes"]}

        new = bootstrap_merlin(
            root=root,
            source_commit="b" * 40,
            repository_root=REPOSITORY_ROOT,
        )
        new_snapshot = old_graph.export_snapshot()
        new_node_ids = {node["node_id"] for node in new_snapshot["nodes"]}

        assert old_node_ids.issubset(new_node_ids)
        assert "idea:MATH-REP-001:aaaaaaaaaaaa" in new_node_ids
        assert "idea:MATH-REP-001:bbbbbbbbbbbb" in new_node_ids
        assert new["counts"]["graph_nodes"] > old["counts"]["graph_nodes"]
        assert new["source_commit"] == "b" * 40
        assert new["promotion_authority"] is False
