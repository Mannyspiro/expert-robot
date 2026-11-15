from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.registry_queries import MerlinReadAPI
from merlin.text_extractor import (
    EXTRACTION_SCHEMA,
    extract_text_artifact,
    store_text_extraction,
)


class TextExtractorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = MerlinRegistry(self.root / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.graph = MerlinKnowledgeGraph(self.root / "knowledge-graph.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def _source(self, path: str, raw: bytes):
        self.registry.put_artifact("merlin", path, raw, "text/plain; charset=utf-8")
        return self.registry.artifact_ref("merlin", path)

    def test_markdown_segments_have_exact_utf8_byte_and_line_ranges(self):
        raw = (
            "# Título\r\n\r\n"
            "Párrafo uno\r\ncontinúa aquí.\r\n\r\n"
            "- primero\r\n- segundo\r\n\r\n"
            "> cita\r\n\r\n"
            "```py\r\nx = 1\r\n```\r\n"
        ).encode("utf-8")
        ref = self._source("notes/example.md", raw)
        result = extract_text_artifact(self.registry, ref)
        self.assertEqual(result["schema"], EXTRACTION_SCHEMA)
        self.assertEqual(result["format"], "markdown")
        self.assertEqual(
            [segment["kind"] for segment in result["segments"]],
            ["heading", "paragraph", "list", "blockquote", "code_block"],
        )
        self.assertEqual(result["segments"][0]["level"], 1)
        self.assertTrue(result["segments"][-1]["closed"])
        for segment in result["segments"]:
            start = segment["byte_range"]["start"]
            end = segment["byte_range"]["end_exclusive"]
            exact = raw[start:end]
            self.assertEqual(segment["text"].encode("utf-8"), exact)
            self.assertEqual(segment["content_sha256"], hashlib.sha256(exact).hexdigest())
            self.assertLessEqual(segment["line_range"]["start"], segment["line_range"]["end"])
        self.assertEqual(result["source_sha256"], ref["sha256"])
        self.assertEqual(result["source_bytes"], len(raw))

    def test_plain_text_does_not_infer_markdown_structure(self):
        raw = b"# This is plain text\nsecond line\n\nthird paragraph\n"
        ref = self._source("notes/plain.txt", raw)
        result = extract_text_artifact(self.registry, ref)
        self.assertEqual(result["format"], "plain_text")
        self.assertEqual([x["kind"] for x in result["segments"]], ["paragraph", "paragraph"])
        self.assertTrue(result["segments"][0]["text"].startswith("# This is plain text"))

    def test_empty_file_has_a_whole_artifact_binding(self):
        ref = self._source("notes/empty.txt", b"")
        result = extract_text_artifact(self.registry, ref)
        self.assertEqual(result["segment_count"], 0)
        self.assertEqual(len(result["source_bindings"]), 1)
        self.assertEqual(result["source_bindings"][0]["locator_type"], "whole_artifact")

    def test_invalid_utf8_fails_closed(self):
        ref = self._source("notes/invalid.txt", b"valid\xffinvalid")
        with self.assertRaises(UnicodeDecodeError):
            extract_text_artifact(self.registry, ref)

    def test_byte_and_segment_budgets_are_enforced(self):
        ref = self._source("notes/long.txt", b"one\ntwo\nthree\n")
        with self.assertRaises(ValueError):
            extract_text_artifact(self.registry, ref, max_bytes=2)
        with self.assertRaises(ValueError):
            extract_text_artifact(self.registry, ref, max_segments=1, format="plain_text")

    def test_extraction_is_deterministic_for_same_artifact_version(self):
        ref = self._source("notes/stable.md", b"# Stable\n\nSame body.\n")
        first = extract_text_artifact(self.registry, ref)
        second = extract_text_artifact(self.registry, ref)
        self.assertEqual(first["extraction_id"], second["extraction_id"])
        self.assertEqual(first["segments"], second["segments"])

    def test_store_creates_canonical_derived_representation_and_read_api_view(self):
        raw = b"# Stored\n\nOriginal source remains immutable.\n"
        ref = self._source("notes/stored.md", raw)
        result = store_text_extraction(
            self.registry,
            self.graph,
            ref,
            project_id="merlin",
            source_repo="Mannyspiro/expert-robot",
            source_commit="d" * 40,
        )
        stored = result["stored_representation"]
        self.assertEqual(stored["authority"], "derived-representation-only")
        self.assertEqual(stored["verification"], "not-verified")
        api = MerlinReadAPI(self.registry, graph=self.graph)
        query = api.knowledge_representation(stored["representation_ref"])
        self.assertEqual(query["manifest"]["representation_type"], "text_extraction")
        self.assertEqual(query["manifest"]["payload"]["schema"], EXTRACTION_SCHEMA)
        self.assertEqual(query["sources"][0]["artifact_ref"], ref)
        self.assertEqual(query["sources"][0]["resolution"]["verified"], True)
        self.assertFalse(query["source_bytes_included"])


if __name__ == "__main__":
    unittest.main()
