"""Read-only host preflight for the OCI-first / GitLab-fallback build path."""
import argparse
import json
import shutil
import socket
import subprocess
from pathlib import Path


def inspect(root: Path, expected_sha: str | None = None) -> dict:
    root = root.resolve()
    checks = {"checkout": (root / ".git").exists(),
              "tools": {name: shutil.which(name) is not None for name in
                        ("git", "python3", "cmake", "ninja")}}
    for host in ("github.com", "gitlab.com"):
        try:
            socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            checks["dns_" + host] = True
        except OSError:
            checks["dns_" + host] = False
    checks["sha"] = None
    checks["clean"] = False
    if checks["checkout"] and checks["tools"]["git"]:
        def git(*args):
            try:
                result = subprocess.run(["git", "-C", str(root), *args],
                                        capture_output=True, text=True, timeout=10)
                return result.stdout.strip() if result.returncode == 0 else None
            except (OSError, subprocess.TimeoutExpired):
                return None
        checks["sha"] = git("rev-parse", "HEAD")
        checks["clean"] = git("status", "--porcelain") == ""
    checks["expected_sha_matches"] = expected_sha is None or checks["sha"] == expected_sha
    checks["offline_ci_script"] = (root / "scripts/run_merlin_offline_ci.sh").is_file()
    ready = bool(checks["checkout"] and checks["sha"] and checks["clean"]
                 and checks["expected_sha_matches"] and checks["offline_ci_script"]
                 and all(checks["tools"].values()))
    return {"schema": "merlin-hybrid-preflight/1", "root": str(root),
            "checks": checks, "ready": ready}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-sha")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = inspect(args.root, args.expected_sha)
    data = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
