"""Minimal read-only WSGI endpoint for the Merlin activity HUD.

Mount at /api/hud/activity behind the local Merlin runtime. Bind the runtime to
loopback by default; production deployments must add their normal authentication.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from merlin.hud_activity import HudActivityProjector, HudOutboxConsumer


class HudActivityWSGI:
    def __init__(self, projector: HudActivityProjector,
                 consumer: HudOutboxConsumer | None = None,
                 *, max_drain_per_request: int = 100):
        if not isinstance(projector, HudActivityProjector):
            raise ValueError("projector must be a HudActivityProjector")
        if isinstance(max_drain_per_request, bool) or not isinstance(max_drain_per_request, int) or not 1 <= max_drain_per_request <= 1000:
            raise ValueError("max_drain_per_request must be between 1 and 1000")
        self.projector = projector
        self.consumer = consumer
        self.max_drain_per_request = max_drain_per_request

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        if environ.get("PATH_INFO") != "/api/hud/activity":
            return self._respond(start_response, "404 Not Found",
                                 {"error": "not_found"})
        if environ.get("REQUEST_METHOD", "GET").upper() != "GET":
            return self._respond(start_response, "405 Method Not Allowed",
                                 {"error": "method_not_allowed"},
                                 extra=[("Allow", "GET")])
        try:
            if self.consumer is not None:
                for _ in range(self.max_drain_per_request):
                    result = self.consumer.drain_one()
                    if result is None:
                        break
            run_id = environ.get("QUERY_STRING", "")
            selected_run = None
            if run_id.startswith("run_id="):
                from urllib.parse import parse_qs
                values = parse_qs(run_id).get("run_id", [])
                selected_run = values[0] if values else None
            return self._respond(start_response, "200 OK",
                                 self.projector.snapshot(run_id=selected_run))
        except Exception as exc:
            return self._respond(start_response, "503 Service Unavailable",
                                 {"error": "hud_projection_unavailable",
                                  "error_type": type(exc).__name__})

    @staticmethod
    def _respond(start_response: Callable[..., Any], status: str,
                 payload: dict[str, Any], *, extra: list[tuple[str, str]] | None = None):
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ] + (extra or [])
        start_response(status, headers)
        return [body]


__all__ = ["HudActivityWSGI"]
