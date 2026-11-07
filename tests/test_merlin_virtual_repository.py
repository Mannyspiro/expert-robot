import json
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from pathlib import Path

from python.merlin.virtual_repository import VirtualGitError, VirtualRepository
from python.merlin.app import EventStore, make_handler


class VirtualRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "forge.sqlite3"
        self.repo = VirtualRepository(self.db)
        self.initial = self.repo.initialize({
            "README.md": "# Merlin\n",
            "src/core.py": "VERSION = 1\n",
        })

    def tearDown(self):
        self.temp.cleanup()

    def test_content_addressed_commit_and_restart_persistence(self):
        branch = self.repo.create_branch("feature/one")
        commit = self.repo.commit("feature/one", "add feature", {
            "src/feature.py": "FEATURE = True\n",
        })
        digest = commit["commit_id"]
        reopened = VirtualRepository(self.db)
        self.assertEqual(reopened.read_file("feature/one", "src/feature.py"),
                         b"FEATURE = True\n")
        self.assertEqual({row["name"]: row["commit_id"] for row in reopened.branches()}["feature/one"], digest)
        self.assertEqual(branch["commit_id"], self.initial["commit_id"])

    def test_three_way_merge_combines_non_overlapping_changes(self):
        self.repo.create_branch("feature/docs")
        self.repo.commit("feature/docs", "update docs", {"README.md": "# Merlin Forge\n"})
        self.repo.commit("main", "add runtime module", {"src/runtime.py": "READY = True\n"})
        pr = self.repo.open_pull_request("feature/docs", "main", "Merge docs")
        merged = self.repo.merge_pull_request(pr["pr_id"])
        self.assertEqual(merged["status"], "merged")
        self.assertEqual(self.repo.read_file("main", "README.md"), b"# Merlin Forge\n")
        self.assertEqual(self.repo.read_file("main", "src/runtime.py"), b"READY = True\n")
        self.assertEqual(self.repo.pull_requests()[0]["status"], "merged")

    def test_three_way_merge_reports_same_path_conflict_without_moving_target(self):
        self.repo.create_branch("feature/conflict")
        self.repo.commit("feature/conflict", "feature edit", {"src/core.py": "VERSION = 2\n"})
        self.repo.commit("main", "main edit", {"src/core.py": "VERSION = 3\n"})
        pr = self.repo.open_pull_request("feature/conflict", "main", "Conflicting edit")
        before = {row["name"]: row["commit_id"] for row in self.repo.branches()}["main"]
        result = self.repo.merge_pull_request(pr["pr_id"])
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["conflicts"], ["src/core.py"])
        after = {row["name"]: row["commit_id"] for row in self.repo.branches()}
        self.assertEqual(after["main"], before)
        self.assertEqual(self.repo.pull_requests()[0]["status"], "open")

    def test_rebase_replays_nonconflicting_changes_onto_updated_target(self):
        self.repo.create_branch("feature/rebase")
        self.repo.commit("feature/rebase", "feature docs", {"README.md": "# Feature docs\n"})
        target = self.repo.commit("main", "target adds module", {"src/runtime.py": "READY = True\n"})
        result = self.repo.rebase_branch("feature/rebase", "main")
        self.assertEqual(result["status"], "rebased")
        self.assertEqual(result["replayed_commits"], 1)
        self.assertEqual(self.repo.read_file("feature/rebase", "README.md"), b"# Feature docs\n")
        self.assertEqual(self.repo.read_file("feature/rebase", "src/runtime.py"), b"READY = True\n")
        with sqlite3.connect(self.db) as db:
            parent = db.execute("SELECT parent1 FROM commits WHERE commit_id=?",
                                (result["commit_id"],)).fetchone()[0]
        self.assertEqual(parent, target["commit_id"])
        self.assertEqual(self.repo.events()[0]["kind"], "branch.rebased")

    def test_rebase_conflict_preserves_original_branch_ref(self):
        self.repo.create_branch("feature/rebase-conflict")
        self.repo.commit("feature/rebase-conflict", "feature version", {"src/core.py": "VERSION = 2\n"})
        self.repo.commit("main", "target version", {"src/core.py": "VERSION = 3\n"})
        before = {row["name"]: row["commit_id"] for row in self.repo.branches()}["feature/rebase-conflict"]
        result = self.repo.rebase_branch("feature/rebase-conflict", "main")
        after = {row["name"]: row["commit_id"] for row in self.repo.branches()}["feature/rebase-conflict"]
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["conflicts"], ["src/core.py"])
        self.assertEqual(after, before)

    def test_rebase_rejects_unknown_ref_and_merge_commit_replay(self):
        with self.assertRaises(KeyError):
            self.repo.rebase_branch("main", "missing")
        self.repo.create_branch("feature/merge-rebase")
        self.repo.create_branch("other/merge-rebase")
        self.repo.commit("feature/merge-rebase", "feature commit", {"a.txt": "a"})
        self.repo.commit("other/merge-rebase", "other commit", {"b.txt": "b"})
        pr = self.repo.open_pull_request("other/merge-rebase", "feature/merge-rebase", "make merge commit")
        self.assertEqual(self.repo.merge_pull_request(pr["pr_id"])["status"], "merged")
        with self.assertRaises(VirtualGitError):
            self.repo.rebase_branch("feature/merge-rebase", "main")

    def test_branch_rollback_is_audited_and_restores_content(self):
        first = self.initial["commit_id"]
        self.repo.commit("main", "temporary edit", {"src/core.py": "VERSION = 9\n"})
        result = self.repo.rollback_branch("main", first)
        self.assertEqual(result["commit_id"], first)
        self.assertEqual(self.repo.read_file("main", "src/core.py"), b"VERSION = 1\n")
        self.assertEqual(self.repo.events()[0]["kind"], "branch.rollback")

    def test_deletions_are_merged_and_recorded(self):
        self.repo.create_branch("feature/remove")
        self.repo.commit("feature/remove", "remove source", {"src/core.py": None})
        pr = self.repo.open_pull_request("feature/remove", "main", "Remove file")
        self.assertEqual(self.repo.merge_pull_request(pr["pr_id"])["status"], "merged")
        with self.assertRaises(KeyError):
            self.repo.read_file("main", "src/core.py")

    def test_rejects_path_traversal_and_oversized_event_queries(self):
        with self.assertRaises(VirtualGitError):
            self.repo.commit("main", "bad path", {"../outside.txt": "no"})
        with self.assertRaises(VirtualGitError):
            self.repo.events(1001)

    def test_forge_http_api_exposes_status_branch_commit_pr_and_merge(self):
        event_store = EventStore(Path(self.temp.name) / "api-events.sqlite3")
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(event_store))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def get(path):
            with urlopen(base + path, timeout=5) as response:
                return json.loads(response.read())

        def post(path, payload):
            request = Request(base + path, data=json.dumps(payload).encode("utf-8"),
                              headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=5) as response:
                return json.loads(response.read())

        try:
            status = get("/api/forge/status")
            self.assertEqual(status["schema"], "merlin-forge-status/1")
            self.assertEqual(status["runner_execution"], "not_performed")
            self.assertTrue(any(item["name"] == "main" for item in status["branches"]))

            post("/api/forge/branches", {"name": "feature/api"})
            commit = post("/api/forge/commits", {
                "branch": "feature/api", "message": "update forge API",
                "changes": {"README.md": "# Merlin Forge API\n"},
            })
            self.assertEqual(commit["schema"], "merlin-forge-commit/1")
            pr = post("/api/forge/pulls", {
                "source_branch": "feature/api", "target_branch": "main",
                "title": "Forge API integration",
            })
            merged = post(f"/api/forge/pulls/{pr['pr_id']}/merge", {})
            self.assertEqual(merged["status"], "merged")
            file_result = get("/api/forge/file?ref=main&path=README.md")
            self.assertEqual(file_result["content_utf8"], "# Merlin Forge API\n")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_blobs_commits_and_events_are_immutable(self):
        commit_id = self.initial["commit_id"]
        event_id = self.repo.events()[0]["event_id"]
        with sqlite3.connect(self.db) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE commits SET message='tampered' WHERE commit_id=?", (commit_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM commits WHERE commit_id=?", (commit_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE events SET kind='tampered' WHERE event_id=?", (event_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM events WHERE event_id=?", (event_id,))
            blob = db.execute("SELECT digest FROM blobs LIMIT 1").fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM blobs WHERE digest=?", (blob,))

    def test_commit_history_is_append_only_and_auditable(self):
        self.repo.create_branch("feature/audit")
        self.repo.commit("feature/audit", "one", {"a.txt": "a"})
        self.repo.commit("feature/audit", "two", {"b.txt": "b"})
        events = self.repo.events(20)
        kinds = [event["kind"] for event in events]
        self.assertIn("repository.initialized", kinds)
        self.assertIn("branch.created", kinds)
        self.assertEqual(kinds.count("commit.created"), 2)


if __name__ == "__main__":
    unittest.main()
