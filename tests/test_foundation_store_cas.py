import pytest

from merlin.foundation_store import MerlinFoundationStore


def test_explicit_replacement_keeps_predecessor_and_graph_lineage(tmp_path):
    store = MerlinFoundationStore(tmp_path)
    store.register_project("p", "Project")
    first = store.put_artifact("p", "source.txt", b"v1", "text/plain", artifact_type="source")
    head = store.registry.get_artifact_head("p", "source.txt")
    second = store.replace_artifact(
        "p", "source.txt", b"v2", expected_digest=first,
        expected_generation=head["generation"], media_type="text/plain",
        artifact_type="source", actor="test", operation_id="replace-1",
    )
    assert second != first
    assert store.registry.get_artifact_bytes(first) == b"v1"
    assert store.registry.get_artifact_bytes(second) == b"v2"
    assert store.registry.artifact_history("p", "source.txt")[1]["pre_change_recovery_id"]
    assert store.reconcile_project("p")["consistent"] is True
