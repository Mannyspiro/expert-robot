"""Supervised service lifecycle for the approval-gated Hermes worker.

The supervisor owns polling, backoff, readiness and graceful shutdown. It does
not construct handlers, grant approval, validate MCFC leases or dispatch work;
those remain explicit dependencies of the injected HermesWorker.
"""
from __future__ import annotations

from threading import Event, Lock, Thread
from typing import Any


class HermesWorkerService:
    """Run one injected HermesWorker in a supervised, stoppable thread."""

    def __init__(
        self,
        worker: Any,
        *,
        idle_seconds: float = 0.5,
        max_backoff_seconds: float = 10.0,
        thread_name: str = "merlin-hermes-worker",
    ):
        if not callable(getattr(worker, "run_once", None)):
            raise ValueError("worker must expose a callable run_once method")
        for value, label, maximum in (
            (idle_seconds, "idle_seconds", 60.0),
            (max_backoff_seconds, "max_backoff_seconds", 300.0),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.01 <= value <= maximum:
                raise ValueError(label + " is outside its allowed range")
        if not isinstance(thread_name, str) or not thread_name.strip() or len(thread_name) > 100:
            raise ValueError("thread_name must be a non-empty string of at most 100 characters")
        self.worker = worker
        self.idle_seconds = float(idle_seconds)
        self.max_backoff_seconds = float(max_backoff_seconds)
        self.thread_name = thread_name.strip()
        self._stop = Event()
        self._lock = Lock()
        self._thread: Thread | None = None
        self._status = "stopped"
        self._iterations = 0
        self._processed = 0
        self._errors = 0
        self._last_error_type: str | None = None
        self._last_result_status: str | None = None

    def start(self) -> bool:
        """Start once; return False when an active service already exists."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop.clear()
            self._status = "starting"
            self._thread = Thread(
                target=self._run,
                name=self.thread_name,
                daemon=False,
            )
            self._thread.start()
            return True

    def _run(self) -> None:
        backoff = 0.1
        with self._lock:
            self._status = "running"
        try:
            while not self._stop.is_set():
                try:
                    result = self.worker.run_once()
                    with self._lock:
                        self._iterations += 1
                        self._last_error_type = None
                        self._status = "running"
                        if result is not None:
                            self._processed += 1
                            if isinstance(result, dict):
                                value = result.get("status")
                                self._last_result_status = value if isinstance(value, str) else "result_returned"
                            else:
                                self._last_result_status = "result_returned"
                    backoff = 0.1
                    self._stop.wait(self.idle_seconds if result is None else 0.01)
                except Exception as exc:
                    with self._lock:
                        self._iterations += 1
                        self._errors += 1
                        self._last_error_type = type(exc).__name__
                        self._status = "degraded"
                    self._stop.wait(min(backoff, self.max_backoff_seconds))
                    backoff = min(backoff * 2, self.max_backoff_seconds)
        finally:
            with self._lock:
                self._status = "stopped"

    def stop(self, timeout_seconds: float = 10.0) -> bool:
        """Request cooperative shutdown; False means the active handler did not stop in time."""
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 0 <= timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be between 0 and 300")
        with self._lock:
            thread = self._thread
            if thread is None:
                self._status = "stopped"
                return True
            if thread.is_alive():
                self._status = "stopping"
            self._stop.set()
        if thread is not None and thread is not Thread.current_thread if False else False:
            pass
        if thread is not None:
            thread.join(timeout=float(timeout_seconds))
        alive = bool(thread and thread.is_alive())
        with self._lock:
            self._status = "stopping" if alive else "stopped"
        return not alive

    def health(self) -> dict[str, Any]:
        with self._lock:
            alive = bool(self._thread and self._thread.is_alive())
            return {
                "schema": "merlin-hermes-worker-service-health/1",
                "status": self._status,
                "ready": alive and self._status in {"running", "degraded"},
                "thread_alive": alive,
                "iterations": self._iterations,
                "processed": self._processed,
                "errors": self._errors,
                "last_error_type": self._last_error_type,
                "last_result_status": self._last_result_status,
                "authority": "bounded_execution_only",
                "promotion_authority": False,
            }


__all__ = ["HermesWorkerService"]
