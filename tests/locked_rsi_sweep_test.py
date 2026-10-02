"""Runner unit tests. All suite/result fixtures are synthetic, never benchmarks."""
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_locked_rsi_sweep as sweep


def inputs():
    baseline = sweep.json_bytes({"schema_version": 1, "strategies": ["trivial"], "timeout_seconds": 20})
    roadmap = sweep.json_bytes({"schema_version": 1, "locked_before_next_hidden_tier": True,
        "source_qualified_sha": sweep.QUALIFIED_SOURCE, "source_visible_inputs": [sweep.CONFIG_PATH],
        "generations": [{"generation": f"G{i}", "theme": "unit fixture", "add_strategies": [f"synthetic-{i}"]}
                        for i in range(4, 11)]})
    return baseline, roadmap


def metric(run_id, solved, attempts=5):
    return {"run_id": run_id, "case_ids": ["fixture-a", "fixture-b"],
            "solved_case_ids": solved, "proof_attempts": attempts, "cases": 2, "verified": len(solved)}


class RestorationTests(unittest.TestCase):
    def test_restores_bytes_and_permissions_after_failure_and_interruption(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            original = b'{ "original": true }\n'
            path.write_bytes(original)
            path.chmod(0o640)
            for exception in (ValueError("bad result"), KeyboardInterrupt(), InterruptedError("terminate")):
                with self.assertRaises(type(exception)):
                    with sweep.applied_config(path, b'{"candidate":true}\n'):
                        self.assertEqual(path.read_bytes(), b'{"candidate":true}\n')
                        raise exception
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
            self.assertEqual(sorted(p.name for p in Path(temp).iterdir()), ["config.json"])

    def test_refuses_symlink_config(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "target"
            target.write_bytes(b"unchanged")
            link = Path(temp) / "link"
            link.symlink_to(target)
            with self.assertRaises(sweep.SweepError):
                with sweep.applied_config(link, b"candidate"):
                    pass
            self.assertEqual(target.read_bytes(), b"unchanged")


class PlanAndRankingTests(unittest.TestCase):
    def test_cumulative_distinct_plan_is_independent_of_champion(self):
        baseline, roadmap = inputs()
        plan = sweep.materialize_plan(baseline, roadmap)
        self.assertEqual([p["generation"] for p in plan], [f"G{i}" for i in range(3, 11)])
        self.assertEqual(len({p["config_sha256"] for p in plan}), 8)
        for index, candidate in enumerate(plan[1:], 1):
            self.assertEqual(candidate["parent_config_sha256"], plan[index - 1]["config_sha256"])
            before = json.loads(plan[index - 1]["bytes"])["strategies"]
            after = json.loads(candidate["bytes"])["strategies"]
            self.assertEqual(after[:-1], before)
        self.assertEqual(plan[0]["bytes"], baseline)

    def test_duplicate_or_missing_generation_rejected(self):
        baseline, roadmap = inputs()
        value = json.loads(roadmap)
        value["generations"][1]["add_strategies"] = ["synthetic-4"]
        with self.assertRaises(sweep.SweepError):
            sweep.materialize_plan(baseline, sweep.json_bytes(value))
        value["generations"].pop()
        with self.assertRaises(sweep.SweepError):
            sweep.materialize_plan(baseline, sweep.json_bytes(value))

    def test_more_solves_cannot_hide_case_regression(self):
        champion = sweep.aggregate_repetitions([metric("a1", ["fixture-a"]), metric("a2", ["fixture-a"])])
        candidate = sweep.aggregate_repetitions([metric("b1", ["fixture-b"], 1), metric("b2", ["fixture-b"], 1)])
        self.assertEqual(sweep.select_candidate(champion, candidate), (False, "previously_solved_case_regression"))

    def test_unstable_solution_not_counted_and_tie_retains_champion(self):
        stable = sweep.aggregate_repetitions([metric("a1", ["fixture-a"]), metric("a2", ["fixture-a"])])
        unstable = sweep.aggregate_repetitions([metric("b1", ["fixture-a", "fixture-b"]), metric("b2", ["fixture-a"])])
        self.assertEqual(unstable["verified_count"], 1)
        self.assertEqual(sweep.select_candidate(stable, unstable), (False, "deterministic_tie_retain_champion"))
        faster = sweep.aggregate_repetitions([metric("c1", ["fixture-a"], 4), metric("c2", ["fixture-a"], 4)])
        self.assertEqual(sweep.select_candidate(stable, faster), (True, "fewer_total_proof_attempts"))


class ToolAndResultTests(unittest.TestCase):
    def test_timeout_is_recorded_and_stdout_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            command = [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(5)"]
            audit = sweep.capture_process(command, root, {"PATH": os.environ["PATH"]}, root / "run", 0.1)
            self.assertEqual(audit["status"], "timeout")
            self.assertEqual(audit["command"], command)
            self.assertEqual((root / "run/stdout.log").read_text(), "started\n")
            self.assertLess(audit["duration_seconds"], 2)
            self.assertLess(audit["terminated_returncode"], 0)

    def test_exit127_detected_even_if_benchmark_exits_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "proof_memory.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE proof_attempts(exit_code INTEGER, output_excerpt TEXT)")
                db.executemany("INSERT INTO proof_attempts VALUES (?,?)", [(127, ""), (1, "tactic failed")])
            audit = sweep.proof_tool_audit(Path(temp))
            self.assertEqual(audit["fatal_exit_codes"], ["127"])
            self.assertEqual(audit["persisted_exit_code_counts"]["127"], 1)

    def test_missing_lake_cannot_produce_meaningful_baseline(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(sweep.shutil, "which", return_value=None):
            with self.assertRaisesRegex(sweep.SweepError, "no meaningful baseline"):
                sweep.preflight(Path(temp), Path(temp), {"PATH": "", "ELAN_TOOLCHAIN": "leanprover/lean4:v4.34.0"}, 1)

    def test_environment_excludes_credentials_and_injection(self):
        with mock.patch.dict(os.environ, {"SECRET_API_KEY": "secret", "LD_PRELOAD": "fake.so", "LEAN_PATH": "fake", "LEAN_NUM_THREADS": "99"}):
            env = sweep.safe_environment("leanprover/lean4:v4.34.0")
        self.assertNotIn("SECRET_API_KEY", env)
        self.assertNotIn("LD_PRELOAD", env)
        self.assertNotIn("LEAN_PATH", env)
        self.assertEqual(env["LEAN_NUM_THREADS"], "1")

    def test_validation_metrics_exclude_filler_splits(self):
        mapping = {"fixture-t": "train", "fixture-a": "validation", "fixture-h": "holdout"}
        result = {"run_id": "fixture-run", "records": [
            {"case_id": k, "variant": "proof_search", "verified": True, "proof_attempts": 2, "model_calls": 0} for k in mapping],
            "summaries": [{"variant": "proof_search", "split": "validation", "cases": 1, "verified": 1}]}
        metric = sweep.validate_result(result, mapping, "fixture-run", "validation")
        self.assertEqual(metric["case_ids"], ["fixture-a"])
        self.assertEqual(metric["proof_attempts"], 2)
        result["records"][0]["model_calls"] = 1
        with self.assertRaises(sweep.SweepError):
            sweep.validate_result(result, mapping, "fixture-run", "validation")


class WorkflowTests(unittest.TestCase):
    """Use injected synthetic subprocess outputs to test audit ordering only."""

    def fixture(self, root):
        repo = root / "repo"
        (repo / "config").mkdir(parents=True)
        baseline, roadmap = inputs()
        (repo / sweep.CONFIG_PATH).write_bytes(baseline)
        (repo / "config/experiment_policy.json").write_bytes(sweep.json_bytes({"generation_budget": {"min_runs": 2, "max_runs": 30}}))
        baseline_path, roadmap_path = root / "baseline.json", root / "roadmap.json"
        baseline_path.write_bytes(baseline)
        roadmap_path.write_bytes(roadmap)
        validation, holdout = root / "validation.json", root / "holdout.json"
        def suite(ids):
            return {"schema_version": 1, "cases": [{"case_id": k, "split": s} for k, s in ids],
                    "variants": [{"variant_id": "proof_search", "enabled_layers": ["proof_search"]}]}
        validation.write_bytes(sweep.json_bytes(suite([("fixture-t", "train"), ("fixture-a", "validation"), ("fixture-b", "validation"), ("fixture-h", "holdout")])))
        holdout.write_bytes(sweep.json_bytes(suite([("final-t", "train"), ("final-v", "validation"), ("final-h", "holdout")])))
        output = root / "output"
        args = sweep.parse_args(["--repo", str(repo), "--executable", sys.executable, "--roadmap", str(roadmap_path),
            "--baseline-config", str(baseline_path), "--validation-suite", str(validation), "--holdout-suite", str(holdout), "--output-dir", str(output)])
        def git(_repo, *arguments):
            if arguments[0] == "show":
                return baseline if arguments[1].endswith(sweep.CONFIG_PATH) else roadmap
            if arguments[0] == "rev-parse":
                return (sweep.QUALIFIED_SOURCE + "\n").encode()
            return b""
        return args, baseline, git

    def test_every_generation_locked_before_feedback_and_holdout_delayed(self):
        with tempfile.TemporaryDirectory() as temp:
            args, baseline, fake_git = self.fixture(Path(temp))
            calls = []
            actual_mapping = sweep.suite_mapping
            def mapping(path, split):
                if split == "holdout":
                    self.assertTrue((args.output_dir / "selection.lock.json").is_file())
                    self.assertEqual(len(calls), 16)
                return actual_mapping(path, split)
            def capture(command, cwd, env, directory, timeout):
                self.assertTrue((args.output_dir / "configs.lock.json").is_file())
                self.assertEqual(len(list((args.output_dir / "generations").glob("*/proof-search.json"))), 8)
                result_path, run_id = Path(command[3]), command[4]
                gen, phase = run_id.split("-")[2:4]
                cases = json.loads(Path(command[1]).read_bytes())["cases"]
                records = []
                for case in cases:
                    solved = case["case_id"] != "fixture-b" or gen != "g3"
                    records.append({"case_id": case["case_id"], "variant": "proof_search", "verified": solved,
                                    "proof_attempts": 1 if solved else 2, "model_calls": 0})
                summaries = [{"variant": "proof_search", "split": split,
                    "cases": sum(c["split"] == split for c in cases),
                    "verified": sum(r["verified"] for c, r in zip(cases, records) if c["split"] == split)}
                    for split in ("train", "validation", "holdout")]
                result = {"run_id": run_id, "records": records, "summaries": summaries}
                directory.mkdir(parents=True)
                result_path.write_bytes(sweep.json_bytes(result))
                (directory / "stdout.log").write_bytes(sweep.json_bytes(result))
                (directory / "stderr.log").write_bytes(b"")
                audit = {"status": "completed", "returncode": 0, "command": command}
                sweep.save_json(directory / "command.json", audit)
                calls.append((gen, phase))
                return audit
            with mock.patch.object(sweep, "git", side_effect=fake_git), mock.patch.object(sweep, "source_inputs", return_value={}), \
                 mock.patch.object(sweep, "dependency_lock", return_value={"toolchain": "leanprover/lean4:v4.34.0"}), \
                 mock.patch.object(sweep, "preflight", return_value={"lake_path": sys.executable, "lake_sha256": sweep.file_hash(Path(sys.executable))}), \
                 mock.patch.object(sweep, "capture_process", side_effect=capture), mock.patch.object(sweep, "suite_mapping", side_effect=mapping):
                manifest = sweep.run(args)
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["selection"]["selected_generation"], "G4")
            self.assertEqual(len(calls), 20)
            self.assertTrue(all(phase == "validation" for _, phase in calls[:16]))
            self.assertTrue(all(phase == "holdout" for _, phase in calls[16:]))
            self.assertEqual((args.repo / sweep.CONFIG_PATH).read_bytes(), baseline)
            self.assertTrue(manifest["original_config_restored"])
            self.assertFalse(manifest["official_promotion"])

    def test_preflight_failure_preserves_locked_inputs_and_original_config(self):
        with tempfile.TemporaryDirectory() as temp:
            args, baseline, fake_git = self.fixture(Path(temp))
            with mock.patch.object(sweep, "git", side_effect=fake_git), mock.patch.object(sweep, "source_inputs", return_value={}), \
                 mock.patch.object(sweep, "dependency_lock", side_effect=sweep.SweepError("lake dependency missing")):
                with self.assertRaises(sweep.SweepError):
                    sweep.run(args)
            manifest = json.loads((args.output_dir / "manifest.json").read_bytes())
            self.assertEqual(manifest["status"], "failed")
            self.assertTrue(manifest["original_config_restored"])
            self.assertTrue((args.output_dir / "configs.lock.json").is_file())
            self.assertFalse((args.output_dir / "selection.lock.json").exists())
            self.assertEqual((args.repo / sweep.CONFIG_PATH).read_bytes(), baseline)

    def test_interrupted_launched_run_stays_in_generation_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            args, baseline, fake_git = self.fixture(Path(temp))
            def interrupted(command, cwd, env, directory, timeout):
                directory.mkdir(parents=True)
                sweep.save_json(directory / "command.json", {"command": command, "status": "interrupted",
                                                             "terminated_returncode": -9})
                raise InterruptedError("synthetic interrupted invocation")
            with mock.patch.object(sweep, "git", side_effect=fake_git), mock.patch.object(sweep, "source_inputs", return_value={}), \
                 mock.patch.object(sweep, "dependency_lock", return_value={"toolchain": "leanprover/lean4:v4.34.0"}), \
                 mock.patch.object(sweep, "preflight", return_value={"lake_path": sys.executable, "lake_sha256": sweep.file_hash(Path(sys.executable))}), \
                 mock.patch.object(sweep, "capture_process", side_effect=interrupted):
                with self.assertRaises(InterruptedError):
                    sweep.run(args)
            manifest = json.loads((args.output_dir / "manifest.json").read_bytes())
            gen = json.loads((args.output_dir / "generations/G3/manifest.json").read_bytes())
            self.assertEqual(manifest["status"], "interrupted")
            self.assertEqual(gen["status"], "interrupted")
            self.assertEqual(len(gen["validation_runs"]), 1)
            self.assertEqual(gen["validation_runs"][0]["status"], "interrupted")
            self.assertEqual((args.repo / sweep.CONFIG_PATH).read_bytes(), baseline)
            self.assertFalse((args.output_dir / "selection.lock.json").exists())

    def test_restoration_failure_is_audited_and_releases_repository_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            args, baseline, fake_git = self.fixture(Path(temp))
            actual_write = sweep.atomic_write
            def write(path, data, mode=0o600):
                if path == args.repo / sweep.CONFIG_PATH:
                    raise OSError("synthetic restore write failure")
                return actual_write(path, data, mode)
            with mock.patch.object(sweep, "git", side_effect=fake_git), mock.patch.object(sweep, "source_inputs", return_value={}), \
                 mock.patch.object(sweep, "dependency_lock", side_effect=sweep.SweepError("missing dependency")), \
                 mock.patch.object(sweep, "atomic_write", side_effect=write):
                with self.assertRaisesRegex(sweep.SweepError, "restoration failed"):
                    sweep.run(args)
            manifest = json.loads((args.output_dir / "manifest.json").read_bytes())
            self.assertEqual(manifest["status"], "restoration_failed")
            self.assertFalse(manifest["original_config_restored"])
            self.assertEqual(manifest["restoration_error"]["type"], "OSError")
            self.assertIn("finished_at", manifest)
            with sweep.repository_lock(args.repo):
                pass

    def test_live_baseline_alias_rejected_before_evaluation(self):
        with tempfile.TemporaryDirectory() as temp:
            args, baseline, fake_git = self.fixture(Path(temp))
            args.baseline_config = args.repo / sweep.CONFIG_PATH
            with self.assertRaisesRegex(sweep.SweepError, "immutable snapshot"):
                sweep.run(args)
            manifest = json.loads((args.output_dir / "manifest.json").read_bytes())
            self.assertEqual(manifest["status"], "failed")
            self.assertTrue(manifest["original_config_restored"])
            self.assertEqual((args.repo / sweep.CONFIG_PATH).read_bytes(), baseline)


if __name__ == "__main__":
    unittest.main()
