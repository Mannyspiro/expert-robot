#!/usr/bin/env python3
"""Audited, non-promoting G3→G10 proof-search experiment using real Lean.

Only the repository's proof-search configuration is temporarily replaced. The
provided validation suite must use validation-origin fillers for the executable's
required train/holdout splits; the final holdout suite is not parsed until the
validation winner is locked. No automatic proposal generation or promotion runs.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

ROADMAP_COMMIT = "9d4968631a7cac64c096c08629c4016656743b77"
ROADMAP_GIT_PATH = "config/g4_g10_blind_roadmap.json"
QUALIFIED_SOURCE = "0b4c9b29e50890785fbe36d4a849e297f480bcd1"
CONFIG_PATH = "config/proof_search.json"
VARIANT = "proof_search"


class SweepError(RuntimeError):
    """A failed audit, tool invocation, or invalid input."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_json(path: Path, value: Any) -> None:
    atomic_write(path, json_bytes(value))


@contextlib.contextmanager
def applied_config(path: Path, candidate: bytes):
    """Atomically apply bytes and restore exact original bytes/mode in finally."""
    if path.is_symlink() or not path.is_file():
        raise SweepError(f"config must be a regular, nonsymlink file: {path}")
    original = path.read_bytes()
    mode = stat.S_IMODE(path.stat().st_mode)
    try:
        atomic_write(path, candidate, mode)
        yield
    finally:
        atomic_write(path, original, mode)
        if path.read_bytes() != original:
            raise SweepError("original configuration restoration failed")


@contextlib.contextmanager
def signal_guard():
    def interrupted(signum, _frame):
        raise InterruptedError(f"interrupted by signal {signum}")
    previous = {}
    for name in ("SIGTERM", "SIGHUP"):
        sig = getattr(signal, name, None)
        if sig is not None:
            previous[sig] = signal.signal(sig, interrupted)
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


@contextlib.contextmanager
def repository_lock(repo: Path):
    name = sha256(str(repo).encode())[:24]
    with open(Path(tempfile.gettempdir()) / f"locked-rsi-{name}.lock", "a+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SweepError("another sweep is modifying this repository") from exc
        yield


def capture_process(command: list[str], cwd: Path, env: dict[str, str],
                    directory: Path, timeout: float) -> dict[str, Any]:
    """Preserve stdout/stderr and exit status, including timeouts/interruptions."""
    directory.mkdir(parents=True, exist_ok=True)
    audit = {"command": command, "cwd": str(cwd), "environment": env,
             "started_at": utc_now(), "timeout_seconds": timeout, "status": "running"}
    save_json(directory / "command.json", audit)
    started = time.monotonic()
    proc = None
    pending = None
    with (directory / "stdout.log").open("wb") as out, (directory / "stderr.log").open("wb") as err:
        try:
            proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=err,
                                    start_new_session=True)
            audit["pid"] = proc.pid
            audit["returncode"] = proc.wait(timeout=timeout)
            audit["status"] = "completed" if proc.returncode == 0 else "tool_failed"
        except subprocess.TimeoutExpired:
            audit["status"] = "timeout"
            audit["returncode"] = None
        except (KeyboardInterrupt, InterruptedError) as exc:
            audit["status"] = "interrupted"
            audit["error"] = str(exc)
            pending = exc
        except OSError as exc:
            audit["status"] = "launch_failed"
            audit["error"] = str(exc)
        finally:
            if proc is not None and proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    audit["terminated_returncode"] = proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    audit["status"] = "termination_failed"
                    audit["error"] = "process did not terminate within bounded cleanup wait"
    audit["finished_at"] = utc_now()
    audit["duration_seconds"] = round(time.monotonic() - started, 6)
    audit["stdout_sha256"] = file_hash(directory / "stdout.log")
    audit["stderr_sha256"] = file_hash(directory / "stderr.log")
    save_json(directory / "command.json", audit)
    if pending is not None:
        raise pending
    return audit


def git(repo: Path, *arguments: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *arguments], capture_output=True, timeout=30)
    if result.returncode != 0:
        raise SweepError(f"git command failed: {' '.join(arguments)}")
    return result.stdout


def load_object(data: bytes, description: str) -> dict:
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise SweepError(f"invalid JSON: {description}") from exc
    if not isinstance(value, dict):
        raise SweepError(f"expected a JSON object: {description}")
    return value


