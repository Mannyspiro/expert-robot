import tempfile
import unittest

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
    "3. Master Chronological Ledger of All Historical Milestones (Iterations 1–3054)\n"
    "Technical appendix must not be attached to the final conversation.\n"
)


class GeminiHandoffImportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MerlinFoundationStore(self.temp_dir.name + "/store")
        self.store.register_project("merlin", "Merlin")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parser_preserves_all_sections_and_marks_handoff_granularity(self):
        parsed = parse_gemini_handoff(HANDOFF)
        self.assertEqual(parsed["expected_count"], 2)
        self.assertEqual(parsed["parsed_count"], 2)
        self.assertEqual(parsed["completeness"], "complete")
        self.assertNotIn("Technical appendix", parsed["conversations"][-1].raw_text)

        first = parsed["conversations"][0]
        self.assertEqual(first.conversation_id, "c_1234567890abcdef")
        self.assertEqual(first.title, "Merlin architecture")
        self.assertEqual(first.timestamp, "2026-11-01 12:00:00 UTC")
        self.assertEqual(first.status, "COMPLETED")
        self.assertEqual(first.status_details, "2 Turns")
        self.assertIn('* User Prompt: "Build the canonical Merlin registry."', first.prompt_excerpts)
        self.assertTrue(any("Execution & Synthesis" in marker for marker in first.response_markers))
        self.assertTrue(first.raw_text.endswith("* Deliverables Created: registry design and tests.\n"))

    def test_parser_rejects_missing_headers_and_incomplete_declared_count(self):
        with self.assertRaises(GeminiHandoffError):
            parse_gemini_handoff("not a Gemini conversation handoff")

        incomplete = HANDOFF.replace(
            "Detailed Full-Context Breakdown of All 2",
            "Detailed Full-Context Breakdown of All 3",
        )
        with self.assertRaises(IncompleteGeminiHandoff):
            parse_gemini_handoff(incomplete)

    def test_import_requires_explicit_allowlist_and_rejects_unknown_ids(self):
        archive = HANDOFF.encode("utf-8")
        with self.assertRaises(GeminiHandoffError):
            ingest_gemini_handoff(
                self.store, "merlin", archive, source_filename="handoff.txt",
                included_conversation_ids=(),
            )
        with self.assertRaises(GeminiHandoffError):
            ingest_gemini_handoff(
                self.store, "merlin", archive, source_filename="handoff.txt",
                included_conversation_ids=("c_0000000000000000",),
            )
        with self.assertRaises(GeminiHandoffError):
            ingest_gemini_handoff(
                self.store, "merlin", archive, source_filename="handoff.txt",
                included_conversation_ids=("c_1234567890abcdef",),
                conversation_metadata={"c_1234567890abcdef": {"domain": "core", "unknown": "value"}},
            )
        self.assertEqual(self.store.registry.inventory("merlin")["artifacts"], [])

    def test_import_stores_only_allowlisted_sections_and_links_the_graph(self):
        archive = HANDOFF.encode("utf-8")
        result = ingest_gemini_handoff(
            self.store,
            "merlin",
            archive,
            source_filename="Full Chats Master Handoff.txt",
            included_conversation_ids=("c_1234567890abcdef",),
            conversation_metadata={
                "c_1234567890abcdef": {
                    "domain": "merlin_architecture",
                    "relevance": "core_architecture",
                    "merlin_capabilities": ["registry", "knowledge_graph", "provenance"],
                    "evidence_handling": "source_context_unverified",
                }
            },
        )

        self.assertEqual(result["parsed_conversation_count"], 2)
        self.assertEqual(result["imported_conversation_count"], 1)
        self.assertEqual(result["excluded_conversation_count"], 1)
        self.assertFalse(result["source_archive_bytes_retained"])
        self.assertEqual(
            result["source_granularity"],
            "handoff_summary_and_selected_technical_appendices",
        )
        self.assertTrue(result["registry_reconciliation"]["consistent"])

        inventory = self.store.registry.inventory("merlin")
        paths = {item["logical_path"] for item in inventory["artifacts"]}
        self.assertEqual(len(paths), 3)
        self.assertTrue(any(path.endswith("c_1234567890abcdef.txt") for path in paths))
        self.assertTrue(any(path.endswith("c_1234567890abcdef.index.json") for path in paths))
        self.assertTrue(any(path.endswith("/manifest.json") for path in paths))
        self.assertFalse(any("c_abcdef1234567890" in path for path in paths))

        imported = result["imported_conversations"][0]
        raw = self.store.registry.get_artifact_bytes(imported["raw_section_sha256"])
        self.assertEqual(
            raw.decode("utf-8"),
            (
                "Chat 1 — c_1234567890abcdef: Merlin architecture (2026-11-01 12:00:00 UTC · COMPLETED · 2 Turns)\n"
                "* User Prompt: \"Build the canonical Merlin registry.\"\n"
                "* Execution & Synthesis: The assistant described the registry and provenance model.\n"
                "* Deliverables Created: registry design and tests.\n"
            ),
        )

        source_node = self.store.graph.get_node(result["source_node_id"])
        self.assertIsNotNone(source_node)
        self.assertFalse(source_node.payload["source_archive_bytes_retained"])
        session = self.store.graph.get_node(imported["session_node_id"])
        self.assertIsNotNone(session)
        self.assertEqual(session.payload["source_granularity"], "handoff_summary_not_raw_transcript")
        self.assertEqual(session.payload["classification"]["domain"], "merlin_architecture")
        self.assertTrue(self.store.graph.neighbors(imported["session_node_id"], "out"))

    def test_import_is_idempotent_for_same_source_and_allowlist(self):
        args = {
            "store": self.store,
            "project_id": "merlin",
            "archive_bytes": HANDOFF.encode("utf-8"),
            "source_filename": "handoff.txt",
            "included_conversation_ids": ("c_1234567890abcdef",),
        }
        first = ingest_gemini_handoff(**args)
        second = ingest_gemini_handoff(**args)

        self.assertEqual(first["manifest_artifact_sha256"], second["manifest_artifact_sha256"])
        self.assertEqual(len(self.store.registry.inventory("merlin")["artifacts"]), 3)
        self.assertTrue(second["registry_reconciliation"]["consistent"])

    def test_import_rejects_non_utf8_and_oversized_sources(self):
        with self.assertRaises(GeminiHandoffError):
            ingest_gemini_handoff(
                self.store, "merlin", b"\xff", source_filename="bad.txt",
                included_conversation_ids=("c_1234567890abcdef",),
            )
        with self.assertRaises(GeminiHandoffError):
            ingest_gemini_handoff(
                self.store, "merlin", b"x" * 20, source_filename="large.txt",
                included_conversation_ids=("c_1234567890abcdef",),
                max_archive_bytes=10,
            )


if __name__ == "__main__":
    unittest.main()
