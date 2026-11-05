import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from merlin.app import _build_optional_hud_runtime
from merlin.project_registry import MerlinRegistry
from scripts.init_merlin_dashboard_stores import initialize


class MerlinDashboardBootstrapTests(unittest.TestCase):
    def test_bootstrapped_paths_mount_read_only_hud_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize(directory, project_id="merlin-live", project_name="Merlin Live")
            environment = {
                "MERLIN_REGISTRY_ROOT": str(root / "registry"),
                "MERLIN_GRAPH_DB_PATH": str(root / "knowledge-graph.sqlite3"),
                "MERLIN_OUTBOX_DB_PATH": str(root / "event-outbox.sqlite3"),
                "MERLIN_HYPOTHESES_DB_PATH": str(root / "hypotheses.sqlite3"),
                "MERLIN_DB_PATH": str(root / "events.sqlite3"),
            }
            with patch.dict(os.environ, environment):
                runtime = _build_optional_hud_runtime()
            self.assertIsNotNone(runtime)
            response = {}
            def start(status, headers):
                response["status"] = status
                response["headers"] = dict(headers)
            body = b"".join(runtime.application(
                {"PATH_INFO": "/api/hud/graph", "REQUEST_METHOD": "GET"},
                start,
            ))
            self.assertEqual(response["status"], "200 OK")
            payload = json.loads(body)
            self.assertEqual(payload["schema_version"], "1.0")
            response.clear()
            runtime.application(
                {"PATH_INFO": "/api/hud/graph", "REQUEST_METHOD": "POST"},
                start,
            )
            self.assertEqual(response["status"], "405 Method Not Allowed")

    def test_existing_project_metadata_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = MerlinRegistry(root / "registry")
            registry.register_project(
                "merlin-existing", "Existing Project",
                metadata={"owner": "preserve-me"},
            )
            initialize(directory, project_id="merlin-existing", project_name="Do Not Replace")
            inventory = registry.inventory("merlin-existing")
            self.assertEqual(inventory["name"], "Existing Project")
            self.assertEqual(inventory["metadata"], {"owner": "preserve-me"})

    def test_initializes_canonical_read_only_dashboard_stores_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            first = initialize(directory, project_id="merlin-test", project_name="Merlin Test")
            second = initialize(directory, project_id="merlin-test", project_name="Merlin Test")

            root = Path(directory)
            self.assertEqual(first["project_id"], "merlin-test")
            self.assertEqual(second["project_id"], "merlin-test")
            self.assertTrue((root / "registry" / "merlin.sqlite3").is_file())
            self.assertTrue((root / "knowledge-graph.sqlite3").is_file())
            self.assertTrue((root / "event-outbox.sqlite3").is_file())
            self.assertTrue((root / "hypotheses.sqlite3").is_file())
            self.assertTrue((root / "merlin-hud.env").is_file())
            self.assertEqual(first["read_only_dashboard"], "http://127.0.0.1:8765/hud")

            env = (root / "merlin-hud.env").read_text(encoding="utf-8")
            self.assertIn("MERLIN_REGISTRY_ROOT=", env)
            self.assertIn("MERLIN_GRAPH_DB_PATH=", env)
            self.assertIn("MERLIN_OUTBOX_DB_PATH=", env)
            self.assertIn("MERLIN_HYPOTHESES_DB_PATH=", env)
            inventory = MerlinRegistry(root / "registry").inventory("merlin-test")
            self.assertEqual(inventory["project_id"], "merlin-test")


if __name__ == "__main__":
    unittest.main()