def materialize_plan(baseline_bytes: bytes, roadmap_bytes: bytes) -> list[dict[str, Any]]:
    baseline = load_object(baseline_bytes, "baseline config")
    roadmap = load_object(roadmap_bytes, "roadmap")
    strategies = baseline.get("strategies")
    if baseline.get("schema_version") != 1 or not isinstance(strategies, list) or not strategies:
        raise SweepError("invalid baseline proof-search schema")
    if not all(isinstance(s, str) and s.strip() for s in strategies) or len(set(strategies)) != len(strategies):
        raise SweepError("baseline strategies must be distinct nonempty strings")
    if type(baseline.get("timeout_seconds")) is not int or baseline["timeout_seconds"] <= 0:
        raise SweepError("baseline timeout_seconds must be a positive integer")
    if (roadmap.get("schema_version") != 1 or roadmap.get("locked_before_next_hidden_tier") is not True
            or roadmap.get("source_qualified_sha") != QUALIFIED_SOURCE):
        raise SweepError("roadmap lock/source metadata mismatch")
    generations = roadmap.get("generations", [])
    if [entry.get("generation") for entry in generations] != [f"G{i}" for i in range(4, 11)]:
        raise SweepError("roadmap must contain G4 through G10 in order")
    plan = [{"generation": "G3", "theme": "qualified source baseline",
             "bytes": baseline_bytes, "config_sha256": sha256(baseline_bytes), "parent_config_sha256": None}]
    config = json.loads(json.dumps(baseline))
    for entry in generations:
        additions = entry.get("add_strategies")
        if not isinstance(additions, list) or not additions or not all(isinstance(s, str) and s.strip() for s in additions):
            raise SweepError("roadmap additions must be nonempty strings")
        if len(set(additions)) != len(additions) or any(s in config["strategies"] for s in additions):
            raise SweepError("roadmap must add distinct strategies at every generation")
        config["strategies"].extend(additions)
        data = json_bytes(config)
        plan.append({"generation": entry["generation"], "theme": entry.get("theme", ""),
                     "bytes": data, "config_sha256": sha256(data),
                     "parent_config_sha256": plan[-1]["config_sha256"]})
    if len({entry["config_sha256"] for entry in plan}) != len(plan):
        raise SweepError("candidate configuration hashes are not distinct")
    return plan


def verify_candidate_manifest(repo: Path, path: Path, plan: list[dict]) -> None:
    external = load_object(path.read_bytes(), "candidate manifest")
    if external.get("roadmap_sha") != ROADMAP_COMMIT or external.get("source_qualified_sha") != QUALIFIED_SOURCE:
        raise SweepError("external candidate manifest lock/source mismatch")
    entries = external.get("candidates", [])
    if [e.get("generation") for e in entries] != [p["generation"] for p in plan[1:]]:
        raise SweepError("external candidate generations mismatch")
    parent = QUALIFIED_SOURCE
    plan[0].update({"candidate_source_commit": QUALIFIED_SOURCE, "candidate_parent_commit": None})
    for candidate, entry in zip(plan[1:], entries):
        commit = entry.get("candidate_sha", "")
        if not re.fullmatch(r"[0-9a-f]{40}", commit) or entry.get("parent_sha") != parent:
            raise SweepError("external candidate lineage mismatch")
        actual_lineage = git(repo, "rev-list", "--parents", "-n", "1", commit).decode().split()
        if actual_lineage != [commit, parent]:
            raise SweepError("external candidates must have one exact recorded Git parent")
        if git(repo, "rev-parse", f"{commit}^").decode().strip() != parent:
            raise SweepError("external candidate actual Git parent mismatch")
        actual_config = git(repo, "show", f"{commit}:{CONFIG_PATH}")
        if sha256(actual_config) != candidate["config_sha256"] or entry.get("config_sha256") != candidate["config_sha256"]:
            raise SweepError("external candidate config hash mismatch")
        changed = git(repo, "diff", "--name-only", parent, commit).decode().splitlines()
        if changed != [CONFIG_PATH]:
            raise SweepError("external candidate changes must be config-only")
        candidate.update({"candidate_source_commit": commit, "candidate_parent_commit": parent,
                          "candidate_branch": entry.get("branch")})
        parent = commit


def safe_environment(toolchain: str) -> dict[str, str]:
    # Deliberately exclude credentials, LD_PRELOAD, and inherited Lean search paths.
    result = {"PATH": os.environ.get("PATH", os.defpath),
              "HOME": os.environ.get("HOME", str(Path.home())),
              "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "ELAN_TOOLCHAIN": toolchain,
              "LEAN_NUM_THREADS": "1"}
    for name in ("ELAN_HOME", "XDG_CACHE_HOME", "TMPDIR"):
        if name in os.environ:
            result[name] = os.environ[name]
    return result


