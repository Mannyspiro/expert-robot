"""Exact-source focused test gate; not a sandbox, signer or promotion authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import selectors
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

SUITES = (
    "test_merlin_prompt_contract.py",
    "test_merlin_scientific_workflow.py",
    "test_scientific_recording.py",
    "test_scientific_worker_integration.py",
    "test_hermes_worker.py",
    "test_failure_prevention.py",
    "test_hermes_teacher.py",
    "test_mathematical_methods.py",
    "test_event_outbox.py",
    "test_hypothesis_ledger.py",
    "test_scientific_loop.py",
    "test_text_extractor.py",
    "test_knowledge_compression.py",
    "test_ideonomy.py",
    "test_hermes_ideonomy_stage.py",
    "test_logos_review.py",
    "test_merlin_research_stack_gate.py",
)
MAX_TRACKED_BYTES = 256 * 1024 * 1024
_CHILD = r'''
import json, sys, unittest
from pathlib import Path
root, pattern, output = sys.argv[1:]
sys.path[:0] = [str(Path(root) / "python"), root]
suite = unittest.TestLoader().discover(str(Path(root) / "tests"), pattern=pattern)
result = unittest.TextTestRunner(verbosity=2).run(suite)
status = ("failed" if not result.wasSuccessful() else
          "incomplete" if result.testsRun == 0 or result.skipped or result.expectedFailures else
          "passed")
Path(output).write_text(json.dumps({
    "suite": pattern, "status": status, "tests_run": result.testsRun,
    "failures": len(result.failures), "errors": len(result.errors),
    "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
    "unexpected_successes": len(result.unexpectedSuccesses),
}, sort_keys=True) + "\n", encoding="utf-8")
sys.exit(0 if status == "passed" else 1)
'''


def _git(root: Path, *args: str) -> bytes:
    run = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=30)
    if run.returncode:
        # Git errors may contain credential-bearing remote URLs. Do not echo them.
        raise ValueError("Git source inspection failed; a complete local checkout is required")
    return run.stdout


def inspect_checkout(root: Path, expected_sha: str) -> dict[str, Any]:
    """Compare actual tracked bytes with Git objects, including skip-worktree files."""
    root = root.resolve()
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise ValueError("expected source SHA must be a full lowercase 40-character commit")
    top = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
    if top != root:
        raise ValueError("source root must be the Git worktree root")
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    if head != expected_sha:
        raise ValueError("checkout HEAD does not match the expected source commit")
    entries = _git(root, "ls-tree", "-rz", "--full-tree", "HEAD")
    records = [record for record in entries.split(b"\0") if record]
    if not records or len(records) > 20000:
        raise ValueError("tracked source inventory is empty or exceeds the inspection limit")
    paths: set[str] = set()
    total = 0
    for record in records:
        descriptor, raw_path = record.split(b"\t", 1)
        mode, kind, expected_blob = descriptor.decode("ascii").split()
        relative = Path(os.fsdecode(raw_path))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid tracked source path")
        paths.add(relative.as_posix())
        path = root / relative
        if any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
            raise ValueError("tracked source has a symlinked parent")
        if kind != "blob" or mode not in {"100644", "100755", "120000"}:
            raise ValueError("unsupported tracked entry; submodules require separate pinned qualification")
        try:
            before = path.lstat()
        except FileNotFoundError as exc:
            raise ValueError("tracked source file is missing") from exc
        if mode == "120000":
            raise ValueError("tracked symlinks require separate target qualification")
        else:
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("tracked source is not a regular file")
            if bool(before.st_mode & stat.S_IXUSR) != (mode == "100755"):
                raise ValueError("tracked executable mode changed")
            total += before.st_size
            if total > MAX_TRACKED_BYTES:
                raise ValueError("tracked source bytes exceed the inspection budget")
            digest_state = hashlib.sha1(b"blob " + str(before.st_size).encode() + b"\0")
            with path.open("rb") as handle:
                opened = os.fstat(handle.fileno())
                if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                    raise ValueError("source changed during inspection")
                read_bytes = 0
                while chunk := handle.read(1024 * 1024):
                    read_bytes += len(chunk)
                    if read_bytes > before.st_size:
                        raise ValueError("source grew during inspection")
                    digest_state.update(chunk)
                after = os.fstat(handle.fileno())
            if (read_bytes != before.st_size or after.st_mtime_ns != before.st_mtime_ns
                    or after.st_ctime_ns != before.st_ctime_ns):
                raise ValueError("source changed during inspection")
            digest = digest_state.hexdigest()
        if digest != expected_blob:
            raise ValueError("tracked source bytes do not match the source commit")
    if total > MAX_TRACKED_BYTES:
        raise ValueError("tracked source bytes exceed the inspection budget")
    # Reject ignored as well as visible untracked importable code in source areas.
    for area in ("python", "merlin", "tests", "scripts"):
        directory = root / area
        if directory.is_symlink():
            raise ValueError("source directory is a symlink")
        if not directory.exists():
            continue
        for base, dirs, files in os.walk(directory, followlinks=False):
            if any((Path(base) / child).is_symlink() for child in dirs):
                raise ValueError("source directory contains an uninspected symlink")
            dirs[:] = [child for child in dirs if child != "__pycache__"]
            for filename in files:
                path = Path(base) / filename
                if path.suffix in {".py", ".so", ".pyd", ".pth"} and path.relative_to(root).as_posix() not in paths:
                    raise ValueError("untracked importable source is present")
    return {"commit_sha": head, "tree_sha": _git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
            "tracked_files": len(records), "tracked_bytes": total,
            "inventory_sha256": hashlib.sha256(entries).hexdigest(),
            "working_tree_matches_commit": True}


def _stop(process: subprocess.Popen) -> None:
    """Bound this CI test process group; not an adversarial worker isolation claim."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def run_suite(root: Path, name: str, output: Path, *, timeout: float = 120,
              max_log_bytes: int = 2 * 1024 * 1024) -> dict[str, Any]:
    if not re.fullmatch(r"test_[a-z0-9_]+\.py", name):
        raise ValueError("invalid suite filename")
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or not 0 < timeout <= 600
            or type(max_log_bytes) is not int or not 1 <= max_log_bytes <= 16 * 1024 * 1024):
        raise ValueError("positive execution bounds are required")
    log_path, result_path = output / (name + ".log"), output / (name + ".json")
    if not (root / "tests" / name).is_file():
        return {"suite": name, "status": "missing", "tests_run": 0}
    result_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="merlin-focused-") as temporary:
        env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL") if key in os.environ}
        env.update(HOME=temporary, TMPDIR=temporary, PYTHONNOUSERSITE="1",
                   PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(Path(temporary) / "pycache"),
                   PYTHONPATH=os.pathsep.join((str(root / "python"), str(root))))
        started = time.monotonic()
        deadline = started + timeout
        timed_out = False
        output_limit = False
        with log_path.open("wb") as log:
            process = subprocess.Popen([sys.executable, "-c", _CHILD,
                                        str(root), name, str(result_path)], cwd=root,
                                       env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    written = 0
                    while selector.get_map() and not output_limit:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            timed_out = True
                            _stop(process)
                            break
                        for key, _ in selector.select(min(0.1, remaining)):
                            chunk = os.read(key.fd, 65536)
                            if not chunk:
                                selector.unregister(key.fileobj)
                                continue
                            room = max_log_bytes - written
                            log.write(chunk[:room])
                            written += min(len(chunk), room)
                            if len(chunk) > room:
                                output_limit = True
                                _stop(process)
                                break
                if not timed_out and not output_limit:
                    try:
                        process.wait(timeout=max(0.001, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        _stop(process)
            finally:
                if process.poll() is None:
                    _stop(process)
                process.stdout.close()
        # Kill same-group descendants even after the direct child exits.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    status = "timeout" if timed_out else "missing_result"
    result: dict[str, Any] = {"suite": name, "status": status, "tests_run": 0}
    if not timed_out and result_path.is_file():
        try:
            parsed = json.loads(result_path.read_text(encoding="utf-8"))
            if (isinstance(parsed, dict) and parsed.get("suite") == name
                    and parsed.get("status") in {"passed", "failed", "incomplete"}
                    and type(parsed.get("tests_run")) is int and parsed["tests_run"] >= 0):
                result = parsed
        except (ValueError, OSError):
            pass
    if result["status"] == "passed" and (process.returncode != 0 or result["tests_run"] == 0):
        result["status"] = "failed"
    if output_limit:
        result["status"] = "output_limit"
    result.update(exit_code=process.returncode, elapsed_seconds=round(time.monotonic() - started, 6),
                  log_sha256=hashlib.sha256(log_path.read_bytes()).hexdigest())
    return result


def run_gate(root: Path, expected_sha: str, output: Path, *, python_version: tuple[int, int] = (3, 11),
             suites: tuple[str, ...] = SUITES, timeout: float = 120) -> dict[str, Any]:
    """Run every requested suite; CLI always uses the fixed production suite set."""
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema": "merlin-research-stack-gate/1", "expected_source_commit": expected_sha,
        "required_python": ".".join(map(str, python_version)), "actual_python": sys.version.split()[0],
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "status": "blocked", "required_suites": list(suites), "suites": [], "cace_independent_verification": False,
        "production_qualification": False, "promotion_authority": False,
    }
    try:
        if sys.version_info[:2] != python_version:
            raise ValueError("Python interpreter does not match the required target version")
        report["source_before"] = inspect_checkout(root, expected_sha)
        for name in suites:
            inspect_checkout(root, expected_sha)
            try:
                result = run_suite(root, name, output, timeout=timeout)
            except (OSError, ValueError, subprocess.SubprocessError):
                result = {"suite": name, "status": "runner_error", "tests_run": 0}
            report["suites"].append(result)
        report["source_after"] = inspect_checkout(root, expected_sha)
        report["status"] = "passed" if suites and all(s["status"] == "passed" for s in report["suites"]) else "failed"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        report["blocker"] = str(exc)
    recorded = {item["suite"] for item in report["suites"]}
    report["suites"].extend({"suite": name, "status": "not_run", "tests_run": 0}
                            for name in suites if name not in recorded)
    report["limitations"] = [
        "Repository test execution only; not OS/container worker isolation or provider qualification.",
        "Byte identity and local test results are not signed independent CACE evidence.",
        "Pre/post snapshots detect lasting source changes, not adversarial transient mutation.",
        "Python package dependencies are environment inputs, not fully hermetic build evidence.",
    ]
    (output / "research-stack-result.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/research-stack"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = run_gate(root, args.expected_sha, args.output.resolve())
    print(json.dumps({"status": result["status"], "source_commit": args.expected_sha,
                      "suites_recorded": len(result["suites"]), "report": str(args.output / "research-stack-result.json")}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
