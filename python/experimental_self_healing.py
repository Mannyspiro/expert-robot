"""Bounded experimental subsystem supervisor; no arbitrary command execution.

The caller supplies probe and recovery functions. The supervisor cannot grant
permissions, edit production code, or promote a candidate by itself.
"""
from __future__ import annotations

import hashlib
import contextlib
import errno
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

_LEDGER_LOCK = threading.RLock()
_RECOVERY_LOCKS: dict[tuple[str, str], threading.Lock] = {}


@contextlib.contextmanager
def _advisory_lock(path: Path, *, blocking: bool = True):
    """Cooperating-process lock on POSIX and Windows; never an authority boundary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            if not path.stat().st_size:
                handle.write(b"\0")
                handle.flush()
            def lock():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            def unlock():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            def lock():
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            def unlock():
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        while True:
            try:
                lock()
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                if not blocking:
                    yield False
                    return
                time.sleep(0.01)
        try:
            yield True
        finally:
            unlock()


@dataclass(frozen=True)
class RecoveryPolicy:
    max_repairs: int = 1
    require_independent_verification: bool = True

    def __post_init__(self):
        if type(self.max_repairs) is not int or not 0 <= self.max_repairs <= 3:
            raise ValueError("max_repairs must be between 0 and 3")
        if type(self.require_independent_verification) is not bool:
            raise ValueError("require_independent_verification must be bool")


class EvidenceLedger:
    """Append-only hash-linked JSONL records with durable flush."""

    def __init__(self, path: Path):
        self.path = Path(path)

    @contextlib.contextmanager
    def _locked(self):
        """Cross-process advisory lock; all writers must cooperate."""
        with _LEDGER_LOCK:
            with _advisory_lock(self.path.with_suffix(self.path.suffix + ".lock")):
                yield

    @contextlib.contextmanager
    def recovery_guard(self, subsystem: str):
        """Own the entire recovery, including callbacks, without waiting for a peer."""
        key = (str(self.path.resolve()), subsystem)
        with _LEDGER_LOCK:
            thread_lock = _RECOVERY_LOCKS.setdefault(key, threading.Lock())
        if not thread_lock.acquire(blocking=False):
            yield False
            return
        try:
            lock_path = self.path.with_name(self.path.name + ".recover-" + subsystem + ".lock")
            with _advisory_lock(lock_path, blocking=False) as acquired:
                yield acquired
        finally:
            thread_lock.release()

    def append(self, event: dict) -> dict:
        with self._locked():
            return self._append_locked(event)

    def _append_locked(self, event: dict) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        previous = self._verify_locked()
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

    def pending_recoveries(self) -> set[str]:
        """Detect interrupted repair attempts on restart; never resume automatically."""
        with self._locked():
            self._verify_locked()
            pending: dict[str, set[str]] = {}
            if not self.path.exists():
                return set()
            for line in self.path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)["event"]
                subsystem = event.get("subsystem")
                if not isinstance(subsystem, str):
                    continue
                recovery_id = event.get("recovery_id", "legacy")
                if not isinstance(recovery_id, str):
                    raise ValueError("invalid recovery identity")
                if event.get("state") == "repair_started":
                    pending.setdefault(subsystem, set()).add(recovery_id)
                elif event.get("state") in ("verified_recovery", "rolled_back"):
                    pending.get(subsystem, set()).discard(recovery_id)
            return {name for name, attempts in pending.items() if attempts}

    def verify(self) -> str:
        with self._locked():
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
        if not isinstance(subsystem, str) or not subsystem or not subsystem.isascii() or not subsystem.replace("_", "").replace("-", "").isalnum():
            raise ValueError("invalid subsystem identifier")
        if sandbox is not True:
            self.ledger.append({"subsystem": subsystem, "state": "blocked_not_sandbox"})
            return "blocked"
        with self.ledger.recovery_guard(subsystem) as acquired:
            if not acquired:
                self.ledger.append({"subsystem": subsystem, "state": "recovery_busy"})
                return "busy"
            return self._recover_owned(subsystem, probe, repair, verify, rollback)

    def _recover_owned(self, subsystem, probe, repair, verify, rollback):
        # An escalation is an observation, not evidence that an interrupted
        # mutation was verified or undone. Check before even a healthy probe.
        if subsystem in self.ledger.pending_recoveries():
            self.ledger.append({"subsystem": subsystem, "state": "escalate", "reason": "interrupted_repair"})
            return "escalate"
        try:
            healthy = probe()
            if type(healthy) is not bool:
                raise TypeError("probe must return bool")
        except Exception as exc:
            self.ledger.append({"subsystem": subsystem, "state": "probe_error", "error_type": type(exc).__name__})
            self.ledger.append({"subsystem": subsystem, "state": "escalate", "reason": "probe_unavailable"})
            return "escalate"
        if healthy:
            self.ledger.append({"subsystem": subsystem, "state": "healthy"})
            return "healthy"
        if self.policy.require_independent_verification and verify is probe:
            self.ledger.append({"subsystem": subsystem, "state": "escalate", "reason": "independent_verifier_required"})
            return "escalate"
        self.ledger.append({"subsystem": subsystem, "state": "fault_detected"})
        for attempt in range(self.policy.max_repairs):
            identity = {"subsystem": subsystem, "attempt": attempt + 1, "recovery_id": str(uuid.uuid4())}
            try:
                self.ledger.append({**identity, "state": "repair_started"})
                repair()
                probe_result = probe()
                verify_result = verify()
                if type(probe_result) is not bool or type(verify_result) is not bool:
                    raise TypeError("probe and verifier must return bool")
                if not probe_result or not verify_result:
                    raise RuntimeError("post-repair verification failed")
                self.ledger.append({**identity, "state": "verified_recovery"})
                return "recovered"
            except Exception as exc:
                # Evidence IO may be the failing operation. Undo the mutation
                # before another write, so a full disk cannot skip rollback.
                rollback_error = None
                try:
                    rollback()
                except Exception as error:
                    rollback_error = error
                self.ledger.append({**identity, "state": "repair_failed", "error_type": type(exc).__name__})
                if rollback_error is not None:
                    self.ledger.append({**identity, "state": "rollback_failed", "error_type": type(rollback_error).__name__})
                    return "escalate"
                self.ledger.append({**identity, "state": "rolled_back"})
        self.ledger.append({"subsystem": subsystem, "state": "escalate"})
        return "escalate"