def source_inputs(repo: Path, visible: list[str]) -> dict[str, str]:
    tracked = git(repo, "ls-files", "-z", "cpp", "CMakeLists.txt", "formal/MathAI", "formal/MathAI.lean").split(b"\0")
    names = {name.decode() for name in tracked if name}
    names.update(visible)
    names.update(("formal/lean-toolchain", "formal/lake-manifest.json", "formal/lakefile.toml",
                  "config/formal_dependency_lock.json", "config/experiment_policy.json"))
    names.discard(CONFIG_PATH)
    for name in names:
        if name.startswith(("config/benchmarks/", "tests/")) or ".." in Path(name).parts or Path(name).is_absolute():
            raise SweepError("unexpected excluded source input")
    return {name: file_hash(repo / name) for name in sorted(names)}


def dependency_lock(repo: Path) -> dict[str, Any]:
    lock = load_object((repo / "config/formal_dependency_lock.json").read_bytes(), "dependency lock")
    manifest = load_object((repo / "formal/lake-manifest.json").read_bytes(), "Lake manifest")
    toolchain = (repo / "formal/lean-toolchain").read_text().strip()
    if toolchain != lock.get("lean_toolchain") or not re.fullmatch(r"leanprover/lean4:v\d+\.\d+\.\d+", toolchain):
        raise SweepError("Lean toolchain does not match exact dependency pin")
    fields = ("name", "type", "url", "rev", "inputRev")
    expected = {p["name"]: {key: p.get(key) for key in fields} for p in lock.get("packages", [])}
    actual = {p["name"]: {key: p.get(key) for key in fields} for p in manifest.get("packages", [])}
    if not expected or expected != actual:
        raise SweepError("Lake manifest packages do not match exact dependency lock")
    revisions = {}
    for name, entry in expected.items():
        package = repo / "formal/.lake/packages" / name
        if not package.is_dir():
            raise SweepError(f"pinned Lake dependency is missing: {name}")
        revision = git(package, "rev-parse", "HEAD").decode().strip()
        if revision != entry["rev"]:
            raise SweepError(f"Lake dependency checkout differs from pin: {name}")
        if git(package, "status", "--porcelain", "--untracked-files=no").strip():
            raise SweepError(f"Lake dependency has tracked modifications: {name}")
        revisions[name] = revision
    return {"toolchain": toolchain, "package_revisions": revisions,
            "lock_sha256": file_hash(repo / "config/formal_dependency_lock.json")}


def require_success(audit: dict, label: str) -> None:
    if audit["status"] != "completed" or audit.get("returncode") != 0:
        raise SweepError(f"{label} failed ({audit['status']}); inspect saved command/stdout/stderr")


def preflight(repo: Path, output: Path, env: dict[str, str], timeout: float) -> dict:
    lake = shutil.which("lake", path=env["PATH"])
    if lake is None:
        raise SweepError("lake is missing from PATH; no meaningful baseline can be measured")
    directory = output / "preflight"
    version = capture_process([lake, "env", "lean", "--version"], repo / "formal", env,
                              directory / "lean-version", timeout)
    require_success(version, "pinned Lean version check")
    version_text = (directory / "lean-version/stdout.log").read_text(errors="replace")
    expected_version = env["ELAN_TOOLCHAIN"].split(":v", 1)[1]
    if not re.search(r"\bversion " + re.escape(expected_version) + r"(?:\s|,|\))", version_text):
        raise SweepError("installed Lean version differs from pinned toolchain")
    smoke = directory / "tool-smoke.lean"
    atomic_write(smoke, b"import MathAI\nexample : True := by trivial\n")
    check = capture_process([lake, "env", "lean", str(smoke)], repo / "formal", env,
                            directory / "lean-import-smoke", timeout)
    require_success(check, "pinned Lean import smoke check")
    lake_version = capture_process([lake, "--version"], repo / "formal", env,
                                   directory / "lake-version", timeout)
    require_success(lake_version, "Lake version check")
    return {"lake_path": lake, "lake_resolved_path": str(Path(lake).resolve()),
            "lake_sha256": file_hash(Path(lake)), "lean_version": version_text.strip(),
            "lake_version": (directory / "lake-version/stdout.log").read_text(errors="replace").strip(),
            "commands": [version, check, lake_version], "smoke_sha256": file_hash(smoke)}


