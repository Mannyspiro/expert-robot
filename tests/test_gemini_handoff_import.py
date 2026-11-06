import json

import pytest

from merlin.foundation_store import MerlinFoundationStore
from merlin.gemini_handoff_import import (
    GeminiHandoffError,
    IncompleteGeminiHandoff,
    ingest_gemini_handoff,
    parse_gemini_handoff,
)


HANDOFF = (
    "Gemini master handoff fixture\n"
    "2. Detailed Full-Context Breakdown of All 2 Conversations\n"
    "Chat 1 — c_1234567890abcdef: Merlin architecture (2026-11-01 12:00:00 UTC · COMPLETED · 2 Turns)\n"
    "* User Prompt: \"Build the canonical Merlin registry.\"\n"
    "* Execution & Synthesis: The assistant described the registry and provenance model.\n"
    "* Deliverables Created: registry design and tests.\n"
    "Chat 2 — c_abcdef1234567890: Personal nutrition (2026-11-01 13:00:00 UTC · COMPLETED · 1 Turn)\n"
    "* User Prompt: \"Create a personal meal plan.\"\n"
    "* Execution & Synthesis: A private personal plan was summarized.\n"
)


def make_store(tmp_path):
    store = MerlinFoundationStore(tmp_path / "store")
    store.register_project("merlin", "Merlin")
    return store


def test_parser_preserves_all_sections_and_marks_handoff_granularity():
    parsed = parse_gemini_handoff(HANDOFF)
    assert parsed["expected_count"] == 2
    assert parsed["parsed_count"] == 2
    assert parsed["completeness"] == "complete"

    first = parsed["conversations"][0]
    assert first.conversation_id == "c_1234567890abcdef"
    assert first.title == "Merlin architecture"
    assert first.timestamp == "2026-11-01 12:00:00 UTC"
    assert first.status == "COMPLETED"
    assert first.status_details == "2 Turns"
    assert '* User Prompt: "Build the canonical Merlin registry."' in first.prompt_excerpts
    assert any("Execution & Synthesis" in marker for marker in first.response_markers)
    assert first.raw_text.endswith("* Deliverables Created: registry design and tests.\n")


def test_parser_rejects_missing_headers_and_incomplete_declared_count():
    with pytest.raises(GeminiHandoffError):
        parse_gemini_handoff("not a Gemini conversation handoff")

    incomplete = HANDOFF.replace("Detailed Full-Context Breakdown of All 2", "Detailed Full-Context Breakdown of All 3")
    with pytest.raises(IncompleteGeminiHandoff):
        parse_gemini_handoff(incomplete)


def test_import_requires_explicit_allowlist_and_rejects_unknown_ids(tmp_path):
    store = make_store(tmp_path)
    archive = HANDOFF.encode("utf-8")

    with pytest.raises(GeminiHandoffError):
        ingest_gemini_handoff(
            store, "merlin", archive, source_filename="handoff.txt",
            included_conversation_ids=(),
        )
    with pytest.raises(GeminiHandoffError):
        ingest_gemini_handoff(
            store, "merlin", archive, source_filename="handoff.txt",
            included_conversation_ids=("c_0000000000000000",),
        )

    assert store.registry.inventory("merlin")["artifacts"] == []


def test_import_stores_only_allowlisted_sections_and_links_the_graph(tmp_path):
    store = make_store(tmp_path)
    archive = HANDOFF.encode("utf-8")
    result = ingest_gemini_handoff(
        store,
        "merlin",
        archive,
        source_filename="Full Chats Master Handoff.txt",
        included_conversation_ids=("c_1234567890abcdef",),
    )

    assert result["parsed_conversation_count"] == 2
    assert result["imported_conversation_count"] == 1
    assert result["excluded_conversation_count"] == 1
    assert result["source_archive_bytes_retained"] is False
    assert result["source_granularity"] == "conversation_handoff_summary_not_raw_transcript"
    assert result["registry_reconciliation"]["consistent"] is True

    inventory = store.registry.inventory("merlin")
    paths = {item["logical_path"] for item in inventory["artifacts"]}
    assert len(paths) == 3
    assert any(path.endswith("c_1234567890abcdef.txt") for path in paths)
    assert any(path.endswith("c_1234567890abcdef.index.json") for path in paths)
    assert any(path.endswith("/manifest.json") for path in paths)
    assert not any("c_abcdef1234567890" in path for path in paths)

    imported = result["imported_conversations"][0]
    raw = store.registry.get_artifact_bytes(imported["raw_section_sha256"])
    assert raw.decode("utf-8") == (
        "Chat 1 — c_1234567890abcdef: Merlin architecture (2026-11-01 12:00:00 UTC · COMPLETED · 2 Turns)\n"
        "* User Prompt: \"Build the canonical Merlin registry.\"\n"
        "* Execution & Synthesis: The assistant described the registry and provenance model.\n"
        "* Deliverables Created: registry design and tests.\n"
    )

    source_node = store.graph.get_node(result["source_node_id"])
    assert source_node is not None
    assert source_node.payload["source_archive_bytes_retained"] is False
    session = store.graph.get_node(imported["session_node_id"])
    assert session is not None
    assert session.payload["source_granularity"] == "handoff_summary_not_raw_transcript"
    assert store.graph.neighbors(imported["session_node_id"], "out")


def test_import_is_idempotent_for_same_source_and_allowlist(tmp_path):
    store = make_store(tmp_path)
    args = {
        "store": store,
        "project_id": "merlin",
        "archive_bytes": HANDOFF.encode("utf-8"),
        "source_filename": "handoff.txt",
        "included_conversation_ids": ("c_1234567890abcdef",),
    }
    first = ingest_gemini_handoff(**args)
    second = ingest_gemini_handoff(**args)

    assert first["manifest_artifact_sha256"] == second["manifest_artifact_sha256"]
    assert len(store.registry.inventory("merlin")["artifacts"]) == 3
    assert second["registry_reconciliation"]["consistent"] is True


def test_import_rejects_non_utf8_and_oversized_sources(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(GeminiHandoffError):
        ingest_gemini_handoff(
            store, "merlin", b"\xff", source_filename="bad.txt",
            included_conversation_ids=("c_1234567890abcdef",),
        )
    with pytest.raises(GeminiHandoffError):
        ingest_gemini_handoff(
            store, "merlin", b"x" * 20, source_filename="large.txt",
            included_conversation_ids=("c_1234567890abcdef",),
            max_archive_bytes=10,
        )
