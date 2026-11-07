import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
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

    def pass_main_checks(self, commit_id):
        # Test-only trusted-receipt fixture. Production code has no public
        # method to elevate local check records to VERIFIED.
        for check_name in ("python.compile", "python.unified_tests", "hud.javascript_syntax"):
            local = self.repo.record_check_result(
                commit_id, check_name, "success",
                "local-" + commit_id[:10] + "-" + check_name,
                "unit-test-runner", "PASS: " + check_name,
            )
            receipt = {
                "commit_id": commit_id, "check_name": check_name,
                "conclusion": "success", "run_id": "cace-test-" + commit_id[:10] + "-" + check_name,
                "runner_id": "cace-test-signer", "log_sha256": local["log_sha256"],
                "verification_status": "VERIFIED", "promotion_authorized": True,
                "cace_receipt_id": "test-receipt-" + check_name,
            }
            with sqlite3.connect(self.db) as db:
                db.execute("""INSERT INTO check_results
                    (commit_id,check_name,conclusion,run_id,runner_id,log_digest,result_json,recorded_at)
                    VALUES(?,?,?,?,?,?,?,?)""",
                    (commit_id, check_name, "success", receipt["run_id"],
                     receipt["runner_id"], local["log_sha256"],
                     json.dumps(receipt, sort_keys=True), time.time() + 1))

    def test_concurrent_first_start_initialization_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "concurrent-forge.sqlite3"
            repositories = [VirtualRepository(database), VirtualRepository(database)]
            barrier = threading.Barrier(2)
            failures = []

            def initialize(repo):
                barrier.wait(timeout=5)
                if not repo.branches():
                    try:
                        repo.initialize({"README.md": "# concurrent\n"})
                    except VirtualGitError:
                        if not repo.branches():
                            failures.append("initialization failed without a winner")

            threads = [threading.Thread(target=initialize, args=(repo,)) for repo in repositories]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(failures, [])
            self.assertEqual([row["name"] for row in repositories[0].branches()], ["main"])

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

    def test_virtual_ci_queue_idempotency_lease_fencing_and_logs(self):
        job = self.repo.enqueue_job(self.initial["commit_id"], "python.compile", "compile-once")
        replay = self.repo.enqueue_job(self.initial["commit_id"], "python.compile", "compile-once")
        self.assertEqual(job["job_id"], replay["job_id"])
        self.assertTrue(replay["idempotent_replay"])
        first = self.repo.claim_job("runner-a", lease_seconds=15,
                                    job_types=["python.compile"])
        self.assertEqual(first["job_id"], job["job_id"])
        self.assertEqual(first["attempts"], 1)
        self.assertIsNone(self.repo.claim_job("runner-b", job_types=["python.compile"]))
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE virtual_jobs SET lease_expires_at=? WHERE job_id=?",
                       (time.time() - 1, job["job_id"]))
        second = self.repo.claim_job("runner-b", lease_seconds=30,
                                     job_types=["python.compile"])
        self.assertEqual(second["job_id"], job["job_id"])
        self.assertEqual(second["attempts"], 2)
        with self.assertRaises(VirtualGitError):
            self.repo.heartbeat_job(job["job_id"], "runner-a", first["lease_token"])
        with self.assertRaises(VirtualGitError):
            self.repo.complete_job(job["job_id"], "runner-a", first["lease_token"],
                                   "succeeded", {"exit_code": 0}, "stale")
        self.repo.heartbeat_job(job["job_id"], "runner-b", second["lease_token"])
        completed = self.repo.complete_job(
            job["job_id"], "runner-b", second["lease_token"],
            "succeeded", {"exit_code": 0, "test_count": 0}, "compile complete",
        )
        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(self.repo.read_job_log(job["job_id"]), b"compile complete")
        self.assertEqual(self.repo.get_job(job["job_id"])["result"]["exit_code"], 0)
        self.assertEqual(self.repo.check_results(self.initial["commit_id"]), [])

    def test_virtual_ci_queue_serializes_competing_claims(self):
        job = self.repo.enqueue_job(self.initial["commit_id"], "python.unified_tests",
                                    "unified-tests-once")
        barrier = threading.Barrier(2)
        claimed = []

        def claim(runner_id):
            barrier.wait(timeout=5)
            claimed.append(self.repo.claim_job(runner_id, job_types=["python.unified_tests"]))

        threads = [threading.Thread(target=claim, args=("runner-" + str(i),)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        winners = [item for item in claimed if item is not None]
        self.assertEqual(len(winners), 1)
        self.assertEqual(winners[0]["job_id"], job["job_id"])

    def test_virtual_ci_job_fails_after_maximum_expired_leases(self):
        job = self.repo.enqueue_job(self.initial["commit_id"], "hud.javascript_syntax",
                                    "hud-once", max_attempts=1)
        claim = self.repo.claim_job("runner-a", job_types=["hud.javascript_syntax"])
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE virtual_jobs SET lease_expires_at=? WHERE job_id=?",
                       (time.time() - 1, job["job_id"]))
        self.assertIsNone(self.repo.claim_job("runner-b", job_types=["hud.javascript_syntax"]))
        failed = self.repo.get_job(job["job_id"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["result"]["error"], "lease_expired")

    def test_export_commit_materializes_verified_workspace(self):
        branch = self.repo.create_branch("feature/export")
        commit = self.repo.commit("feature/export", "export workspace", {
            "src/main.py": "print('merlin')\\n",
            "docs/README.md": "# export\\n",
        })
        workspace = Path(self.temp.name) / "workspace"
        manifest = self.repo.export_commit(commit["commit_id"], workspace)
        self.assertEqual(manifest["commit_id"], commit["commit_id"])
        self.assertEqual(manifest["file_count"], 4)
        self.assertEqual((workspace / "src/main.py").read_text(), "print('merlin')\\n")
        self.assertEqual((workspace / "docs/README.md").read_text(), "# export\\n")
        with self.assertRaises(VirtualGitError):
            self.repo.export_commit(commit["commit_id"], workspace)
        with self.assertRaises(VirtualGitError):
            self.repo.export_commit(commit["commit_id"], Path(self.temp.name) / "limited",
                                    max_total_bytes=1)

    def test_integrity_checked_backup_restores_repository_state(self):
        self.repo.create_branch("feature/backup")
        self.repo.commit("feature/backup", "backup candidate", {
            "src/backup.py": "BACKUP_READY = True\\n",
        })
        backup_path = Path(self.temp.name) / "backups" / "merlin-backup.sqlite3"
        result = self.repo.backup_to(backup_path)
        self.assertTrue(result["integrity"]["ok"])
        self.assertEqual(list(backup_path.parent.glob(".*.tmp")), [])
        restored = VirtualRepository(backup_path)
        self.assertTrue(restored.integrity_report()["ok"])
        self.assertEqual(
            restored.read_file("feature/backup", "src/backup.py"),
            b"BACKUP_READY = True\\n",
        )
        with self.assertRaises(VirtualGitError):
            self.repo.backup_to(backup_path)

    def test_integrity_report_rejects_malformed_commit_tree(self):
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO commits VALUES(?,?,?,?,?,?)",
                       ("0" * 64, None, None, "[]", "corrupt tree", time.time()))
        report = self.repo.integrity_report()
        self.assertFalse(report["ok"])
        self.assertIn("invalid_commit_tree:" + "0" * 64, report["problems"])

    def test_integrity_report_detects_blob_tampering(self):
        with sqlite3.connect(self.db) as db:
            db.execute("DROP TRIGGER virtual_blobs_no_update")
            db.execute("UPDATE blobs SET content=? WHERE digest=(SELECT digest FROM blobs LIMIT 1)",
                       (b"tampered",))
        report = self.repo.integrity_report()
        self.assertFalse(report["ok"])
        self.assertTrue(any(item.startswith("blob:") for item in report["problems"]))

    def test_three_way_merge_combines_non_overlapping_changes(self):
        self.repo.create_branch("feature/docs")
        self.repo.commit("feature/docs", "update docs", {"README.md": "# Merlin Forge\n"})
        self.repo.commit("main", "add runtime module", {"src/runtime.py": "READY = True\n"}, allow_protected=True)
        pr = self.repo.open_pull_request("feature/docs", "main", "Merge docs")
        self.pass_main_checks(pr["head_commit"])
        merged = self.repo.merge_pull_request(pr["pr_id"])
        self.assertEqual(merged["status"], "merged")
        self.assertEqual(self.repo.read_file("main", "README.md"), b"# Merlin Forge\n")
        self.assertEqual(self.repo.read_file("main", "src/runtime.py"), b"READY = True\n")
        self.assertEqual(self.repo.pull_requests()[0]["status"], "merged")

    def test_main_merge_requires_successful_checks_for_exact_pr_head(self):
        self.repo.create_branch("feature/protected")
        self.repo.commit("feature/protected", "protected change", {"README.md": "# protected\n"})
        pr = self.repo.open_pull_request("feature/protected", "main", "Protected merge")
        blocked = self.repo.merge_pull_request(pr["pr_id"])
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(set(blocked["missing_checks"]), {
            "python.compile", "python.unified_tests", "hud.javascript_syntax",
        })
        self.pass_main_checks(self.initial["commit_id"])
        still_blocked = self.repo.merge_pull_request(pr["pr_id"])
        self.assertEqual(still_blocked["status"], "blocked")
        self.pass_main_checks(pr["head_commit"])
        merged = self.repo.merge_pull_request(pr["pr_id"])
        self.assertEqual(merged["status"], "merged")

    def test_unverified_local_success_cannot_satisfy_protected_merge(self):
        self.repo.create_branch("feature/unverified")
        self.repo.commit("feature/unverified", "local-only checks", {"README.md": "# local\\n"})
        pr = self.repo.open_pull_request("feature/unverified", "main", "Unverified checks")
        for check_name in ("python.compile", "python.unified_tests", "hud.javascript_syntax"):
            self.repo.record_check_result(
                pr["head_commit"], check_name, "success",
                "unverified-" + check_name, "local-runner", "success",
            )
        result = self.repo.merge_pull_request(pr["pr_id"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(set(result["unverified_checks"]), {
            "python.compile", "python.unified_tests", "hud.javascript_syntax",
        })
        self.assertEqual(self.repo.pull_requests("open")[0]["status"], "open")

    def test_malformed_latest_receipt_cannot_satisfy_merge(self):
        self.repo.create_branch("feature/malformed")
        self.repo.commit("feature/malformed", "malformed check metadata", {"README.md": "# malformed\\n"})
        pr = self.repo.open_pull_request("feature/malformed", "main", "Malformed receipt")
        first = None
        for check_name in ("python.compile", "python.unified_tests", "hud.javascript_syntax"):
            result = self.repo.record_check_result(
                pr["head_commit"], check_name, "success",
                "malformed-base-" + check_name, "local-runner", "success",
            )
            if check_name == "python.compile":
                first = result
        with sqlite3.connect(self.db) as db:
            db.execute("""INSERT INTO check_results
                (commit_id,check_name,conclusion,run_id,runner_id,log_digest,result_json,recorded_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (pr["head_commit"], "python.compile", "success", "malformed-latest",
                 "unknown-runner", first["log_sha256"], "not-json", time.time() + 10))
        result = self.repo.merge_pull_request(pr["pr_id"])
        self.assertEqual(result["status"], "blocked")
        self.assertIn("python.compile", result["unverified_checks"])

    def test_check_receipts_are_idempotent_and_immutable(self):
        result = self.repo.record_check_result(
            self.initial["commit_id"], "python.compile", "success",
            "run-check-1", "runner-1", "compile passed",
        )
        replay = self.repo.record_check_result(
            self.initial["commit_id"], "python.compile", "success",
            "run-check-1", "runner-1", "compile passed",
        )
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["verification_status"], "UNVERIFIED")
        self.assertFalse(replay["promotion_authorized"])
        self.assertEqual(result["log_sha256"], replay["log_sha256"])
        self.assertEqual(self.repo.read_check_log(result["check_id"]), b"compile passed")
        with self.assertRaises(VirtualGitError):
            self.repo.record_check_result(
                self.initial["commit_id"], "python.compile", "failure",
                "run-check-1", "runner-1", "different outcome",
            )
        with sqlite3.connect(self.db) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE check_results SET conclusion='failure' WHERE check_id=?",
                           (result["check_id"],))

    def test_legacy_or_malformed_check_metadata_fails_closed(self):
        local = self.repo.record_check_result(
            self.initial["commit_id"], "hud.javascript_syntax", "success",
            "legacy-source", "legacy-runner", "old log",
        )
        with sqlite3.connect(self.db) as db:
            for run_id, raw in (("legacy-json", "{}"), ("malformed-json", "not-json")):
                db.execute("""INSERT INTO check_results
                    (commit_id,check_name,conclusion,run_id,runner_id,log_digest,result_json,recorded_at)
                    VALUES(?,?,?,?,?,?,?,?)""",
                    (self.initial["commit_id"], "hud.javascript_syntax", "success",
                     run_id, "legacy-runner", local["log_sha256"], raw, time.time() + 1))
        rows = self.repo.check_results(self.initial["commit_id"])
        legacy_rows = [row for row in rows if row["run_id"] in {"legacy-json", "malformed-json"}]
        self.assertEqual(len(legacy_rows), 2)
        self.assertTrue(all(row["verification_status"] == "UNVERIFIED" for row in legacy_rows))
        self.assertTrue(all(row["promotion_authorized"] is False for row in legacy_rows))

    def test_pull_request_reports_current_head_after_branch_advances(self):
        self.repo.create_branch("feature/moving-head")
        self.repo.commit("feature/moving-head", "first", {"a.txt": "one"})
        pr = self.repo.open_pull_request("feature/moving-head", "main", "Moving head")
        original_head = pr["head_commit"]
        next_commit = self.repo.commit("feature/moving-head", "second", {"b.txt": "two"})
        current = self.repo.pull_requests("open")[0]
        self.assertEqual(current["head_commit"], original_head)
        self.assertEqual(current["current_head_commit"], next_commit["commit_id"])
        self.assertNotEqual(current["current_head_commit"], current["head_commit"])

    def test_three_way_merge_reports_same_path_conflict_without_moving_target(self):
        self.repo.create_branch("feature/conflict")
        self.repo.commit("feature/conflict", "feature edit", {"src/core.py": "VERSION = 2\n"})
        self.repo.commit("main", "main edit", {"src/core.py": "VERSION = 3\n"}, allow_protected=True)
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
        target = self.repo.commit("main", "target adds module", {"src/runtime.py": "READY = True\n"}, allow_protected=True)
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
        self.repo.commit("main", "target version", {"src/core.py": "VERSION = 3\n"}, allow_protected=True)
        before = {row["name"]: row["commit_id"] for row in self.repo.branches()}["feature/rebase-conflict"]
        result = self.repo.rebase_branch("feature/rebase-conflict", "main")
        after = {row["name"]: row["commit_id"] for row in self.repo.branches()}["feature/rebase-conflict"]
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["conflicts"], ["src/core.py"])
        self.assertEqual(after, before)

    def test_rebase_rejects_unknown_ref_and_merge_commit_replay(self):
        with self.assertRaises(VirtualGitError):
            self.repo.rebase_branch("main", "missing")
        self.repo.create_branch("feature/unknown-ref")
        with self.assertRaises(KeyError):
            self.repo.rebase_branch("feature/unknown-ref", "missing")
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
        self.repo.create_branch("feature/rollback")
        self.repo.commit("feature/rollback", "temporary edit", {"src/core.py": "VERSION = 9\n"})
        result = self.repo.rollback_branch("feature/rollback", first)
        self.assertEqual(result["commit_id"], first)
        self.assertEqual(self.repo.read_file("feature/rollback", "src/core.py"), b"VERSION = 1\n")
        self.assertEqual(self.repo.events()[0]["kind"], "branch.rollback")
        with self.assertRaises(VirtualGitError):
            self.repo.rollback_branch("main", first)

    def test_deletions_are_merged_and_recorded(self):
        self.repo.create_branch("feature/remove")
        self.repo.commit("feature/remove", "remove source", {"src/core.py": None})
        pr = self.repo.open_pull_request("feature/remove", "main", "Remove file")
        self.pass_main_checks(pr["head_commit"])
        self.assertEqual(self.repo.merge_pull_request(pr["pr_id"])["status"], "merged")
        with self.assertRaises(KeyError):
            self.repo.read_file("main", "src/core.py")

    def test_rejects_path_traversal_and_oversized_event_queries(self):
        with self.assertRaises(VirtualGitError):
            self.repo.commit("main", "bad path", {"../outside.txt": "no"}, allow_protected=True)
        with self.assertRaises(VirtualGitError):
            self.repo.events(1001)

    def test_forge_http_api_exposes_status_branch_commit_pr_and_merge(self):
        event_store = EventStore(Path(self.temp.name) / "api-events.sqlite3")
        worker_token = "w" * 40
        with patch.dict(os.environ, {"MERLIN_WORKER_TOKENS": json.dumps({"test-worker": worker_token})}):
            handler = make_handler(event_store)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
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

        def worker_post(path, payload):
            request = Request(base + path, data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "X-Merlin-Worker-ID": "test-worker",
                         "Authorization": "Bearer " + worker_token})
            with urlopen(request, timeout=5) as response:
                return json.loads(response.read())

        try:
            status = get("/api/forge/status")
            self.assertEqual(status["schema"], "merlin-forge-status/1")
            self.assertEqual(status["runner_execution"], "not_performed")
            self.assertEqual(set(status["required_checks"]["main"]), {
                "python.compile", "python.unified_tests", "hud.javascript_syntax",
            })
            self.assertTrue(any(item["name"] == "main" for item in status["branches"]))

            post("/api/forge/branches", {"name": "feature/api"})
            commit = post("/api/forge/commits", {
                "branch": "feature/api", "message": "update forge API",
                "changes": {"README.md": "# Merlin Forge API\n"},
            })
            self.assertEqual(commit["schema"], "merlin-forge-commit/1")
            try:
                post("/api/forge/commits", {
                    "branch": "main", "message": "direct protected mutation",
                    "changes": {"src/runtime.py": "READY = True\n"},
                })
                self.fail("direct commit to protected main must be rejected")
            except HTTPError as exc:
                protected = json.loads(exc.read())
            self.assertIn("protected branch", protected["detail"])
            rebased = post("/api/forge/branches/feature%2Fapi/rebase", {"onto_ref": "main"})
            self.assertEqual(rebased["status"], "up_to_date")
            pr = post("/api/forge/pulls", {
                "source_branch": "feature/api", "target_branch": "main",
                "title": "Forge API integration",
            })
            for check_name in ("python.compile", "python.unified_tests", "hud.javascript_syntax"):
                post("/api/forge/checks", {
                    "commit_id": pr["head_commit"], "check_name": check_name,
                    "conclusion": "success", "run_id": "api-test-" + check_name,
                    "runner_id": "test-runner", "log": "PASS " + check_name,
                })
            check_payload = get("/api/forge/checks?commit=" + pr["head_commit"])
            self.assertEqual(len(check_payload["check_results"]), 3)
            self.assertTrue(all(row["verification_status"] == "UNVERIFIED" for row in check_payload["check_results"]))
            self.assertTrue(all(row["promotion_authorized"] is False for row in check_payload["check_results"]))
            log_payload = get("/api/forge/checks/" + str(check_payload["check_results"][0]["check_id"]) + "/log")
            self.assertTrue(log_payload["log_utf8"].startswith("PASS "))
            try:
                post(f"/api/forge/pulls/{pr['pr_id']}/merge", {})
                self.fail("unverified local CI must not merge")
            except HTTPError as exc:
                blocked = json.loads(exc.read())
            self.assertEqual(blocked["status"], "blocked")
            self.assertEqual(len(blocked["unverified_checks"]), 3)

            main_commit = next(row["commit_id"] for row in status["branches"] if row["name"] == "main")
            queued = post("/api/forge/jobs", {
                "commit_id": main_commit, "job_type": "python.compile",
                "idempotency_key": "api-compile-job",
            })
            self.assertEqual(queued["status"], "queued")
            self.assertEqual(queued["verification_status"], "UNVERIFIED")
            claimed = worker_post("/api/internal/forge/jobs/claim", {
                "job_types": ["python.compile"], "lease_seconds": 30,
            })["lease"]
            self.assertEqual(claimed["job_id"], queued["job_id"])
            worker_post("/api/internal/forge/jobs/" + queued["job_id"] + "/heartbeat", {
                "lease_token": claimed["lease_token"], "lease_seconds": 30,
            })
            completed = worker_post("/api/internal/forge/jobs/" + queued["job_id"] + "/complete", {
                "lease_token": claimed["lease_token"], "conclusion": "succeeded",
                "result": {"exit_code": 0}, "log": "compile complete",
            })
            self.assertEqual(completed["status"], "succeeded")
            self.assertEqual(completed["verification_status"], "UNVERIFIED")
            self.assertEqual(get("/api/forge/jobs/" + queued["job_id"])["job"]["status"], "succeeded")
            job_log = get("/api/forge/jobs/" + queued["job_id"] + "/log")
            self.assertEqual(job_log["log_utf8"], "compile complete")
            file_result = get("/api/forge/file?ref=main&path=README.md")
            self.assertEqual(file_result["content_utf8"], "# Merlin\n")
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
