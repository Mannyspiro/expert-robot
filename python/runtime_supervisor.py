"""Bind experimental recovery to an explicitly configured JSONL worker.

The process runs with the caller's OS privileges. ``sandbox=True`` is a caller
attestation that the surrounding execution environment is isolated; this
adapter does not create a security sandbox. A failed user request is never
replayed. An independently supplied reference checker admits a replacement.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Sequence

from experimental_self_healing import EvidenceLedger, ExperimentalSupervisor, RecoveryPolicy
from orchestrator import RuntimeProcess


class RuntimeSupervisor:
    def __init__(
        self,
        command: str | Sequence[str],
        ledger: EvidenceLedger,
        *,
        verification_request: tuple[str, str],
        verify_response: Callable[[dict], bool],
        probe_request: tuple[str, str] = ("health", "check"),
        subsystem: str = "cpp_runtime",
        policy: RecoveryPolicy | None = None,
        request_timeout: float = 5.0,
        shutdown_timeout: float = 1.0,
    ):
        self.command = (command,) if isinstance(command, str) else tuple(command)
        if not self.command or any(not isinstance(part, str) or not part for part in self.command):
            raise ValueError("runtime command must contain nonempty strings")
        for request in (verification_request, probe_request):
            if not isinstance(request, tuple) or len(request) != 2 or any(not isinstance(x, str) or not x for x in request):
                raise ValueError("probe and verification requests must be nonempty (role, task) pairs")
        if not callable(verify_response):
            raise ValueError("an independent response checker is required")
        self.ledger = ledger
        self.supervisor = ExperimentalSupervisor(ledger, policy)
        self.subsystem = subsystem
        self.verification_request = verification_request
        self.probe_request = probe_request
        self.verify_response = verify_response
        self.request_timeout = request_timeout
        self.shutdown_timeout = shutdown_timeout
        self.runtime: RuntimeProcess | None = None
        self._lock = threading.RLock()
        # This is a command identity, not a hash of the executable or model.
        self.command_sha256 = hashlib.sha256(json.dumps(self.command).encode()).hexdigest()

    def ensure_healthy(self, *, sandbox: bool = False) -> str:
        """Probe, or replace once within policy, then check a separate reference task."""
        with self._lock:
            return self.supervisor.recover(
                self.subsystem, self._probe, self._replace, self._verify,
                self._rollback, sandbox=sandbox,
            )

    def _probe(self) -> bool:
        if self.runtime is None or not self.runtime.running:
            return False
        try:
            return self.runtime.request(*self.probe_request).get("ok") is True
        except (OSError, RuntimeError, ValueError, TimeoutError):
            return False

    def _replace(self) -> None:
        if self.runtime is not None:
            self.runtime.close()
        self.runtime = RuntimeProcess(
            self.command, request_timeout=self.request_timeout,
            shutdown_timeout=self.shutdown_timeout,
        )
        self.ledger.append({
            "subsystem": self.subsystem, "state": "runtime_spawned",
            "pid": self.runtime.pid, "command_sha256": self.command_sha256,
        })

    def _verify(self) -> bool:
        if self.runtime is None:
            return False
        response = self.runtime.request(*self.verification_request)
        accepted = self.verify_response(response)
        if type(accepted) is not bool:
            raise TypeError("independent checker must return bool")
        self.ledger.append({
            "subsystem": self.subsystem, "state": "runtime_reference_check",
            "pid": self.runtime.pid, "accepted": accepted,
            "response_sha256": hashlib.sha256(
                json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        })
        return accepted

    def _rollback(self) -> None:
        # Restore the stopped state, never a known-failed worker or an old task.
        if self.runtime is not None:
            self.runtime.close()
            if self.runtime.running or self.runtime._proc.poll() is None:
                raise RuntimeError("replacement process did not stop")
            self.runtime = None

    def request(self, role: str, task: str) -> dict:
        """Send one user request. Failures return to the caller without replay."""
        with self._lock:
            if self.runtime is None:
                raise RuntimeError("runtime has not passed recovery admission")
            return self.runtime.request(role, task)

    def close(self) -> None:
        with self._lock:
            self._rollback()

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self.runtime is not None and self.runtime.running,
                "pid": self.runtime.pid if self.runtime else None,
                "unresolved_recovery": self.subsystem in self.ledger.pending_recoveries(),
                "command_sha256": self.command_sha256,
            }
