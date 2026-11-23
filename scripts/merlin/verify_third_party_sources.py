#!/usr/bin/env python3
"""Verify pinned optional upstream sources before executing third-party code."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def git(*arguments):
    result = subprocess.run(["git", *map(str, arguments)], text=True,
                            capture_output=True, timeout=10, check=False)
    if result.returncode:
        raise ValueError("Git source verification failed")
    return result.stdout.strip()


def verify(repo):
    root = Path(repo).resolve()
    manifest = json.loads((root / "config/merlin/third-party-sources.json").read_text(encoding="utf-8"))
    problems = []
    for entry in manifest.get("components", []):
        name = entry["name"]
        relative = entry["path"]
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_dir():
            problems.append(name + ": source missing or escapes checkout")
            continue
        expected_url = entry["repository"] + ".git"
        try:
            submodule_url = git("config", "-f", root / ".gitmodules",
                                "--get", "submodule." + relative + ".url")
            if submodule_url != expected_url:
                problems.append(name + ": submodule URL mismatch")
            if git("-C", path, "rev-parse", "HEAD") != entry["source_commit"]:
                problems.append(name + ": source commit mismatch")
            if git("-C", path, "status", "--porcelain", "--untracked-files=no"):
                problems.append(name + ": tracked source files modified")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            problems.append(name + ": cannot verify Git source identity")
        expected_license = "Apache License" if entry["license"] == "Apache-2.0" else "MIT License"
        license_path = (path / entry["license_file"]).resolve()
        if not license_path.is_relative_to(path):
            problems.append(name + ": invalid license path")
            continue
        try:
            contents = license_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            contents = ""
        if expected_license not in contents:
            problems.append(name + ": expected license notice missing")
    if len(manifest.get("components", [])) != 2:
        problems.append("expected exactly two pinned components")
    return problems


def main():
    root = Path(__file__).resolve().parents[2]
    problems = verify(root)
    if problems:
        for problem in problems:
            print("SOURCE CHECK FAILED:", problem, file=sys.stderr)
        return 1
    print("Two optional upstream source commits and license notices verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
