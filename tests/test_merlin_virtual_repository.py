import tempfile
import unittest
from pathlib import Path

from python.merlin.virtual_repository import VirtualGitError, VirtualRepository


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
