"""Opt-in, privacy-minimized PostHog export for Merlin operational events.

Merlin's local event ledger remains authoritative. This adapter exports only
allowlisted metadata and advances its cursor only after a successful batch
acknowledgement. Stable insert IDs make retries deduplicable.
"""
from __future__ import annotations

from hashlib import sha256
from math import isfinite
import json
import os
from threading import Event, Lock, Thread
from time import monotonic
from typing import Any, Callable, Mapping, Sequence
from urllib.request import Request, urlopen


_REGIONS = {
    "us": "https://us.i.posthog.com/batch/",
    "eu": "https://eu.i.posthog.com/batch/",
}
_SAFE_SUMMARY_KEYS = {
    "component", "stage", "status", "outcome", "provider", "provider_host",
    "model", "model_id", "streamed", "bytes", "response_bytes", "choices",
    "duration_ms", "latency_ms", "retry_count", "attempt", "error_class",
    "queue_depth", "queue_latency_ms", "execution_ms", "http_status",
}


class PostHogTelemetrySink:
    """Send only pseudonymous operational metadata to PostHog's public API."""

    def __init__(
        self,
        *,
        project_token: str,
        region: str = "us",
        instance_id: str = "default",
        opener: Callable[..., Any] = urlopen,
        timeout_seconds: float = 5.0,
        max_batch_size: int = 100,
    ):
        if not isinstance(project_token, str) or not project_token.strip():
            raise ValueError("PostHog project token is required")
        if region not in _REGIONS:
            raise ValueError("PostHog region must be us or eu")
        if not isinstance(instance_id, str) or not instance_id.strip():
            raise ValueError("Merlin instance ID is required")
        if not 0.1 <= timeout_seconds <= 30:
            raise ValueError("PostHog timeout must be between 0.1 and 30 seconds")
        if not 1 <= max_batch_size <= 500:
            raise ValueError("PostHog batch size must be between 1 and 500")
        self._token = project_token.strip()
        self.endpoint = _REGIONS[region]
        self.region = region
        self.distinct_id = "merlin:" + sha256(instance_id.encode("utf-8")).hexdigest()[:24]
        self._opener = opener
        self.timeout_seconds = timeout_seconds
        self.max_batch_size = max_batch_size

    @classmethod
    def from_environment(
        cls, *, opener: Callable[..., Any] = urlopen
    ) -> "PostHogTelemetrySink | None":
        token = os.environ.get("MERLIN_POSTHOG_PROJECT_TOKEN", "").strip()
        if not token:
            return None
        instance_id = os.environ.get("MERLIN_INSTANCE_ID", "").strip()
        if not instance_id:
            raise ValueError("MERLIN_INSTANCE_ID is required when PostHog export is enabled")
        return cls(
            project_token=token,
            region=os.environ.get("MERLIN_POSTHOG_REGION", "us").strip().lower(),
            instance_id=instance_id,
            timeout_seconds=float(os.environ.get("MERLIN_POSTHOG_TIMEOUT_SECONDS", "5")),
            max_batch_size=int(os.environ.get("MERLIN_POSTHOG_BATCH_SIZE", "100")),
            opener=opener,
        )

    @staticmethod
    def _safe_properties(row: Mapping[str, Any]) -> dict[str, Any]:
        summary = row.get("summary")
        if not isinstance(summary, Mapping):
            summary = {}
        safe = {}
        for key in _SAFE_SUMMARY_KEYS:
            value = summary.get(key)
            if isinstance(value, str) and len(value) <= 128:
                safe[key] = value
            elif isinstance(value, (int, bool)):
                safe[key] = value
            elif isinstance(value, float) and isfinite(value):
                safe[key] = value
        return safe

    def _event(self, row: Mapping[str, Any]) -> dict[str, Any]:
        row_id = row.get("id")
        kind = row.get("kind")
        request_digest = row.get("request_sha256")
        if not isinstance(row_id, int) or row_id < 1:
            raise ValueError("event row ID must be a positive integer")
        if not isinstance(kind, str) or not kind or len(kind) > 128:
            raise ValueError("event kind is invalid")
        if not isinstance(request_digest, str) or len(request_digest) != 64:
            raise ValueError("event request digest is invalid")
        insert_id = sha256(
            ("merlin-posthog-v1:" + str(row_id) + ":" + request_digest).encode("utf-8")
        ).hexdigest()
        properties = {
            "distinct_id": self.distinct_id,
            "$insert_id": insert_id,
            "$process_person_profile": False,
            "merlin_event_id": row_id,
            "merlin_event_kind": kind,
            **self._safe_properties(row),
        }
        event = {
            "event": "merlin_runtime_event",
            "properties": properties,
        }
        created_at = row.get("created_at")
        if isinstance(created_at, str) and len(created_at) <= 64:
            event["timestamp"] = created_at
        return event

    def capture_batch(self, rows: Sequence[Mapping[str, Any]]) -> int:
        if not rows:
            return 0
        if len(rows) > self.max_batch_size:
            raise ValueError("PostHog batch exceeds configured maximum")
        events = [self._event(row) for row in rows]
        body = json.dumps(
            {"api_key": self._token, "batch": events},
            separators=(",", ":"), ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with self._opener(request, timeout=self.timeout_seconds) as response:
            status = getattr(response, "status", 200)
            if not 200 <= status < 300:
                raise RuntimeError("PostHog rejected telemetry batch")
            response.read(1024)
        return len(events)


class PostHogExportService:
    """Poll a minimal EventStore export interface and safely advance its cursor."""

    def __init__(
        self,
        *,
        event_store: Any,
        sink: PostHogTelemetrySink,
        poll_seconds: float = 5.0,
        batch_size: int = 100,
    ):
        if not 0.1 <= poll_seconds <= 300:
            raise ValueError("PostHog poll interval is out of range")
        if not 1 <= batch_size <= sink.max_batch_size:
            raise ValueError("PostHog export batch size is out of range")
        self.event_store = event_store
        self.sink = sink
        self.poll_seconds = poll_seconds
        self.batch_size = batch_size
        self._stop = Event()
        self._thread: Thread | None = None
        self._lock = Lock()
        self._last_error: str | None = None
        self._last_exported = 0
        self._last_success_monotonic: float | None = None

    def run_once(self) -> int:
        cursor = self.event_store.get_posthog_export_cursor()
        rows = self.event_store.export_batch(cursor=cursor, limit=self.batch_size)
        if not rows:
            return 0
        exported = self.sink.capture_batch(rows)
        # Advance only after remote acceptance. A crash before this point causes
        # a replay with the same stable $insert_id rather than lost telemetry.
        self.event_store.advance_posthog_export_cursor(rows[-1]["id"])
        with self._lock:
            self._last_error = None
            self._last_exported += exported
            self._last_success_monotonic = monotonic()
        return exported

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:
                with self._lock:
                    self._last_error = type(exc).__name__
            self._stop.wait(self.poll_seconds)

    def start(self) -> bool:
        if self._thread is not None and self._thread.is_alive():
            return False
        self._stop.clear()
        self._thread = Thread(
            target=self._loop, name="merlin-posthog-export", daemon=True
        )
        self._thread.start()
        return True

    def stop(self, timeout_seconds: float = 5.0) -> bool:
        self._stop.set()
        if self._thread is None:
            return True
        self._thread.join(timeout=timeout_seconds)
        return not self._thread.is_alive()

    def health(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": "merlin-posthog-export-health/1",
                "status": (
                    "running" if self._thread is not None and self._thread.is_alive()
                    else "stopped"
                ),
                "region": self.sink.region,
                "exported_events": self._last_exported,
                "last_error_class": self._last_error,
                "promotion_authority": False,
                "raw_conversation_export": False,
                "last_success_age_seconds": (
                    None if self._last_success_monotonic is None
                    else max(0.0, monotonic() - self._last_success_monotonic)
                ),
            }


__all__ = ["PostHogTelemetrySink", "PostHogExportService"]
