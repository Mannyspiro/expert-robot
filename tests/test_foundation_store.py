import pytest

from merlin.foundation_store import MerlinFoundationStore


def test_project_artifact_claim_and_evidence_are_unified(tmp_path):
    store = MerlinFoundationStore(tmp_path)
    store.register_project("merlin-core", "Merlin Core", metadata={"layer": "foundation"})
    digest = store.put_artifact(
        "merlin-core", "research/source.txt", b"source material",
        "text/plain", artifact_type="source", evidence_class="literature",
        metadata={"origin": "public"},
    )
    store.add_claim(
        "claim-001", "The source supports a bounded statement.",
        "literature", assumptions=("source is authentic",),
        project_id="merlin-core", evidence_artifact_digests=(digest,),
    )
    assert store.registry.verify_artifact(digest)
    assert store.graph.get_node(f"claim:claim-001") is not None
    assert store.reconcile_project("merlin-core")["consistent"] is True
    supports = store.graph.neighbors(f"claim:claim-001", "in")
    assert any(edge["relation"] == "supports" for edge in supports)


def test_reconciliation_detects_graph_drift(tmp_path):
    store = MerlinFoundationStore(tmp_path)
    store.register_project("p", "Project")
    digest = store.registry.put_artifact("p", "orphan.bin", b"orphan")
    report = store.reconcile_project("p")
    assert report["consistent"] is False
    assert report["graph_artifact_missing"] == ["orphan.bin"]
    assert digest


def test_evidence_must_be_integrity_verified_and_in_graph(tmp_path):
    store = MerlinFoundationStore(tmp_path)
    store.register_project("p", "Project")
    with pytest.raises(ValueError):
        store.add_claim("c", "Claim", "unreviewed", evidence_artifact_digests=("0" * 64,))
