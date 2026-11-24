#!/usr/bin/env python3
"""Opt-in bounded supervisor for deterministic, synthetic research only.

Exclusive POSIX advisory lock prevents concurrent invocations sharing a
checkpoint. Each completed step is durably checkpointed by run_episode.
Crash before checkpoint can replay a *pure synthetic* computation: this is
not an exactly-once guarantee for external tools, models or side effects.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import sys

from merlin_research_episode import run_episode, load_or_initialize

SCHEMA = "merlin-explicit-research-supervisor/1"


def supervise(checkpoint: Path, *, max_invocations: int = 3) -> dict:
    if type(max_invocations) is not int or not 1 <= max_invocations <= 3:
        raise ValueError("bounded invocation count 1..3 required")
    checkpoint = Path(checkpoint)
    if checkpoint.is_symlink() or checkpoint.parent.is_symlink():
        raise ValueError("symlink checkpoint or parent refused")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    lock_path = checkpoint.with_name(checkpoint.name + ".lock")
    if lock_path.is_symlink():
        raise ValueError("symlink lock refused")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock_path, flags, 0o600)
    try:
        with os.fdopen(fd, "r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            initial = load_or_initialize(checkpoint)
            before = len(initial.receipts)
            latest = []
            for _ in range(max_invocations):
                if not load_or_initialize(checkpoint).queue and checkpoint.exists():
                    break
                result = run_episode(checkpoint, 1)
                latest.extend(result["latest_receipts"])
                if not result["latest_receipts"] or result["latest_receipts"][-1]["status"] != "checked":
                    break
            final = load_or_initialize(checkpoint)
            return {"schema": SCHEMA, "checkpoint": str(checkpoint),
                    "steps_before": before, "steps_after": len(final.receipts),
                    "new_task_ids": [r["task_id"] for r in latest],
                    "summary": final.summary(), "lock": "exclusive_nonblocking",
                    "external_side_effects": False, "background_worker_running": False,
                    "exactly_once_external_execution_proven": False,
                    "production_qualified": False}
    except BlockingIOError as exc:
        raise RuntimeError("research checkpoint already supervised") from exc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--max-invocations", type=int, default=3)
    args = p.parse_args()
    print(json.dumps(supervise(args.checkpoint, max_invocations=args.max_invocations),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
