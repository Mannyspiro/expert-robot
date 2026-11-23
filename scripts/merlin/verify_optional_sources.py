#!/usr/bin/env python3
"""Check exact optional Graft/OpenSandbox gitlinks and notices before reuse."""
import json
from pathlib import Path
import subprocess
import sys


def git(*arguments):
    p = subprocess.run(["git", *map(str, arguments)], text=True,
                       capture_output=True, timeout=20, check=False)
    if p.returncode:
        raise ValueError("git source identity query failed")
    return p.stdout.strip()


def verify(repo_root):
    root = Path(repo_root).resolve()
    manifest = json.loads((root / "config/merlin/optional-source-candidates.json").read_text())
    problems = []
    components = manifest.get("components")
    if not isinstance(components, list) or len(components) != 2:
        return ["expected exactly two pinned optional source candidates"]
    for item in components:
        relative = item["path"]
        src = (root / relative).resolve()
        if not src.is_relative_to(root) or not src.is_dir():
            problems.append(relative + ": source missing")
            continue
        expected = item["source_commit"]
        try:
            if git("-C", src, "rev-parse", "HEAD") != expected:
                problems.append(relative + ": source SHA mismatch")
            if git("-C", src, "status", "--porcelain", "--untracked-files=no"):
                problems.append(relative + ": dirty tracked source")
            gitlink = git("-C", root, "ls-tree", "HEAD", relative).split()
            if len(gitlink) < 3 or gitlink[:2] != ["160000", "commit"] or gitlink[2] != expected:
                problems.append(relative + ": parent gitlink mismatch")
            url = git("config", "-f", root / ".gitmodules", "--get", "submodule." + relative + ".url")
            if url != item["repository"] + ".git":
                problems.append(relative + ": URL mismatch")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            problems.append(relative + ": unverified git source")
        try:
            license_content = (src / "LICENSE").read_text(encoding="utf-8")
            if "Apache License" not in license_content or "Version 2.0" not in license_content:
                problems.append(relative + ": Apache 2.0 license notice missing")
            if relative.endswith("/graft") and not (src / "NOTICE").is_file():
                problems.append(relative + ": NOTICE missing")
        except (OSError, UnicodeError):
            problems.append(relative + ": license not readable")
    return problems


def main():
    problems = verify(Path(__file__).resolve().parents[2])
    if problems:
        for message in problems:
            print("FAIL:", message, file=sys.stderr)
        return 1
    print("OpenSandbox and Graft optional source gitlinks and licenses verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
