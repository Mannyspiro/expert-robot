"""Compose Studio with canonical research stores; publish actual metadata only.

Studio's durable events are the producer record. A stable event identity makes
replay into the canonical telemetry outbox idempotent across process restarts.
No conversation text, tool arguments/results, or workspace artifacts are copied
into the research display automatically. Scientific proof claims are never
inferred from chat or task completion.
"""
from __future__ import annotations

import json
from pathlib import Path
import threading
from urllib.parse import parse_qs


PATHS = frozenset({"/research/dashboard", "/api/hud/activity", "/api/hud/graph", "/api/hud/node", "/api/hud/artifact"})
MAX_RESPONSE = 8 * 1024 * 1024


class ResearchIntegration:
    def __init__(self, store, state_dir):
        from merlin.research_window import ResearchWindow
        state = Path(state_dir).resolve()
        workspace = (store.root / "workspace").resolve()
        if state == store.root or state.is_relative_to(workspace):
            raise ValueError("Canonical research state must be separate from the model workspace and Studio state root")
        self.store = store
        self.window = ResearchWindow(state, project_id="merlin-studio-live", project_title="Merlin Studio activity")
        self.cursor = 0
        self.last_error = None
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._run, name="merlin-studio-research", daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=2)

    @staticmethod
    def event(row):
        event = row["event"]
        kind = event["type"]
        tool = str(event.get("tool", ""))[:80]
        payload = {"component": "merlin_studio", "studio_event_id": event["id"],
                   "studio_run_id": row["run_id"], "event_type": kind}
        source = "runtime"
        if kind == "started":
            target = "task.started"
            payload.update(question="Studio request " + row["run_id"][:8],
                           summary="Studio request started; observable runtime activity.",
                           proof_status="This Studio run makes no scientific proof or verification claim.")
        elif kind == "completed":
            target = "task.completed"
            payload["summary"] = "Studio request completed. Task completion is not scientific verification."
        elif kind == "failed":
            target = "system.error"
            payload["summary"] = "Studio request failed; inspect its retained Activity for details."
        elif kind in {"cancelled", "interrupted", "approval_required"}:
            target = "task.progress"
            payload.update(status="waiting" if kind == "approval_required" else kind, summary={
                "cancelled": "Studio request cancelled.",
                "interrupted": "Studio restart interrupted the request; no action was replayed.",
                "approval_required": "Studio is waiting for an explicit action approval.",
            }[kind])
        elif kind == "approval_decided":
            target, source = "task.progress", "operator"
            payload.update(status="active", approved=event.get("approved") is True,
                           summary="Studio action approval recorded." if event.get("approved") is True else "Studio action declined.")
        elif kind in {"tool_started", "tool_result", "tool_error", "tool_denied"}:
            target = "agent.tool.started" if kind == "tool_started" else "agent.tool.completed"
            payload.update(tool=tool, outcome=kind, summary=tool + ": " + {
                "tool_started": "execution started", "tool_result": "result recorded",
                "tool_error": "error recorded", "tool_denied": "execution denied",
            }[kind])
        else:
            target = "task.progress"
            payload["summary"] = {"model_request": "Local model request started.",
                                  "assistant_note": "Model response recorded; content remains in the conversation.",
                                  "model_tool_adapter": "Explicit model tool compatibility adapter used."}.get(kind, "Studio activity recorded.")
        return {"event_id": "studio:" + event["id"], "source": source,
                "kind": target, "timestamp": event["created_at"],
                "run_id": "studio:" + row["run_id"], "payload": payload,
                "evidence_refs": ["studio-event:" + event["id"]]}

    def sync(self):
        with self.lock:
            rows = self.store.research_events_after(self.cursor, limit=128)
            for row in rows:
                self.window.emit(self.event(row))
                self.cursor = row["ordinal"]
            self.last_error = None
            return len(rows)

    def _run(self):
        while not self.stop.is_set():
            try:
                count = self.sync()
            except Exception as exc:
                self.last_error = type(exc).__name__
                count = 0
            if count < 128:
                self.stop.wait(0.5)

    def status(self):
        return {"enabled": True, "available": self.last_error is None,
                "event_cursor": self.cursor, "error_type": self.last_error,
                "publication": "actual_studio_metadata_to_canonical_outbox",
                "scientific_verification_inferred": False,
                "dashboard": "/research/dashboard"}

    def response(self, path, query):
        if path not in PATHS:
            raise ValueError("Research route is not allowlisted")
        if len(query) > 1024:
            raise ValueError("Research query is too large")
        params = parse_qs(query, keep_blank_values=True, strict_parsing=True, max_num_fields=2)
        allowed = {"run_id"} if path in {"/api/hud/activity", "/research/dashboard"} else {"node_id"} if path in {"/api/hud/node", "/api/hud/artifact"} else set()
        if set(params) - allowed or any(len(values) != 1 or not values[0] or len(values[0]) > 160 for values in params.values()):
            raise ValueError("Unsupported or ambiguous research query")
        with self.lock:
            metadata = {}
            def start(status, headers):
                metadata.update(status=int(status.split(" ", 1)[0]), headers=headers)
            iterable = self.window.application({"PATH_INFO": "/dashboard" if path == "/research/dashboard" else path,
                                                "QUERY_STRING": query, "REQUEST_METHOD": "GET"}, start)
            parts, size = [], 0
            try:
                for part in iterable:
                    size += len(part)
                    if size > MAX_RESPONSE:
                        raise ValueError("Research response exceeds the display byte limit")
                    parts.append(part)
            finally:
                if hasattr(iterable, "close"):
                    iterable.close()
            headers = dict(metadata["headers"])
            if path == "/research/dashboard":
                # The dashboard is embedded only by this same-origin Studio.
                # Registered image/source artifact sandbox headers are untouched.
                headers["X-Frame-Options"] = "SAMEORIGIN"
                headers["Content-Security-Policy"] = headers.get("Content-Security-Policy", "").replace("frame-ancestors 'none'", "frame-ancestors 'self'")
            return metadata["status"], headers, b"".join(parts)
