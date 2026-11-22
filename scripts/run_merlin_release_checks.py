#!/usr/bin/env python3
"""Run repository release gate tests and fail-closed CLI without GitHub Actions."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time


def run(argv, cwd):
    started = time.monotonic()
    process = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=180)
    return {"argv": argv, "returncode": process.returncode,
            "stdout": process.stdout[-16000:], "stderr": process.stderr[-16000:],
            "elapsed_seconds": round(time.monotonic() - started, 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("merlin-release-local-report.json"))
    args = parser.parse_args()
    repo = args.repo.resolve()
    files = [repo / "python/merlin_release_gate.py", repo / "tests/test_merlin_release_gate.py"]
    if any(not path.is_file() for path in files):
        parser.error("release gate source/test files missing in --repo")
    report = {"runtime": {"python": sys.version, "platform": platform.platform()},
              "sources": {str(path.relative_to(repo)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
              "checks": []}
    with tempfile.TemporaryDirectory() as directory:
        manifest = Path(directory) / "empty.json"
        manifest.write_text(json.dumps({"gates": {}}), encoding="utf-8")
        checks = [
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_merlin_release_gate.py", "-v"],
            [sys.executable, "-B", str(files[0]), str(manifest), "--evidence-root", directory],
        ]
        for index, command in enumerate(checks):
            try:
                result = run(command, repo)
            except (OSError, subprocess.TimeoutExpired) as exc:
                result = {"argv": command, "error": str(exc), "returncode": None}
            expected = 0 if index == 0 else 1
            result["expected_returncode"] = expected
            result["passed"] = result.get("returncode") == expected
            if index == 1 and result["passed"]:
                try:
                    payload = json.loads(result["stdout"])
                    result["passed"] = (
                        payload.get("ready_for_independent_review") is False
                        and all(value == "missing" for value in payload.get("gate_status", {}).values())
                        and len(payload.get("gate_status", {})) == 9
                    )
                except (ValueError, TypeError, AttributeError):
                    result["passed"] = False
                result["semantic_negative_control"] = result["passed"]
            report["checks"].append(result)
    report["passed"] = all(check["passed"] for check in report["checks"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(args.output),
                      "checks": [(check["passed"], check.get("returncode")) for check in report["checks"]]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
