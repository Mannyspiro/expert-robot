"""Minimal read-only WSGI endpoint for the Merlin activity HUD.

Mount at /api/hud/activity behind the local Merlin runtime. Bind the runtime to
loopback by default; production deployments must add their normal authentication.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from merlin.hud_activity import HudActivityProjector, HudOutboxConsumer


from merlin.research_window_ui import DASHBOARD_HTML



class HudActivityWSGI:
    def __init__(self, projector: HudActivityProjector,
                 consumer: HudOutboxConsumer | None = None,
                 *, read_api: Any | None = None, max_drain_per_request: int = 100):
        if not isinstance(projector, HudActivityProjector):
            raise ValueError("projector must be a HudActivityProjector")
        if isinstance(max_drain_per_request, bool) or not isinstance(max_drain_per_request, int) or not 1 <= max_drain_per_request <= 1000:
            raise ValueError("max_drain_per_request must be between 1 and 1000")
        self.projector = projector
        self.consumer = consumer
        self.read_api = read_api
        self.max_drain_per_request = max_drain_per_request

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        path = environ.get("PATH_INFO")
        if path not in {"/dashboard", "/api/hud/activity", "/api/hud/graph", "/api/hud/node", "/api/hud/artifact"}:
            return self._respond(start_response, "404 Not Found",
                                 {"error": "not_found"})
        if environ.get("REQUEST_METHOD", "GET").upper() != "GET":
            return self._respond(start_response, "405 Method Not Allowed",
                                 {"error": "method_not_allowed"},
                                 extra=[("Allow", "GET")])
        if path == "/dashboard":
            return self._respond_html(start_response, DASHBOARD_HTML)
        try:
            if path == "/api/hud/artifact":
                return self._artifact(environ, start_response)
            if path in {"/api/hud/graph", "/api/hud/node"}:
                if self.read_api is None:
                    return self._respond(start_response, "503 Service Unavailable",
                                         {"error": "graph_query_not_configured"})
                if path == "/api/hud/graph":
                    return self._respond(start_response, "200 OK", self.read_api.graph())
                from urllib.parse import parse_qs
                from dataclasses import asdict
                params = parse_qs(environ.get("QUERY_STRING", ""))
                node_id = (params.get("node_id") or [""])[0]
                if not node_id or len(node_id) > 160:
                    return self._respond(start_response, "400 Bad Request",
                                         {"error": "node_id_required"})
                graph_store = getattr(self.read_api, "graph_store", None)
                if graph_store is None:
                    return self._respond(start_response, "503 Service Unavailable",
                                         {"error": "knowledge_graph_not_configured"})
                node = graph_store.get_node(node_id)
                if node is None:
                    return self._respond(start_response, "404 Not Found",
                                         {"error": "node_not_found"})
                neighbors = graph_store.neighbors(node_id)
                detail = {"schema": "merlin-hud-node/1",
                          "node": asdict(node), "neighbors": neighbors}
                linked_artifacts = []
                candidates = [(node.node_id, node)]
                for edge in neighbors:
                    other_id = (edge["target_id"] if edge["source_id"] == node_id
                                else edge["source_id"])
                    other = graph_store.get_node(other_id)
                    if other is not None:
                        candidates.append((other_id, other))
                detail["linked_artifacts_truncated"] = len(candidates) > 65
                for _candidate_id, candidate in candidates[:65]:
                    project_id = candidate.payload.get("project_id")
                    logical_path = candidate.payload.get("logical_path")
                    if (candidate.node_type == "artifact"
                            and isinstance(project_id, str)
                            and isinstance(logical_path, str)
                            and candidate.payload.get("display_kind") in {"graph", "source", "proof", "data"}):
                        reference = candidate.payload.get("artifact_ref")
                        if isinstance(reference, dict):
                            linked_artifacts.append(self.read_api.registry.read_artifact_ref(
                                reference, max_bytes=8 * 1024 * 1024)["resolution"])
                if linked_artifacts:
                    detail["linked_artifacts"] = linked_artifacts
                primary_artifact = linked_artifacts[0] if linked_artifacts else None
                from merlin.hud_objects import render_descriptor
                detail["workspace"] = render_descriptor(node, primary_artifact)
                detail["workspace"]["linked_artifacts"] = linked_artifacts
                return self._respond(start_response, "200 OK", detail)
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

    def _artifact(self, environ, start_response):
        """Serve only an explicitly registered graph node's exact artifact version."""
        from urllib.parse import parse_qs
        params = parse_qs(environ.get("QUERY_STRING", ""))
        node_id = (params.get("node_id") or [""])[0]
        if not node_id or len(node_id) > 160 or self.read_api is None:
            return self._respond(start_response, "400 Bad Request", {"error": "node_id_required"})
        graph = getattr(self.read_api, "graph_store", None)
        node = graph.get_node(node_id) if graph else None
        if (node is None or node.node_type != "artifact"
                or node.payload.get("display_kind") not in {"graph", "source", "proof", "data"}):
            return self._respond(start_response, "404 Not Found", {"error": "display_artifact_not_found"})
        reference = node.payload.get("artifact_ref")
        if not isinstance(reference, dict):
            return self._respond(start_response, "404 Not Found", {"error": "pinned_artifact_required"})
        result = self.read_api.registry.read_artifact_ref(reference, max_bytes=8 * 1024 * 1024)
        media = result["resolution"]["media_type"]
        allowed = {"image/png", "image/svg+xml", "image/jpeg", "image/webp",
                   "text/plain", "application/json", "text/x-lean"}
        if media not in allowed:
            return self._respond(start_response, "415 Unsupported Media Type", {"error": "display_media_type_not_allowed"})
        if media in {"text/x-lean", "application/json"}:
            media = "text/plain"
        content = result["content"]
        headers = [("Content-Type", media + ("; charset=utf-8" if media.startswith("text/") else "")),
                   ("Content-Length", str(len(content))), ("Cache-Control", "no-store"),
                   ("X-Content-Type-Options", "nosniff"),
                   ("Content-Security-Policy", "sandbox; default-src 'none'; style-src 'unsafe-inline'"),
                   ("X-Artifact-SHA256", reference["sha256"])]
        start_response("200 OK", headers)
        return [content]

    @staticmethod
    def _respond_html(start_response: Callable[..., Any], body_text: str):
        body = body_text.encode("utf-8")
        headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'"),
        ]
        start_response("200 OK", headers)
        return [body]

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
