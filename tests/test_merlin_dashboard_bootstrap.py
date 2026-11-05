import tempfile
import unittest
from pathlib import Path

from merlin.project_registry import MerlinRegistry
from scripts.init_merlin_dashboard_stores import initialize


class MerlinDashboardBootstrapTests(unittest.TestCase):
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
            self.assertEqual(inventory["project"]["project_id"], "merlin-test")


if __name__ == "__main__":
    unittest.main()
