"""Bounded experimental subsystem supervisor; no arbitrary command execution.

The caller supplies probe and recovery functions. The supervisor cannot grant
permissions, edit production code, or promote a candidate by itself.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

_LEDGER_LOCK = threading.RLock()


@dataclass(frozen=True)
class RecoveryPolicy:
    max_repairs: int = 1
    require_independent_verification: bool = True

    def __post_init__(self):
        if not 0 <= self.max_repairs <= 3:
            raise ValueError("max_repairs must be between 0 and 3")


class EvidenceLedger:
    """Append-only hash-linked JSONL records with durable flush."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, event: dict) -> dict:
        with _LEDGER_LOCK:
            return self._append_locked(event)

    def _append_locked(self, event: dict) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        previous = self.verify()
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_hash": previous,
            "event": event,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["hash"] = hashlib.sha256(canonical.encode()).hexdigest()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return payload

    def verify(self) -> str:
        with _LEDGER_LOCK:
            return self._verify_locked()

    def _verify_locked(self) -> str:
        previous = "0" * 64
        if not self.path.exists():
            return previous
        for line in self.path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            recorded = entry.pop("hash")
            actual = hashlib.sha256(
                json.dumps(entry, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if entry["previous_hash"] != previous or recorded != actual:
                raise ValueError("evidence ledger integrity failure")
            previous = recorded
        return previous


class ExperimentalSupervisor:
    def __init__(self, ledger: EvidenceLedger, policy: RecoveryPolicy | None = None):
        self.ledger = ledger
        self.policy = policy or RecoveryPolicy()

    def recover(
        self,
        subsystem: str,
        probe: Callable[[], bool],
        repair: Callable[[], None],
        verify: Callable[[], bool],
        rollback: Callable[[], None],
        *,
        sandbox: bool = False,
    ) -> str:
        if not subsystem or not subsystem.replace("_", "").replace("-", "").isalnum():
            raise ValueError("invalid subsystem identifier")
        if not sandbox:
            self.ledger.append({"subsystem": subsystem, "state": "blocked_not_sandbox"})
            return "blocked"
        try:
            healthy = probe()
            if type(healthy) is not bool:
                raise TypeError("probe must return bool")
        except Exception as exc:
            self.ledger.append({"subsystem": subsystem, "state": "probe_error", "error_type": type(exc).__name__})
            healthy = False
        if healthy:
            self.ledger.append({"subsystem": subsystem, "state": "healthy"})
            return "healthy"
        self.ledger.append({"subsystem": subsystem, "state": "fault_detected"})
        for attempt in range(self.policy.max_repairs):
            try:
                repair()
                if self.policy.require_independent_verification and verify is probe:
                    raise ValueError("independent verifier required")
                probe_result = probe()
                verify_result = verify()
                if type(probe_result) is not bool or type(verify_result) is not bool:
                    raise TypeError("probe and verifier must return bool")
                if not probe_result or not verify_result:
                    raise RuntimeError("post-repair verification failed")
                self.ledger.append({"subsystem": subsystem, "state": "verified_recovery", "attempt": attempt + 1})
                return "recovered"
            except Exception as exc:
                self.ledger.append({"subsystem": subsystem, "state": "repair_failed", "attempt": attempt + 1, "error_type": type(exc).__name__})
                try:
                    rollback()
                    self.ledger.append({"subsystem": subsystem, "state": "rolled_back"})
                except Exception as rollback_error:
                    self.ledger.append({"subsystem": subsystem, "state": "rollback_failed", "error_type": type(rollback_error).__name__})
                    return "escalate"
        self.ledger.append({"subsystem": subsystem, "state": "escalate"})
        return "escalate"
