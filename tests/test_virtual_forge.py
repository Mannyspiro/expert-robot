import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from virtual_forge import ForgeError, MergeConflict, VirtualForge, _three_way_text


class VirtualForgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.forge = VirtualForge(str(Path(self.tmp.name) / "forge.sqlite3"))

    def tearDown(self):
        self.forge.close()
        self.tmp.cleanup()

    def test_branch_commit_and_immutable_history(self):
        root = self.forge._head("main")
        self.forge.commit("main", {"src/main.py": "print('base')\n"}, "add source")
        self.forge.create_branch("feature")
        head = self.forge._head("feature")
        commit = self.forge.commit(
            "feature", {"src/main.py": "print('feature')\n", "docs/notes.md": "idea\n"},
            "feature work", expected_head=head,
        )
        self.assertNotEqual(commit, root)
        self.assertEqual(self.forge.read_file("feature", "src/main.py"), "print('feature')\n")
        self.assertEqual(self.forge.read_file("main", "src/main.py"), "print('base')\n")
        with self.assertRaisesRegex(ForgeError, "stale branch head"):
            self.forge.commit("feature", {"x.txt": "x"}, "stale", expected_head=head)

    def test_three_way_merge_non_overlapping_edits(self):
        self.assertEqual(
            _three_way_text("a\nb\nc\n", "A\nb\nc\n", "a\nb\nC\n"),
            "A\nb\nC\n",
        )
        self.assertIsNone(
            _three_way_text("a\nb\n", "a\nours\n", "a\ntheirs\n")
        )

    def test_pull_request_merges_and_records_two_parents(self):
        self.forge.commit("main", {"one.txt": "one\ntwo\nthree\n"}, "base")
        self.forge.create_branch("feature")
        self.forge.commit("feature", {"one.txt": "ONE\ntwo\nthree\n"}, "feature edit")
        self.forge.commit("main", {"one.txt": "one\ntwo\nTHREE\n"}, "main edit")
        pr = self.forge.open_pull_request("feature", "main", "non-overlapping work")
        merged = self.forge.merge_pull_request(pr)
        self.assertEqual(self.forge.read_file("main", "one.txt"), "ONE\ntwo\nTHREE\n")
        parents = self.forge.db.execute(
            "SELECT parent1,parent2 FROM commits WHERE commit_id=?", (merged,)
        ).fetchone()
        self.assertIsNotNone(parents[0])
        self.assertIsNotNone(parents[1])

    def test_pull_request_rejects_overlapping_conflict_without_moving_branch(self):
        self.forge.commit("main", {"same.txt": "base\n"}, "base")
        self.forge.create_branch("feature")
        self.forge.commit("feature", {"same.txt": "feature\n"}, "feature edit")
        self.forge.commit("main", {"same.txt": "main\n"}, "main edit")
        pr = self.forge.open_pull_request("feature", "main")
        before = self.forge._head("main")
        with self.assertRaises(MergeConflict):
            self.forge.merge_pull_request(pr)
        self.assertEqual(self.forge._head("main"), before)

    def test_rollback_is_a_new_commit(self):
        original = self.forge.commit("main", {"state.txt": "original"}, "original")
        later = self.forge.commit("main", {"state.txt": "changed"}, "changed")
        rollback = self.forge.rollback_branch("main", original)
        self.assertNotEqual(rollback, original)
        self.assertNotEqual(rollback, later)
        self.assertEqual(self.forge.read_file("main", "state.txt"), "original")

    def test_job_queue_is_idempotent_leased_and_worker_owned(self):
        job = self.forge.enqueue_job("python_tests", {"suite": "unit"}, "tests:unit:v1", 10)
        self.assertEqual(
            self.forge.enqueue_job("python_tests", {"suite": "unit"}, "tests:unit:v1"),
            job,
        )
        claimed = self.forge.claim_job("worker-A", allowed_kinds=["python_tests"])
        self.assertEqual(claimed["job_id"], job)
        self.assertIsNone(self.forge.claim_job("worker-B"))
        with self.assertRaisesRegex(ForgeError, "owned by another worker"):
            self.forge.finish_job(job, "worker-B", {"ok": True}, "forged")
        self.forge.finish_job(job, "worker-A", {"ok": True}, "2 tests passed", ["a" * 64])
        self.assertEqual(self.forge.job(job)["status"], "succeeded")

    def test_job_lease_expiry_allows_reclaim(self):
        job = self.forge.enqueue_job("build", {}, "build:v1")
        self.forge.claim_job("worker-A", lease_seconds=1)
        self.forge.db.execute("UPDATE jobs SET lease_expires=0 WHERE job_id=?", (job,))
        reclaimed = self.forge.claim_job("worker-B", lease_seconds=30)
        self.assertEqual(reclaimed["job_id"], job)
        self.assertEqual(reclaimed["attempt"], 2)

    def test_workspace_export_requires_clean_destination(self):
        self.forge.commit("main", {"src/module.py": "value = 42\n"}, "workspace")
        destination = Path(self.tmp.name) / "workspace"
        self.assertEqual(self.forge.export_snapshot("main", str(destination)), 1)
        self.assertEqual((destination / "src" / "module.py").read_text(), "value = 42\n")
        with self.assertRaisesRegex(ForgeError, "must be empty"):
            self.forge.export_snapshot("main", str(destination))

    def test_identical_shared_patch_is_not_a_merge_conflict(self):
        base = "alpha\nbeta\ngamma\n"
        ours = "ALPHA\nbeta\ngamma\n"
        theirs = "ALPHA\nbeta\nGAMMA\n"
        self.assertEqual(
            _three_way_text(base, ours, theirs),
            "ALPHA\nbeta\nGAMMA\n",
        )

    def test_event_chain_and_path_validation(self):
        self.forge.commit("main", {"src/a.py": "a"}, "add")
        self.assertTrue(self.forge.verify_event_chain())
        with self.assertRaises(ForgeError):
            self.forge.commit("main", {"../escape": "bad"}, "unsafe")

    def test_job_result_retains_logs_and_artifact_digests(self):
        job = self.forge.enqueue_job("lean_compile", {"target": "T"}, "lean:T:v1")
        lease = self.forge.claim_job("lean-worker")
        self.forge.finish_job(job, lease["worker_id"], {"exit_code": 0}, "Lean build ok", ["b" * 64])
        stored = self.forge.job(job)
        self.assertEqual(stored["log_text"], "Lean build ok")
        self.assertIn("b" * 64, stored["artifact_digests_json"])


if __name__ == "__main__":
    unittest.main()
