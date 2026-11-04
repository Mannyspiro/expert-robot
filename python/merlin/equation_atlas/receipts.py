"""Create a content-addressed evidence receipt for a reproducible experiment artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--command", default="python3 -m merlin.equation_atlas.experiments.baseline")
    args = parser.parse_args()
    if not args.artifact.is_file():
        raise SystemExit(f"artifact not found: {args.artifact}")
    sources = {name: sha256(Path(name)) for name in args.source}
    receipt = {
        "receipt_schema": "merlin-evidence-receipt/0.1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim_scope": "synthetic reproducibility baseline; not empirical validation",
        "git_commit": os.environ.get("GITHUB_SHA", "local-unpinned"),
        "git_ref": os.environ.get("GITHUB_REF", "local"),
        "command": args.command,
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
        },
        "source_sha256": sources,
        "artifact": {
            "path": str(args.artifact),
            "sha256": sha256(args.artifact),
            "bytes": args.artifact.stat().st_size,
        },
        "verification_boundary": [
            "A matching artifact hash establishes byte identity, not model truth.",
            "Synthetic experiments do not establish empirical validity.",
            "Lean status is not inferred from this receipt.",
        ],
    }
    schema_path = Path("docs/research/real-world-equation-atlas/evidence-receipt.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(receipt))
    if errors:
        raise SystemExit("Invalid evidence receipt: " + "; ".join(error.message for error in errors))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"PASS evidence receipt: {args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
