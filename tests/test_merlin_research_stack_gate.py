"""Offline regression tests of the CI gate, not research/provider qualification."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "merlin_research_stack_gate.py"
SPEC = importlib.util.spec_from_file_location("merlin_research_stack_gate", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
PASS = "import unittest\nclass Passing(unittest.TestCase):\n    def test_ok(self): self.assertEqual(2+2,4)\n"


class ResearchStackGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        self.root.mkdir()
        self.output = Path(self.temp.name) / "results"
        self.output.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Offline fixture")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_a.py").write_text(PASS)
        (self.root / ".gitignore").write_text("__pycache__/\nartifacts/\n")
        self.sha = self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.DEVNULL).decode().strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def change(self, text, name="test_a.py"):
        (self.root / "tests" / name).write_text(text)
        self.sha = self.commit()

    def run_gate(self, suites=("test_a.py",), **kwargs):
        return gate.run_gate(self.root, self.sha, self.output,
                             python_version=sys.version_info[:2], suites=suites, **kwargs)

    def test_valid_byte_verified_checkout(self):
        result = gate.inspect_checkout(self.root, self.sha)
        self.assertEqual(result["commit_sha"], self.sha)
        self.assertTrue(result["working_tree_matches_commit"])
        self.assertEqual(result["tracked_files"], 2)

    def test_wrong_commit(self):
        with self.assertRaisesRegex(ValueError, "HEAD"):
            gate.inspect_checkout(self.root, "a" * 40)

    def test_abbreviated_commit(self):
        with self.assertRaises(ValueError):
            gate.inspect_checkout(self.root, self.sha[:8])

    def test_dirty_tracked_source(self):
        (self.root / "tests/test_a.py").write_text(PASS + "# modified\n")
        with self.assertRaisesRegex(ValueError, "bytes"):
            gate.inspect_checkout(self.root, self.sha)

    def test_skip_worktree_does_not_hide_changes(self):
        self.git("update-index", "--skip-worktree", "tests/test_a.py")
        (self.root / "tests/test_a.py").write_text(PASS + "# hidden\n")
        self.assertEqual(self.git("status", "--porcelain"), "")
        with self.assertRaisesRegex(ValueError, "bytes"):
            gate.inspect_checkout(self.root, self.sha)

    def test_tracked_symlink_requires_target_qualification(self):
        (self.root / "tests/test_link.py").symlink_to("test_a.py")
        self.sha = self.commit()
        with self.assertRaisesRegex(ValueError, "symlinks require"):
            gate.inspect_checkout(self.root, self.sha)

    def test_executable_mode_change_is_rejected(self):
        (self.root / "tests/test_a.py").chmod(0o755)
        with self.assertRaisesRegex(ValueError, "executable mode"):
            gate.inspect_checkout(self.root, self.sha)

    def test_missing_tracked_file(self):
        (self.root / "tests/test_a.py").unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            gate.inspect_checkout(self.root, self.sha)

    def test_ignored_importable_code_is_rejected(self):
        (self.root / ".gitignore").write_text("*.py\n")
        self.sha = self.commit()
        (self.root / "tests/shadow.py").write_text("unexpected = True\n")
        with self.assertRaisesRegex(ValueError, "untracked importable"):
            gate.inspect_checkout(self.root, self.sha)

    def test_symlinked_source_parent_is_rejected(self):
        os.rename(self.root / "tests", self.root / "actual_tests")
        (self.root / "tests").symlink_to("actual_tests", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked parent"):
            gate.inspect_checkout(self.root, self.sha)

    def test_nested_worktree_root_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "worktree root"):
            gate.inspect_checkout(self.root / "tests", self.sha)

    def test_missing_git_checkout_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "complete local checkout"):
            gate.inspect_checkout(self.output, self.sha)

    def test_success_report_is_written_and_non_authoritative(self):
        result = self.run_gate()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["suites"][0]["tests_run"], 1)
        saved = json.loads((self.output / "research-stack-result.json").read_text())
        self.assertEqual(result, saved)
        self.assertFalse(saved["production_qualification"])
        self.assertFalse(saved["cace_independent_verification"])
        self.assertFalse(saved["promotion_authority"])

    def test_zero_tests_is_incomplete(self):
        self.change("VALUE = 1\n")
        result = self.run_gate()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["suites"][0]["status"], "incomplete")

    def test_failure_does_not_skip_later_suites(self):
        self.change(PASS.replace("2+2,4", "2+2,5"))
        self.change(PASS, "test_b.py")
        result = self.run_gate(("test_a.py", "test_b.py"))
        self.assertEqual(result["status"], "failed")
        self.assertEqual([s["status"] for s in result["suites"]], ["failed", "passed"])

    def test_skipped_test_is_incomplete(self):
        self.change(PASS.replace("    def test_ok", "    @unittest.skip('fixture')\n    def test_ok"))
        result = self.run_gate()
        self.assertEqual(result["suites"][0]["status"], "incomplete")
        self.assertEqual(result["suites"][0]["skipped"], 1)

    def test_missing_suite_is_not_a_pass(self):
        result = self.run_gate(("test_absent.py", "test_a.py"))
        self.assertEqual(result["status"], "failed")
        self.assertEqual([s["status"] for s in result["suites"]], ["missing", "passed"])

    def test_timeout_is_recorded(self):
        self.change("import time\ntime.sleep(30)\n" + PASS)
        result = self.run_gate(timeout=0.3)
        self.assertEqual(result["suites"][0]["status"], "timeout")
        self.assertEqual(result["status"], "failed")

    def test_output_cap_is_recorded(self):
        self.change("print('x' * 50000, flush=True)\n" + PASS)
        result = gate.run_suite(self.root, "test_a.py", self.output, max_log_bytes=4096)
        self.assertEqual(result["status"], "output_limit")
        self.assertLessEqual((self.output / "test_a.py.log").stat().st_size, 4096)

    def test_log_limit_does_not_limit_test_fixture_files(self):
        self.change("import tempfile\nfrom pathlib import Path\nwith tempfile.TemporaryDirectory() as d: Path(d, 'large').write_bytes(b'x' * 8192)\n" + PASS)
        result = gate.run_suite(self.root, "test_a.py", self.output, max_log_bytes=4096)
        self.assertEqual(result["status"], "passed")

    def test_parent_secret_is_not_inherited(self):
        self.change("import os\nassert 'MERLIN_SENTINEL_SECRET' not in os.environ\n" + PASS)
        with patch.dict(os.environ, {"MERLIN_SENTINEL_SECRET": "non-secret-fixture"}):
            result = self.run_gate()
        self.assertEqual(result["status"], "passed")

    def test_source_mutation_blocks_next_suite(self):
        self.change("from pathlib import Path\nPath(__file__).write_text('# changed')\n" + PASS)
        self.change(PASS, "test_b.py")
        result = self.run_gate(("test_a.py", "test_b.py"))
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["suites"][1]["status"], "not_run")

    def test_wrong_python_stops_before_execution(self):
        result = gate.run_gate(self.root, self.sha, self.output, python_version=(9, 99), suites=("test_a.py",))
        self.assertEqual(result["status"], "blocked")
        self.assertIn("interpreter", result["blocker"])
        self.assertEqual(result["suites"][0]["status"], "not_run")
        self.assertFalse((self.output / "test_a.py.log").exists())

    def test_stale_pass_result_cannot_mask_early_exit(self):
        self.assertEqual(self.run_gate()["status"], "passed")
        self.change("import os\nos._exit(0)\n")
        result = self.run_gate()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["suites"][0]["status"], "missing_result")

    def test_import_error_is_reported(self):
        self.change("import nonexistent_merlin_fixture_package\n" + PASS)
        result = self.run_gate()
        self.assertEqual(result["suites"][0]["errors"], 1)
        self.assertEqual(result["status"], "failed")

    def test_invalid_runtime_bounds_fail_closed(self):
        for timeout in (True, float("nan"), float("inf"), 0, 601):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                gate.run_suite(self.root, "test_a.py", self.output, timeout=timeout)

    def test_invalid_suite_path(self):
        with self.assertRaises(ValueError):
            gate.run_suite(self.root, "../escape.py", self.output)

    def test_production_suite_set_covers_entire_requested_chain(self):
        self.assertIn("test_merlin_prompt_contract.py", gate.SUITES)
        self.assertIn("test_merlin_scientific_workflow.py", gate.SUITES)
        self.assertIn("test_ideonomy.py", gate.SUITES)
        self.assertIn("test_hermes_ideonomy_stage.py", gate.SUITES)
        self.assertIn("test_logos_review.py", gate.SUITES)
        self.assertEqual(len(gate.SUITES), len(set(gate.SUITES)))


if __name__ == "__main__":
    unittest.main()