def suite_mapping(path: Path, split: str) -> dict[str, str]:
    suite = load_object(path.read_bytes(), f"{split} suite")
    cases = suite.get("cases")
    if suite.get("schema_version") != 1 or not isinstance(cases, list):
        raise SweepError("invalid suite schema")
    mapping = {}
    for case in cases:
        case_id = case.get("case_id")
        case_split = case.get("split")
        if not isinstance(case_id, str) or not case_id or case_id in mapping or case_split not in ("train", "validation", "holdout"):
            raise SweepError("suite has duplicate/invalid case IDs or splits")
        mapping[case_id] = case_split
    if set(mapping.values()) != {"train", "validation", "holdout"}:
        raise SweepError("C++ benchmark requires train, validation, holdout labels; provide designated fillers")
    variants = [p for p in suite.get("variants", []) if p.get("variant_id") == VARIANT]
    if len(variants) != 1 or variants[0].get("enabled_layers") != [VARIANT]:
        raise SweepError("suite does not include proof_search variant")
    return mapping


def proof_tool_audit(state: Path) -> dict:
    """Inspect numeric exit evidence, never use proof text to propose edits."""
    counts = {}
    databases = []
    infrastructure_error_count = 0
    for path in sorted(state.rglob("proof_memory.sqlite3")):
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            try:
                rows = db.execute("SELECT exit_code, COUNT(*) FROM proof_attempts GROUP BY exit_code").fetchall()
                # Evaluation learning is disabled; only persisted training attempts
                # appear here. The separate real-Lean smoke check covers the tool.
                excerpts = db.execute("SELECT output_excerpt FROM proof_attempts WHERE exit_code != 0").fetchall()
            except sqlite3.DatabaseError as exc:
                raise SweepError("unreadable proof-attempt audit database") from exc
        for code, count in rows:
            counts[str(code)] = counts.get(str(code), 0) + count
        pattern = r"unknown module prefix|object file .* does not exist|no default toolchain|could not download|failed to fetch|lake:.*not found"
        infrastructure_error_count += sum(bool(re.search(pattern, text, re.I)) for (text,) in excerpts)
        databases.append({"path": str(path.relative_to(state)), "sha256": file_hash(path)})
    fatal_codes = [code for code in counts if int(code) in (126, 127) or int(code) >= 128]
    return {"persisted_exit_code_counts": counts, "fatal_exit_codes": fatal_codes,
            "infrastructure_error_count": infrastructure_error_count, "databases": databases,
            "scope": "persisted training attempts; evaluation attempts are not persisted by C++"}


def validate_result(result: dict, mapping: dict[str, str], run_id: str, split: str) -> dict:
    if result.get("run_id") != run_id:
        raise SweepError("benchmark run_id mismatch")
    records = result.get("records")
    if not isinstance(records, list) or len(records) != len(mapping):
        raise SweepError("benchmark records do not cover the entire supplied suite")
    indexed = {}
    for record in records:
        case_id = record.get("case_id")
        if record.get("variant") != VARIANT or case_id not in mapping or case_id in indexed:
            raise SweepError("unexpected/duplicate benchmark record")
        if type(record.get("verified")) is not bool or type(record.get("proof_attempts")) is not int or record["proof_attempts"] < 0:
            raise SweepError("invalid verified/proof_attempts fields")
        if record.get("model_calls") != 0:
            raise SweepError("proof_search benchmark unexpectedly used a model")
        indexed[case_id] = record
    summaries = result.get("summaries")
    if not isinstance(summaries, list) or not summaries:
        raise SweepError("missing benchmark summaries")
    summary_cases = sum(s.get("cases", 0) for s in summaries if s.get("variant") == VARIANT and s.get("split") == split)
    selected = {key: record for key, record in indexed.items() if mapping[key] == split}
    if not selected or summary_cases != len(selected):
        raise SweepError("benchmark split summary does not match records")
    summary_verified = sum(s.get("verified", 0) for s in summaries if s.get("variant") == VARIANT and s.get("split") == split)
    if summary_verified != sum(r["verified"] for r in selected.values()):
        raise SweepError("benchmark verified summary mismatch")
    return {"run_id": run_id, "split": split, "cases": len(selected),
            "verified": sum(r["verified"] for r in selected.values()),
            "proof_attempts": sum(r["proof_attempts"] for r in selected.values()),
            "solved_case_ids": sorted(key for key, record in selected.items() if record["verified"]),
            "case_ids": sorted(selected)}


