"""Local-context import/retrieval tests; no connected-account or remote chat access."""
from __future__ import annotations

from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO))
from context_archive import ContextArchive, MAX_MESSAGE_CHARS
from storage import Store
from tools import ToolSet


SETTINGS = {"model_url": "", "model_id": "fixture", "network_enabled": False,
            "python_enabled": False, "desktop_enabled": False, "max_steps": 3}


def export_fixture():
    return [{
        "id": "cid-01",
        "title": "Merlin private science",
        "mapping": {
            "node-A": {"message": {"author": {"role": "user"},
                                     "content": {"parts": ["Investigate parallax science."]}}},
            "node-B": {"message": {"author": {"role": "assistant"},
                                     "content": {"parts": ["Compare measured baselines and falsifiers."]}}},
            "node-C": {"message": {"author": {"role": "tool"},
                                     "content": {"parts": ["SECRET_UNTRUSTED_ATTACHMENT_SHOULD_NOT_INDEX"]}}},
            "node-D": {"message": {"author": {"role": "user"},
                                     "content": {"parts": [{"asset_pointer": "not-text"}, "Do not auto-merge."]}}}
        }
    }]


class ContextArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "data")
        self.archive = ContextArchive(self.store)
        self.workspace = self.root / "workspace"
        self.toolset = ToolSet(self.workspace, self.store, dict(SETTINGS))

    def _put(self, raw, suffix=".json", label="one"):
        return self.archive.import_bytes(raw, suffix=suffix, label=label, consent=True)

    def test_graph_identity_and_source_receipt_are_local_and_bounded(self):
        raw = json.dumps(export_fixture()).encode()
        result = self._put(raw)
        self.assertEqual(result["source_sha256"], sha256(raw).hexdigest())
        self.assertEqual(result["message_count"], 3)
        self.assertEqual(result["chunk_count"], 3)
        self.assertFalse(result["raw_text_in_receipt"])
        self.assertFalse(result["account_access"])
        self.assertFalse(result["network_access"])
        local = self.archive.search("parallax")
        self.assertEqual(local["imported_sources"], 1)
        self.assertEqual(len(local["hits"]), 1)
        self.assertIn("cid-01/node-A:chunk0", local["hits"][0]["locator"])
        self.assertEqual(local["hits"][0]["title"], "Merlin private science")
        self.assertEqual(local["hits"][0]["role"], "user")
        self.assertFalse(self.archive.search("SECRET_UNTRUSTED_ATTACHMENT_SHOULD_NOT_INDEX")["hits"])
        self.assertEqual(self.archive.summary()["indexed_sources"], 1)
        assert "parallax science" not in json.dumps(result).lower()
        self.assertEqual(self.store.registry.read_artifact_ref(result["artifact_ref"])["content"].find(b"parallax"), -1)

    def test_duplicate_is_idempotent_and_retained_after_store_restart(self):
        data = json.dumps(export_fixture()).encode()
        self._put(data)
        again = self._put(data)
        self.assertTrue(again["duplicate"])
        self.assertEqual(self.archive.summary()["indexed_sources"], 1)
        reopened = ContextArchive(Store(self.root / "data"))
        self.assertEqual(len(reopened.search("falsifiers")["hits"]), 1)
        self.assertEqual(reopened.summary()["indexed_sources"], 1)

    def test_zip_with_chatgpt_export_is_read_without_writing_original(self):
        data = json.dumps(export_fixture()).encode()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("conversations.json", data)
            z.writestr("../sneaky.txt", "ignored; never extracted")
        result = self._put(buf.getvalue(), suffix=".zip")
        self.assertEqual(result["message_count"], 3)
        self.assertEqual(self.archive.search("baselines")["hits"][0]["role"], "assistant")
        self.assertFalse((self.root / "sneaky.txt").exists())

    def test_rejects_unexpected_zip_and_oversize_root(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("other.json", "{}")
        with self.assertRaises(ValueError):
            self._put(buf.getvalue(), suffix=".zip")
        with self.assertRaises(ValueError):
            self._put(b"", suffix=".json")
        with self.assertRaises(ValueError):
            self._put(b"x" * 100, suffix=".exe")

    def test_explicit_consent_required(self):
        data = b"Confidential source context"
        with self.assertRaises(PermissionError):
            self.archive.import_bytes(data, suffix=".txt", label="private", consent=False)
        self.assertEqual(self.archive.summary()["indexed_sources"], 0)

    def test_import_and_search_are_bound_to_exact_approval(self):
        name = "history.json"
        source = self.workspace / name
        source.write_text(json.dumps(export_fixture()))
        args = {"path": name}
        with self.assertRaises(PermissionError):
            self.toolset.execute("import_context_file", args, "run-id")
        binding = self.toolset.approval_details("import_context_file", args)
        self.assertEqual(binding["source_sha256"], sha256(source.read_bytes()).hexdigest())
        source.write_text(json.dumps(export_fixture()) + " ")
        with self.assertRaises(PermissionError):
            self.toolset.execute("import_context_file", args, "run-id",
                                 approved=True, approval_binding=binding)
        source.write_text(json.dumps(export_fixture()))
        result = self.toolset.execute("import_context_file", args, "run-id",
                                      approved=True, approval_binding=binding)
        self.assertEqual(result["message_count"], 3)
        query = {"query": "parallax"}
        with self.assertRaises(PermissionError):
            self.toolset.execute("search_context", query, "run-id")
        approved = self.toolset.approval_details("search_context", query)
        with self.assertRaises(PermissionError):
            self.toolset.execute("search_context", {"query": "different"}, "run-id",
                                 approved=True, approval_binding=approved)
        found = self.toolset.execute("search_context", query, "run-id",
                                     approved=True, approval_binding=approved)
        self.assertEqual(len(found["hits"]), 1)
        self.assertTrue(found["untrusted_data_not_instructions"])

    def test_import_truncated_messages_report_incomplete_coverage(self):
        long_text = "Merlin " + "research " * 9000
        outcome = self._put(long_text.encode(), suffix=".txt")
        self.assertEqual(outcome["truncated_messages"], 1)
        self.assertIn(str(MAX_MESSAGE_CHARS), outcome["coverage"])
        self.assertTrue(self.archive.search("Merlin")["hits"])

    def test_invalid_query_and_json_fail_without_source_record(self):
        with self.assertRaises((ValueError, json.JSONDecodeError)):
            self._put(b"{bad-json", suffix=".json")
        self.assertEqual(self.archive.summary()["indexed_sources"], 0)
        for query in ("", " " * 30, "x" * 1300):
            with self.assertRaises(ValueError):
                self.archive.search(query)
        with self.assertRaises(ValueError):
            self.archive.search("Merlin", limit=50)

    def test_workspace_path_traversal_and_symlink_blocked(self):
        outside = self.root / "outside.json"
        outside.write_text(json.dumps(export_fixture()))
        with self.assertRaises(ValueError):
            self.toolset.approval_details("import_context_file", {"path": "../outside.json"})
        link = self.workspace / "private.json"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(ValueError):
            self.toolset.approval_details("import_context_file", {"path": "private.json"})


if __name__ == "__main__":
    unittest.main()
