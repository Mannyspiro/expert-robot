#!/usr/bin/env python3
"""Inventory research-relevant interfaces in a checked-out CACE repository.

This tool performs static, read-only analysis. It emits only paths, declaration
snippets, and API hints; it never prints secret values and never mutates the
target repository.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re


KEYWORDS = {
    "mesh": 5,
    "solver": 5,
    "residual": 5,
    "operator": 5,
    "certificate": 5,
    "interval": 4,
    "geometry": 4,
    "shape": 3,
    "coordinate": 3,
    "fem": 5,
    "maxwell": 5,
    "acoustic": 5,
    "capabilit": 3,
    "graph": 2,
    "validate": 3,
    "simulation": 4,
    "pde": 5,
    "flux": 4,
    "error": 2,
    "adaptive": 4,
    "bound": 3,
}

EXTENSIONS = {
    ".py",
    ".cpp",
    ".cc",
    ".cxx",
    ".hpp",
    ".h",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".lean",
    ".rs",
    ".go",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
}

DECLARATION = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?"
    r"(?:class|def|function|interface|type|struct|enum|namespace|"
    r"theorem|lemma|inductive|structure)\s+[^\s({:]+"
)


def inventory(root: pathlib.Path) -> dict:
    rows = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        if any(
            part in {".git", "node_modules", "vendor", "dist", "build"}
            for part in path.parts
        ):
            continue

        try:
            size = path.stat().st_size
            if size > 1_000_000:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        rel = path.relative_to(root).as_posix()
        haystack = (rel + "\n" + content[:20000]).lower()
        score = sum(
            weight
            for key, weight in KEYWORDS.items()
            if key in haystack
        )
        if score <= 0:
            continue

        declarations = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            low = line.lower()
            if DECLARATION.search(line) or "/api/" in low or "api/" in low:
                declarations.append(
                    {
                        "line": line_no,
                        "text": line.strip()[:240],
                    }
                )
            if len(declarations) >= 20:
                break

        rows.append(
            {
                "path": rel,
                "score": score,
                "size": size,
                "declarations": declarations,
            }
        )

    rows.sort(key=lambda row: (-row["score"], row["path"]))
    return {
        "schema_version": 1,
        "candidate_count": len(rows),
        "candidates": rows[:100],
        "remote_mutated": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=pathlib.Path)
    parser.add_argument("output_dir", type=pathlib.Path)
    parser.add_argument("--repository", default="morganaspim/Cace-app")
    parser.add_argument("--commit-file", type=pathlib.Path)
    args = parser.parse_args()

    payload = inventory(args.root)
    payload["repository"] = args.repository
    if args.commit_file and args.commit_file.exists():
        payload["commit"] = args.commit_file.read_text(
            encoding="utf-8"
        ).strip()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = args.output_dir / "inventory.json"
    destination.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
