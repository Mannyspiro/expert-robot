import hashlib
import json
import zipfile

import pytest

from merlin.archive_intake import ArchiveIntakeError, ingest_archives, inspect_zip
from merlin.foundation_store import MerlinFoundationStore


def make_zip(path, members):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_zip_intake_preserves_paths_hashes_and_original_archive(tmp_path):
    archive = tmp_path / "foundation.zip"
    make_zip(archive, {"docs/overview.md": b"Merlin", "tests/test.txt": b"same"})
    store = MerlinFoundationStore(tmp_path / "store")
    store.register_project("merlin", "Merlin")
    receipt = ingest_archives(store, "merlin", [archive])
    assert receipt["archive_count"] == 1
    assert receipt["total_member_count"] == 2
    assert receipt["registry_reconciliation"]["consistent"] is True
    assert receipt["archives"][0]["members"][0]["sha256"]
    assert receipt["intake_receipt_sha256"]
    assert store.registry.verify_artifact(receipt["archives"][0]["archive_sha256"])


def test_zip_intake_detects_duplicate_content_across_archives(tmp_path):
    one, two = tmp_path / "one.zip", tmp_path / "two.zip"
    make_zip(one, {"a.txt": b"identical"})
    make_zip(two, {"b.txt": b"identical"})
    store = MerlinFoundationStore(tmp_path / "store")
    store.register_project("merlin", "Merlin")
    receipt = ingest_archives(store, "merlin", [one, two])
    assert len(receipt["duplicate_content"]) == 1
    assert receipt["registry_reconciliation"]["consistent"] is True

    digest = hashlib.sha256(b"identical").hexdigest()
    snapshot = store.graph.export_snapshot()
    member_refs = [
        node for node in snapshot["nodes"]
        if node["node_type"] == "source"
        and node["payload"]["artifact_sha256"] == digest
    ]
    assert len(member_refs) == 2
    assert {node["payload"]["logical_path"] for node in member_refs} == {
        f"intake/members/{receipt['archives'][0]['archive_sha256']}/a.txt",
        f"intake/members/{receipt['archives'][1]['archive_sha256']}/b.txt",
    }
    content_nodes = [
        node for node in snapshot["nodes"]
        if node["node_id"] == f"artifact:sha256:{digest}"
    ]
    assert len(content_nodes) == 1
    assert receipt["registry_reconciliation"]["consistent"] is True

    digest = next(iter(receipt["duplicate_content"]))
    artifact_id = f"artifact:sha256:{digest}"
    artifact_node = store.graph.get_node(artifact_id)
    assert artifact_node is not None
    assert artifact_node.node_type == "artifact"
    assert artifact_node.payload == {"sha256": digest, "size_bytes": len(b"identical")}

    project_edges = store.graph.neighbors("project:merlin", "out")
    source_ids = {
        edge["target_id"] for edge in project_edges
        if edge["relation"] == "contains" and edge["target_id"].startswith("source:")
    }
    assert len(source_ids) == 2
    for source_id in source_ids:
        provenance_edges = store.graph.neighbors(source_id, "out")
        assert any(
            edge["relation"] == "derived_from" and edge["target_id"] == artifact_id
            for edge in provenance_edges
        )


def test_zip_intake_rejects_traversal_and_limits(tmp_path):
    archive = tmp_path / "unsafe.zip"
    make_zip(archive, {"../escape.txt": b"no"})
    with pytest.raises(ArchiveIntakeError):
        inspect_zip(archive)
    safe = tmp_path / "large.zip"
    make_zip(safe, {"data.bin": b"x" * 100})
    with pytest.raises(ArchiveIntakeError):
        inspect_zip(safe, max_member_bytes=10)


def test_zip_intake_requires_explicit_project_registration(tmp_path):
    archive = tmp_path / "small.zip"
    make_zip(archive, {"a.txt": b"x"})
    store = MerlinFoundationStore(tmp_path / "store")
    with pytest.raises(KeyError):
        ingest_archives(store, "missing", [archive])
