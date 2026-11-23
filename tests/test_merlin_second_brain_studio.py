"""Real loopback HTTP contracts for opt-in Second Brain note review.

Uses only synthetic public test fixtures. Does not establish secure human
presence against an already-authorized same-user local Python tool.
"""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[1] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
import server


class SecondBrainHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.data = base / "data"
        self.vault = base / "vault"
        self.vault.mkdir()
        self.file = self.vault / "Research.md"
        self.file.write_text("# Research\nThis synthetic note is unverified.\n", encoding="utf-8")
        self.httpd = None
        self.token = ""
        self.start(import_enabled=False)

    def start(self, *, vault=True, import_enabled=False):
        self.httpd = server.create_server(
            data_dir=self.data, start_bundled=False,
            second_brain_vault=self.vault if vault else None,
            second_brain_import=import_enabled,
        )
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        status, payload = self.call("GET", "/api/status")
        self.assertEqual(status, 200)
        self.token = payload["session_token"]

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.thread.join(timeout=3)
            self.httpd = None

    def tearDown(self):
        self.stop()

    def call(self, method, path, value=None, *, token=True, headers=None):
        supplied = dict(headers or {})
        if method == "POST":
            supplied.setdefault("Content-Type", "application/json")
            if token:
                supplied.setdefault("X-Merlin-Token", self.token)
            data = json.dumps({} if value is None else value).encode()
        else:
            data = None
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=8)
        try:
            conn.request(method, path, body=data, headers=supplied)
            response = conn.getresponse()
            raw = response.read()
            if "application/json" in response.getheader("Content-Type", ""):
                return response.status, json.loads(raw)
            return response.status, raw.decode("utf-8")
        finally:
            conn.close()

    def api(self, suffix, value=None, **kwargs):
        return self.call("POST", "/api/second-brain/" + suffix, value, **kwargs)

    def test_read_only_mode_inventory_search_review_but_no_import(self):
        status, info = self.api("status")
        self.assertEqual(status, 200)
        self.assertTrue(info["configured"])
        self.assertFalse(info["import_enabled"])
        status, inv = self.api("inventory")
        self.assertEqual(status, 200)
        self.assertEqual(inv["notes_scanned"], 1)
        self.assertNotIn("synthetic note", json.dumps(inv).lower())
        status, matches = self.api("search", {"query": "synthetic"})
        self.assertEqual(status, 200)
        self.assertEqual([r["path"] for r in matches["results"]], ["Research.md"])
        status, preview = self.api("review", {"path": "Research.md"})
        self.assertEqual(status, 200)
        self.assertIn("synthetic note", preview["content"])
        self.assertIsNone(preview["import"])
        self.assertFalse(preview["source_claims_verified"])
        status, _ = self.api("import", {"nonce": "x", "preview_id": "y", "confirm": True})
        self.assertEqual(status, 403)
        self.assertEqual(self.httpd.app.store.registry.artifact_paths(self.httpd.app.store.PROJECT), [])

    def test_private_note_endpoints_require_real_local_session(self):
        for action, body in (("inventory", {}), ("search", {"query": "Research"}),
                             ("review", {"path": "Research.md"})):
            with self.subTest(action=action):
                self.assertEqual(self.api(action, body, token=False)[0], 403)
                self.assertEqual(self.api(action, body, headers={"Origin": "https://attacker.example"})[0], 403)
                self.assertEqual(self.api(action, body, headers={"Host": "attacker.example"})[0], 403)
                self.assertEqual(self.api(action, body, headers={"Sec-Fetch-Site": "cross-site"})[0], 403)

    def test_import_opt_in_and_one_time_exact_ui_confirmation(self):
        self.stop()
        self.start(import_enabled=True)
        status, preview = self.api("review", {"path": "Research.md"})
        self.assertEqual(status, 200)
        permit = preview["import"]
        self.assertIsNotNone(permit)
        body = {"nonce": permit["nonce"], "preview_id": permit["preview_id"], "confirm": True}
        for invalid in ({**body, "confirm": 1}, {**body, "confirm": False},
                        {**body, "preview_id": "incorrect"},
                        {**body, "nonce": "incorrect"}):
            with self.subTest(invalid=invalid):
                self.assertIn(self.api("import", invalid)[0], (400, 403))
        # Incorrect nonce does not consume the valid pending review.
        # Incorrect preview ID consumes it intentionally: create a fresh review.
        self.assertEqual(self.api("review", {"path": "Research.md"})[0], 200)
        permit = self.api("review", {"path": "Research.md"})[1]["import"]
        body = {"nonce": permit["nonce"], "preview_id": permit["preview_id"], "confirm": True}
        status, imported = self.api("import", body)
        self.assertEqual(status, 200, imported)
        self.assertEqual(imported["inspection"]["status"], "complete_unverified")
        self.assertEqual(imported["receipt"]["status"], "imported_unverified")
        self.assertFalse(imported["receipt"]["note_truth_approved"])
        self.assertEqual(self.api("import", body)[0], 403)
        self.assertEqual(self.file.read_text(), "# Research\nThis synthetic note is unverified.\n")

    def test_note_change_invalidates_review_and_persistent_registry_is_unmodified(self):
        self.stop()
        self.start(import_enabled=True)
        _, preview = self.api("review", {"path": "Research.md"})
        permit = preview["import"]
        self.file.write_text("# modified after review\n", encoding="utf-8")
        status, error = self.api("import", {
            "nonce": permit["nonce"], "preview_id": permit["preview_id"], "confirm": True})
        self.assertNotEqual(status, 200, error)
        self.assertEqual(self.httpd.app.store.registry.artifact_paths(self.httpd.app.store.PROJECT), [])

    def test_discard_or_server_restart_revokes_pending_review(self):
        self.stop()
        self.start(import_enabled=True)
        _, review = self.api("review", {"path": "Research.md"})
        nonce = review["import"]["nonce"]
        self.assertEqual(self.api("discard", {"nonce": nonce})[0], 200)
        self.assertEqual(self.api("import", {
            "nonce": nonce, "preview_id": review["import"]["preview_id"], "confirm": True})[0], 403)
        _, fresh = self.api("review", {"path": "Research.md"})
        old_token = self.token
        self.stop()
        self.start(import_enabled=True)
        self.assertNotEqual(old_token, self.token)
        body = {"nonce": fresh["import"]["nonce"], "preview_id": fresh["import"]["preview_id"], "confirm": True}
        self.assertEqual(self.api("import", body)[0], 403)
        self.assertEqual(self.api("import", body, headers={"X-Merlin-Token": old_token})[0], 403)

    def test_oversize_review_is_refused_and_no_durable_import(self):
        self.file.write_text("z" * (16 * 1024 + 2), encoding="utf-8")
        status, _ = self.api("review", {"path": "Research.md"})
        self.assertNotEqual(status, 200)
        self.assertEqual(self.httpd.app.store.registry.artifact_paths(self.httpd.app.store.PROJECT), [])

    def test_disabled_by_default_and_wrong_configuration(self):
        self.stop()
        self.start(vault=False)
        self.assertEqual(self.api("status"), (200, {
            "configured": False, "import_enabled": False, "read_only_default": True}))
        self.assertEqual(self.api("inventory")[0], 403)
        with self.assertRaises(ValueError):
            server.create_server(data_dir=self.data, start_bundled=False, second_brain_import=True)
        with self.assertRaises(ValueError):
            server.create_server(data_dir=self.vault, start_bundled=False,
                                 second_brain_vault=self.vault)

    def test_note_review_does_not_expose_model_tool(self):
        from engine import SYSTEM
        from tools import ToolSet
        self.assertNotIn("/api/second-brain", SYSTEM)
        self.assertNotIn("second_brain_import", SYSTEM)
        status, _ = self.call("POST", "/api/tool", {
            "tool": "second_brain_import", "args": {"path": "Research.md"}})
        self.assertEqual(status, 403)

    def test_local_ui_route_has_review_controls_and_noninteractive_raw_notes(self):
        status, html = self.call("GET", "/second-brain/")
        self.assertEqual(status, 200)
        for needle in ('id="accept"', 'id="discard"', 'id="source"',
                       'id="phrase"', 'id="ack"', "textContent"):
            self.assertIn(needle, html)
        self.assertNotIn("This synthetic note", html)


if __name__ == "__main__":
    unittest.main()
