"""Approval-gated Obsidian note import into canonical Merlin stores."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.obsidian_promotion import ObsidianNotePromotion
from merlin.obsidian_vault_bridge import ObsidianVaultBridge
from merlin.project_registry import MerlinRegistry


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.vault = base / "vault"
        self.vault.mkdir()
        self.note = self.vault / "Research.md"
        self.note.write_text("# Research\nQwen local reasoning is not independent evidence.\n",
                             encoding="utf-8")
        self.registry = MerlinRegistry(base / "registry")
        self.registry.register_project("project", "Merlin Research")
        self.graph = MerlinKnowledgeGraph(base / "graph.sqlite3")
        self.promotion = ObsidianNotePromotion(
            ObsidianVaultBridge(self.vault), self.registry, self.graph)

    def preview(self):
        return self.promotion.preview("project", "Research.md", vault_label="test")

    def test_readonly_preview_contains_digest_and_no_note_text(self):
        before = self.registry.inventory("project")
        result = self.preview()
        self.assertEqual(result["source_sha256"], hashlib.sha256(self.note.read_bytes()).hexdigest())
        self.assertTrue(result["approval_required"])
        self.assertEqual(result["evidence_class"], "unreviewed_source_content")
        self.assertNotIn("Qwen", repr(result))
        self.assertEqual(self.registry.inventory("project"), before)
        self.assertEqual(self.graph.export_snapshot()["nodes"], [])

    def test_missing_or_denied_operator_approval_never_imports(self):
        preview = self.preview()
        for approval in (None, lambda _preview: False):
            with self.subTest(approval=approval):
                with self.assertRaises(PermissionError):
                    self.promotion.promote(preview, operator_approve=approval)
        self.assertEqual(self.registry.artifact_history("project", preview["logical_path"]), [])
        self.assertEqual(self.graph.export_snapshot()["nodes"], [])

    def test_explicit_approval_creates_versioned_verified_artifact_and_graph(self):
        preview = self.preview()
        seen = []
        def approve(item):
            seen.append(item)
            return True
        result = self.promotion.promote(preview, operator_approve=approve)
        self.assertEqual(seen, [preview])
        self.assertEqual(result["status"], "imported_unverified")
        self.assertFalse(result["note_truth_approved"])
        self.assertEqual(result["source_sha256"], preview["source_sha256"])
        ref = result["artifact_ref"]
        self.assertEqual(ref["version"], 1)
        self.assertEqual(self.registry.read_artifact_ref(ref)["content"], self.note.read_bytes())
        source = self.graph.get_node(result["source_node_id"])
        self.assertEqual(source.evidence_class, "user_approved_unverified")
        self.assertEqual(source.payload["truth_status"], "unverified")
        edges = self.graph.neighbors(result["artifact_node_id"])
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["relation"], "derived_from")
        self.assertFalse(edges[0]["payload"]["asserts_truth"])
        self.assertEqual(self.note.read_text()[:10], "# Research")

    def test_duplicate_exact_approval_is_idempotent(self):
        preview = self.preview()
        first = self.promotion.promote(preview, operator_approve=lambda _: True)
        second = self.promotion.promote(preview, operator_approve=lambda _: True)
        self.assertEqual(first, second)
        self.assertEqual(len(self.registry.artifact_history("project", preview["logical_path"])), 1)
        self.assertEqual(len(self.graph.export_snapshot()["nodes"]), 2)

    def test_stale_note_rejected_before_approval(self):
        preview = self.preview()
        self.note.write_text("# Changed\n")
        calls = []
        with self.assertRaises(RuntimeError):
            self.promotion.promote(preview, operator_approve=lambda x: calls.append(x) or True)
        self.assertEqual(calls, [])
        self.assertEqual(self.registry.artifact_history("project", preview["logical_path"]), [])

    def test_mutation_during_approval_is_rejected(self):
        preview = self.preview()
        def changed(_preview):
            self.note.write_text("# changed during approval\n")
            return True
        with self.assertRaises(RuntimeError):
            self.promotion.promote(preview, operator_approve=changed)
        self.assertEqual(self.graph.export_snapshot()["nodes"], [])
        self.assertEqual(self.registry.artifact_history("project", preview["logical_path"]), [])

    def test_tampered_preview_rejected_before_callback(self):
        preview = self.preview()
        bad = dict(preview, source_sha256="a" * 64)
        calls = []
        with self.assertRaises(ValueError):
            self.promotion.promote(bad, operator_approve=lambda x: calls.append(x) or True)
        self.assertFalse(calls)

    def test_unregistered_project_denied_without_creating_project(self):
        with self.assertRaises(KeyError):
            self.promotion.promote(
                self.promotion.preview("new-project", "Research.md"),
                operator_approve=lambda _: True,
            )
        with self.assertRaises(KeyError):
            self.registry.artifact_history("new-project", "anything")

    def test_disallowed_note_cannot_be_previewed(self):
        secret = self.vault / ".obsidian"
        secret.mkdir()
        (secret / "private.md").write_text("do not ingest")
        for path in ("../outside.md", ".obsidian/private.md", "missing.md"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.promotion.preview("project", path)

    def test_callback_must_return_actual_boolean_true(self):
        preview = self.preview()
        for bogus in (1, "approved", [], {}):
            with self.subTest(value=bogus), self.assertRaises(PermissionError):
                self.promotion.promote(preview, operator_approve=lambda _: bogus)
        self.assertEqual(self.graph.export_snapshot()["nodes"], [])


if __name__ == "__main__":
    unittest.main()