def aggregate_repetitions(metrics: list[dict]) -> dict:
    if not metrics:
        raise SweepError("no valid repetitions")
    case_ids = metrics[0]["case_ids"]
    if any(m["case_ids"] != case_ids for m in metrics):
        raise SweepError("repetitions covered different cases")
    solved = set(metrics[0]["solved_case_ids"])
    for metric in metrics[1:]:
        solved.intersection_update(metric["solved_case_ids"])
    return {"repetitions": len(metrics), "cases": len(case_ids), "case_ids": case_ids,
            "verified_count": len(solved), "stable_solved_case_ids": sorted(solved),
            "total_proof_attempts": sum(m["proof_attempts"] for m in metrics),
            "feedback_record_ids": [m["run_id"] for m in metrics],
            "per_repetition": metrics}


def select_candidate(champion: dict, candidate: dict) -> tuple[bool, str]:
    if champion["case_ids"] != candidate["case_ids"] or champion["repetitions"] != candidate["repetitions"]:
        raise SweepError("cannot rank incomparable evaluations")
    if not set(champion["stable_solved_case_ids"]).issubset(candidate["stable_solved_case_ids"]):
        return False, "previously_solved_case_regression"
    old_key = (champion["verified_count"], -champion["total_proof_attempts"])
    new_key = (candidate["verified_count"], -candidate["total_proof_attempts"])
    if new_key > old_key:
        return True, "higher_verified_count" if new_key[0] > old_key[0] else "fewer_total_proof_attempts"
    return False, "deterministic_tie_retain_champion" if new_key == old_key else "lower_rank"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--roadmap", "--roadmap-path", dest="roadmap", type=Path, required=True)
    parser.add_argument("--baseline-config", type=Path, required=True)
    parser.add_argument("--validation-suite", type=Path, required=True)
    parser.add_argument("--holdout-suite", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate-manifest", type=Path,
                        help="optional externally frozen local candidate commit/hash mapping")
    parser.add_argument("--start-generation", type=int, default=3, choices=[3])
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=3600)
    parser.add_argument("--preflight-timeout-seconds", type=float, default=120)
    parser.add_argument("--validation-only", action="store_true")
    return parser.parse_args(argv)


