#!/usr/bin/env python3
"""Execute one hash-bound Merlin geometry job inside an isolated FreeCAD runtime.

The host/Avrea runner must enforce OS-level CPU, memory, process, time, network
and filesystem limits. This program validates contracts and artifact hashes; it
is not a sandbox.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
ARCHIVE_INTAKE = HERE.parent
if str(ARCHIVE_INTAKE) not in sys.path:
    sys.path.insert(0, str(ARCHIVE_INTAKE))

from cad_geometry_backend import execute_job


def _freecad_backend():
    import FreeCAD as App
    version_parts = App.Version()
    version = ".".join(str(part) for part in version_parts)
    from freecad_adapter import FreeCADBackend
    return FreeCADBackend.from_freecad_runtime(version)


def run_request(
    request_path: Path,
    input_root: Path,
    output_dir: Path,
    *,
    backend_factory: Callable[[], object] = _freecad_backend,
) -> dict:
    request_path = request_path.resolve(strict=True)
    input_root = input_root.resolve(strict=True)
    if not request_path.is_file():
        raise ValueError("job request must be a regular file")
    if not input_root.is_dir():
        raise ValueError("input root must be a directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir.resolve(strict=True)
    if output_dir == input_root or input_root in output_dir.parents or output_dir in input_root.parents:
        raise ValueError("input and output workspaces must be separate, non-nested directories")

    request = json.loads(request_path.read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise ValueError("job request JSON must contain an object")
    backend = backend_factory()
    receipt = execute_job(request, input_root, output_dir, backend)

    # Atomic receipt write: consumers never observe a partially written JSON.
    payload = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".geometry-receipt-", dir=output_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output_dir / "geometry-receipt.json")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, default=Path("/work/input/job.json"))
    parser.add_argument("--input-root", type=Path, default=Path("/work/input"))
    parser.add_argument("--output-dir", type=Path, default=Path("/work/output"))
    args = parser.parse_args()
    try:
        receipt = run_request(args.request, args.input_root, args.output_dir)
    except Exception as exc:
        print(json.dumps({
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({
        "status": receipt["status"],
        "job_id": receipt["job_id"],
        "receipt_sha256": receipt["receipt_sha256"],
        "artifact_count": len(receipt["artifacts"]),
        "receipt_path": str(args.output_dir / "geometry-receipt.json"),
    }, sort_keys=True))
    return 0 if receipt["status"] == "completed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
