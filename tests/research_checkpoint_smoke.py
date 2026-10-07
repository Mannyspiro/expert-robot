#!/usr/bin/env python3
"""Checkpoint identity, corruption detection and bounded storage behavior."""
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import checkpoint_research_state as checkpoint

with TemporaryDirectory() as tmp:
    path = Path(tmp) / "state"
    result = checkpoint.write_checkpoint(path, "a" * 40, "123", "success", [{
        "id": 10, "name": "test", "head_sha": "a" * 40,
        "status": "completed", "conclusion": "success", "unused_secret": "must-not-be-saved",
    }])
    raw = (path / "research-checkpoint.json").read_bytes()
    entry = result["files"][0]
    assert len(raw) == entry["bytes"]
    assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
    state = json.loads(raw)
    assert state["source_commit"] == "a" * 40
    assert state["session_policy"]["commit_target_per_day"] == 20
    assert state["session_policy"]["authority_invariant"] == "Capability grows, authority never expands."
    assert state["promotion_authority"] is False
    assert b"must-not-be-saved" not in raw
    assert hashlib.sha256(raw + b"changed").hexdigest() != entry["sha256"]
    link = Path(tmp) / "linked"
    link.symlink_to(path, target_is_directory=True)
    try:
        checkpoint.write_checkpoint(link, "a" * 40, "123", "success", [])
    except ValueError:
        pass
    else:
        raise AssertionError("symlink checkpoint destination accepted")
    try:
        checkpoint.write_checkpoint(path, "invalid-head", "123", "success", [])
    except ValueError:
        pass
    else:
        raise AssertionError("checkpoint source identity accepted without validation")

    # Bound output before writing anything; large records must not consume storage.
    oversize = Path(tmp) / "oversize"
    try:
        checkpoint.write_checkpoint(oversize, "a" * 40, "123", "success", [],
                                    {"unexpected_large_record": "x" * (256 * 1024)})
    except ValueError:
        pass
    else:
        raise AssertionError("oversized checkpoint accepted")
    assert not (oversize / "research-checkpoint.json").exists()
print("runner checkpoint source binding, corruption and storage checks: PASS")