def run(args) -> dict:
    for name in ("repo", "executable", "roadmap", "baseline_config", "validation_suite", "holdout_suite", "output_dir"):
        setattr(args, name, getattr(args, name).expanduser().resolve())
    if args.candidate_manifest is not None:
        args.candidate_manifest = args.candidate_manifest.expanduser().resolve()
    if (not math.isfinite(args.timeout_seconds) or not math.isfinite(args.preflight_timeout_seconds)
            or args.timeout_seconds <= 0 or args.preflight_timeout_seconds <= 0):
        raise SweepError("timeouts must be finite and positive")
    output = args.output_dir
    # Never overwrite evidence or benchmark state from an earlier invocation.
    output.mkdir(parents=True, exist_ok=False)
    config_path = args.repo / CONFIG_PATH
    manifest = {"schema_version": 1, "experiment_kind": "external_locked_roadmap_evaluation",
                "status": "initializing", "started_at": utc_now(),
                "official_promotion": False, "official_qualification": False, "collared_execution": False,
                "self_generated_system_changes": False, "start_generation": 3,
                "validation_only": args.validation_only, "repetitions": args.repetitions,
                "ranking_policy": "stable verified count descending, total validation proof_attempts ascending; no solved-case regression; ties retain champion",
                "budget_note": "policy minimum paired deterministic runs; no estimator-based budget claim",
                "holdout_policy": "hash frozen at start; contents parsed and evaluated only after selection.lock.json",
                "generation_manifests": []}
    save_json(output / "manifest.json", manifest)
    original = None
    original_mode = None
    lock = repository_lock(args.repo)
    lock_active = False
    plan = []
    try:
        lock.__enter__()
        lock_active = True
        with signal_guard():
            if not args.executable.is_file() or not os.access(args.executable, os.X_OK):
                raise SweepError("benchmark executable is missing or not executable")
            if config_path.is_symlink() or not config_path.is_file():
                raise SweepError("repository proof-search config must be a regular file")
            original = config_path.read_bytes()
            original_mode = stat.S_IMODE(config_path.stat().st_mode)
            atomic_write(output / "original-proof-search.json", original, original_mode)
            if os.path.samefile(args.baseline_config, config_path):
                raise SweepError("baseline-config must be an immutable snapshot, not the live repository config")
            if os.path.samefile(args.validation_suite, args.holdout_suite):
                raise SweepError("validation-suite and holdout-suite must be distinct sealed inputs")
            baseline = args.baseline_config.read_bytes()
            locked_baseline = git(args.repo, "show", f"{QUALIFIED_SOURCE}:{CONFIG_PATH}")
            if baseline != locked_baseline:
                raise SweepError("baseline config differs from qualified G3 source")
            roadmap = args.roadmap.read_bytes()
            locked_roadmap = git(args.repo, "show", f"{ROADMAP_COMMIT}:{ROADMAP_GIT_PATH}")
            if roadmap != locked_roadmap:
                raise SweepError("roadmap bytes differ from locked Git blob")
            plan = materialize_plan(baseline, roadmap)
            if args.candidate_manifest is not None:
                verify_candidate_manifest(args.repo, args.candidate_manifest, plan)
            policy = load_object((args.repo / "config/experiment_policy.json").read_bytes(), "experiment policy")
            minimum = policy["generation_budget"]["min_runs"]
            maximum = policy["generation_budget"]["max_runs"]
            if not minimum <= args.repetitions <= maximum:
                raise SweepError(f"repetitions must obey policy range {minimum}..{maximum}")
            frozen = {"source_commit": git(args.repo, "rev-parse", "HEAD").decode().strip(),
                      "source_tree": git(args.repo, "rev-parse", "HEAD^{tree}").decode().strip(),
                      "qualified_source_commit": QUALIFIED_SOURCE, "roadmap_commit": ROADMAP_COMMIT,
                      "source_files_sha256": source_inputs(args.repo, load_object(roadmap, "roadmap")["source_visible_inputs"]),
                      "roadmap_sha256": sha256(roadmap), "baseline_config_sha256": sha256(baseline),
                      "original_config_sha256": sha256(original), "executable_sha256": file_hash(args.executable),
                      "validation_suite_sha256": file_hash(args.validation_suite),
                      "holdout_suite_sha256": file_hash(args.holdout_suite)}
            if args.candidate_manifest is not None:
                frozen["candidate_manifest_sha256"] = file_hash(args.candidate_manifest)
            manifest["frozen_inputs"] = frozen
            manifest["runner"] = {"python_version": sys.version, "platform": sys.platform,
                                  "script_sha256": file_hash(Path(__file__).resolve())}
            manifest["initial_git_status"] = git(args.repo, "status", "--porcelain", "--untracked-files=no").decode()
            manifest["paths"] = {name: str(getattr(args, name)) for name in ("repo", "executable", "roadmap", "baseline_config", "validation_suite", "holdout_suite")}
            # Freeze every configuration and manifest before reading suite content or feedback.
            for candidate in plan:
                gen_dir = output / "generations" / candidate["generation"]
                candidate["path"] = gen_dir / "proof-search.json"
                atomic_write(candidate["path"], candidate["bytes"])
                gen = {key: candidate[key] for key in ("generation", "theme", "config_sha256", "parent_config_sha256")}
                for key in ("candidate_source_commit", "candidate_parent_commit", "candidate_branch"):
                    if key in candidate:
                        gen[key] = candidate[key]
                gen.update({"lineage_kind": "cumulative_locked_candidate", "status": "config_locked",
                            "frozen_inputs": frozen, "config_locked_at": utc_now(),
                            "feedback_record_ids": [], "validation_runs": [], "holdout_runs": [],
                            "official_promotion": False})
                candidate["manifest"] = gen
                save_json(gen_dir / "manifest.json", gen)
                manifest["generation_manifests"].append(str((gen_dir / "manifest.json").relative_to(output)))
            save_json(output / "configs.lock.json", {"locked_at": utc_now(), "frozen_inputs": frozen,
                       "configs": [{k: c[k] for k in ("generation", "config_sha256", "parent_config_sha256")} for c in plan]})
            manifest["status"] = "configs_locked"
            save_json(output / "manifest.json", manifest)
            dependencies = dependency_lock(args.repo)
            env = safe_environment(dependencies["toolchain"])
            manifest["dependencies"] = dependencies
            manifest["environment"] = env
            manifest["tool_versions"] = preflight(args.repo, output, env, args.preflight_timeout_seconds)
            save_json(output / "manifest.json", manifest)
            validation_map = suite_mapping(args.validation_suite, "validation")

            def check_frozen():
                checks = ((args.executable, "executable_sha256"), (args.validation_suite, "validation_suite_sha256"),
                          (args.holdout_suite, "holdout_suite_sha256"), (args.roadmap, "roadmap_sha256"),
                          (args.baseline_config, "baseline_config_sha256"))
                for path, key in checks:
                    if file_hash(path) != frozen[key]:
                        raise SweepError(f"frozen input changed: {key}")
                if args.candidate_manifest is not None and file_hash(args.candidate_manifest) != frozen["candidate_manifest_sha256"]:
                    raise SweepError("frozen candidate manifest changed")
                if git(args.repo, "rev-parse", "HEAD").decode().strip() != frozen["source_commit"]:
                    raise SweepError("repository HEAD changed during sweep")
                for name, expected in frozen["source_files_sha256"].items():
                    if file_hash(args.repo / name) != expected:
                        raise SweepError(f"frozen source input changed: {name}")
                for candidate in plan:
                    if file_hash(candidate["path"]) != candidate["config_sha256"]:
                        raise SweepError("locked candidate config changed")
                if file_hash(Path(manifest["tool_versions"]["lake_path"])) != manifest["tool_versions"]["lake_sha256"]:
                    raise SweepError("lake executable changed")

            def evaluate(candidate, phase, suite, mapping):
                gen = candidate["manifest"]
                gen_dir = candidate["path"].parent
                gen["status"] = phase + "_running"
                save_json(gen_dir / "manifest.json", gen)
                metrics = []
                if config_path.read_bytes() != original:
                    raise SweepError("repository config changed outside sweep")
                with applied_config(config_path, candidate["bytes"]):
                    for repetition in range(1, args.repetitions + 1):
                        check_frozen()
                        if file_hash(config_path) != candidate["config_sha256"]:
                            raise SweepError("applied config hash mismatch")
                        run_id = f"locked-rsi-{candidate['generation'].lower()}-{phase}-r{repetition:02d}"
                        run_dir = gen_dir / phase / f"r{repetition:02d}"
                        result_path = run_dir / "result.json"
                        state = run_dir / "state"
                        command = [str(args.executable), str(suite), str(state), str(result_path), run_id, VARIANT]
                        entry = {"run_id": run_id, "command_audit": str((run_dir / "command.json").relative_to(output)),
                                 "command": command, "cwd": str(args.repo), "environment": env,
                                 "status": "launch_pending", "returncode": None}
                        gen[phase + "_runs"].append(entry)
                        save_json(gen_dir / "manifest.json", gen)
                        try:
                            audit = capture_process(command, args.repo, env, run_dir, args.timeout_seconds)
                        except BaseException:
                            if (run_dir / "command.json").is_file():
                                interrupted_audit = load_object((run_dir / "command.json").read_bytes(), "interrupted command audit")
                                entry.update({"status": interrupted_audit.get("status", "interrupted"),
                                              "returncode": interrupted_audit.get("returncode")})
                            else:
                                entry["status"] = "interrupted_before_audit"
                            save_json(gen_dir / "manifest.json", gen)
                            raise
                        entry.update({"status": audit["status"], "returncode": audit.get("returncode")})
                        save_json(gen_dir / "manifest.json", gen)
                        require_success(audit, "benchmark")
                        if not result_path.is_file():
                            raise SweepError("benchmark produced no result JSON")
                        # Keep raw stdout as emitted; compare JSON values with emitted result.
                        result = load_object(result_path.read_bytes(), "benchmark result")
                        stdout_result = load_object((run_dir / "stdout.log").read_bytes(), "benchmark stdout")
                        if result != stdout_result:
                            raise SweepError("benchmark stdout/result JSON mismatch")
                        tool_audit = proof_tool_audit(state)
                        save_json(run_dir / "proof-tool-audit.json", tool_audit)
                        if tool_audit["fatal_exit_codes"] or tool_audit["infrastructure_error_count"]:
                            entry["status"] = "invalid_tool_failure"
                            save_json(gen_dir / "manifest.json", gen)
                            raise SweepError("Lean proof execution had infrastructure failures; baseline/result is invalid")
                        metric = validate_result(result, mapping, run_id, phase)
                        save_json(run_dir / "metrics.json", metric)
                        entry.update({"status": "valid", "result_sha256": file_hash(result_path),
                                      "metrics_sha256": file_hash(run_dir / "metrics.json")})
                        gen["feedback_record_ids"].append(run_id)
                        metrics.append(metric)
                        check_frozen()
                        save_json(gen_dir / "manifest.json", gen)
                aggregate = aggregate_repetitions(metrics)
                gen[phase + "_metrics"] = aggregate
                gen["status"] = phase + "_complete"
                save_json(gen_dir / "manifest.json", gen)
                return aggregate

            manifest["status"] = "validation_running"
            save_json(output / "manifest.json", manifest)
            champion = plan[0]
            champion_metrics = evaluate(champion, "validation", args.validation_suite, validation_map)
            champion["manifest"]["selection"] = {"retained_as_champion": True, "reason": "baseline"}
            save_json(champion["path"].parent / "manifest.json", champion["manifest"])
            for candidate in plan[1:]:
                metrics = evaluate(candidate, "validation", args.validation_suite, validation_map)
                chosen, reason = select_candidate(champion_metrics, metrics)
                candidate["manifest"]["selection"] = {"selected_at_this_step": chosen, "reason": reason,
                    "compared_champion": champion["generation"], "feedback_record_ids": metrics["feedback_record_ids"] + champion_metrics["feedback_record_ids"]}
                save_json(candidate["path"].parent / "manifest.json", candidate["manifest"])
                if chosen:
                    champion, champion_metrics = candidate, metrics
            check_frozen()
            selection = {"locked_at": utc_now(), "status": "validation_selection_locked", "frozen_inputs": frozen,
                         "selected_generation": champion["generation"], "selected_config_sha256": champion["config_sha256"],
                         "selected_config_path": str(champion["path"]), "validation_metrics": champion_metrics,
                         "all_validation_complete": True, "official_promotion": False}
            save_json(output / "selection.lock.json", selection)
            manifest["selection"] = selection
            if not args.validation_only:
                manifest["status"] = "final_holdout_running"
                save_json(output / "manifest.json", manifest)
                # This is the first semantic read of final holdout suite contents.
                holdout_map = suite_mapping(args.holdout_suite, "holdout")
                baseline_holdout = evaluate(plan[0], "holdout", args.holdout_suite, holdout_map)
                # If baseline wins, the same paired measurements serve both labels.
                selected_holdout = baseline_holdout if champion is plan[0] else evaluate(champion, "holdout", args.holdout_suite, holdout_map)
                regression = sorted(set(baseline_holdout["stable_solved_case_ids"]) - set(selected_holdout["stable_solved_case_ids"]))
                manifest["final_holdout_comparison"] = {"baseline": baseline_holdout, "selected": selected_holdout,
                    "regressed_case_ids": regression, "non_regression": not regression,
                    "used_for_selection": False, "baseline_reused_when_selected": champion is plan[0]}
            check_frozen()
            manifest["status"] = "validation_complete" if args.validation_only else "complete"
    except BaseException as exc:
        manifest["status"] = "interrupted" if isinstance(exc, (KeyboardInterrupt, InterruptedError)) else "failed"
        manifest["error"] = {"type": type(exc).__name__, "message": str(exc)}
        for candidate in plan:
            gen = candidate.get("manifest")
            if gen and gen["status"].endswith("_running"):
                gen["status"] = manifest["status"]
                gen["error"] = manifest["error"]
                save_json(candidate["path"].parent / "manifest.json", gen)
        raise
    finally:
        restoration_error = None
        try:
            if original is not None:
                # This outer restoration also protects failures outside per-gen contexts.
                atomic_write(config_path, original, original_mode)
                manifest["original_config_restored"] = config_path.read_bytes() == original
                manifest["restored_config_sha256"] = file_hash(config_path)
            else:
                manifest["original_config_restored"] = "no config mutation occurred"
        except BaseException as exc:
            restoration_error = exc
            manifest["status"] = "restoration_failed"
            manifest["original_config_restored"] = False
            manifest["restoration_error"] = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            manifest["finished_at"] = utc_now()
            try:
                save_json(output / "manifest.json", manifest)
            finally:
                if lock_active:
                    lock.__exit__(None, None, None)
        if restoration_error is not None:
            raise SweepError("original configuration restoration failed; recover from original-proof-search.json") from restoration_error
    return manifest


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        manifest = run(args)
    except (Exception, KeyboardInterrupt) as exc:
        print(f"Sweep failed: {exc}. Preserved evidence: {args.output_dir}", file=sys.stderr)
        return 130 if isinstance(exc, (KeyboardInterrupt, InterruptedError)) else 1
    print(json.dumps({"status": manifest["status"], "selected_generation": manifest["selection"]["selected_generation"],
                      "output_dir": str(args.output_dir), "original_config_restored": manifest["original_config_restored"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
