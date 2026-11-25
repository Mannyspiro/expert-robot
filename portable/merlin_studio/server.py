#!/usr/bin/env python3
"""Merlin Studio loopback server. Standard library; no remote account required."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import threading
import time
import urllib.parse
import webbrowser

from engine import Application
from storage import identity
from security_review import load_snapshot, render_snapshot
from gateway import load_gateway_contract, check_request_boundary
from research import ResearchIntegration, PATHS as RESEARCH_PATHS

ROOT = Path(__file__).resolve().parent
MAX_BODY = 384 * 1024


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, app, security_snapshot=None, *, research=None, gateway=None):
        self.app = app
        self.security_snapshot = security_snapshot
        self.research = research
        self.gateway = gateway
        self.session_token = secrets.token_urlsafe(32)
        self.stream_slots = threading.BoundedSemaphore(12)
        self.stream_stop = threading.Event()
        self.stream_seconds = 25.0
        super().__init__(address, Handler)
        if self.research is not None:
            self.research.start()

    def server_close(self):
        self.stream_stop.set()
        if self.research is not None:
            self.research.close()
        self.app.close()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_):
        pass

    def send_data(self, data, status=200, content_type="application/json; charset=utf-8"):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def boundary(self, mutation=False):
        if (not self.path.startswith("/") or self.path.startswith("//") or "\\" in self.path
                or "#" in self.path or len(self.path) > 4096
                or any(ord(char) < 32 for char in self.path)):
            raise ValueError("A bounded same-origin request path is required")
        check_request_boundary(self.headers, self.server.server_port, self.server.gateway,
                               self.server.session_token, mutation=mutation)

    def research_response(self, path, query):
        if self.server.research is None:
            return self.send_data({"error": "research_not_configured", "enabled": False}, 503)
        status, headers, body = self.server.research.response(path, query)
        self.send_response(status)
        for name, value in headers.items():
            if name.lower() in {"content-type", "content-length", "cache-control", "x-content-type-options",
                                "content-security-policy", "x-frame-options", "x-artifact-sha256"}:
                self.send_header(name, value)
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)

    def stream_run(self, run_id):
        """SSE for durable run/activity changes. Model text is a complete response."""
        cursors = self.headers.get_all("Last-Event-ID", [])
        if len(cursors) > 1 or (cursors and (not cursors[0].isdigit() or len(cursors[0]) > 18)):
            raise ValueError("Invalid event stream cursor")
        cursor = int(cursors[0]) if cursors else 0
        update = self.server.app.store.stream_update(run_id, cursor)
        if not self.server.stream_slots.acquire(blocking=False):
            return self.send_data({"error": "event_stream_capacity", "retry_after_seconds": 2}, 503)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            self.connection.settimeout(5)
            deadline = time.monotonic() + self.server.stream_seconds
            first, last_status, heartbeat = True, None, time.monotonic()
            while not self.server.stream_stop.is_set() and time.monotonic() < deadline:
                if first or update["events"] or update["status"] != last_status:
                    body = json.dumps(update, separators=(",", ":"), ensure_ascii=False).encode()
                    if len(body) > 65536:
                        raise ValueError("Event stream record exceeds limit")
                    self.wfile.write(b"id: " + str(update["cursor"]).encode() + b"\nevent: run\ndata: " + body + b"\n\n")
                    self.wfile.flush()
                    cursor, last_status, first = update["cursor"], update["status"], False
                    heartbeat = time.monotonic()
                elif time.monotonic() - heartbeat >= 5:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    heartbeat = time.monotonic()
                if update["terminal"] and not update["more"]:
                    break
                if not update["more"]:
                    self.server.stream_stop.wait(0.4)
                update = self.server.app.store.stream_update(run_id, cursor)
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass
        finally:
            self.server.stream_slots.release()

    def read_json(self):
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isdigit():
            raise ValueError("One valid Content-Length is required")
        size = int(lengths[0])
        if not 0 < size <= MAX_BODY:
            raise ValueError("Request size must be between 1 byte and 384 KiB")
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise ValueError("Incomplete request body")
        value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
        if not isinstance(value, dict):
            raise ValueError("Request must be a JSON object")
        return value

    def do_GET(self):
        try:
            self.boundary()
            url = urllib.parse.urlsplit(self.path)
            path = url.path
            app = self.server.app
            if path in RESEARCH_PATHS:
                return self.research_response(path, url.query)
            if path == "/api/research/status":
                return self.send_data(self.server.research.status() if self.server.research else {"enabled": False, "available": False})
            if path in ("/", "/index.html", "/studio", "/studio/"):
                return self.send_data((ROOT / "web" / "index.html").read_bytes(), content_type="text/html; charset=utf-8")
            if path == "/studio/security":
                return self.send_data(render_snapshot(self.server.security_snapshot).encode("utf-8"),
                                      content_type="text/html; charset=utf-8")
            if path == "/api/health":
                return self.send_data({"ready": True, "service": "merlin-studio", "version": "0.2.0"})
            if path == "/api/status":
                return self.send_data({**app.status(), "session_token": self.server.session_token,
                    "research": self.server.research.status() if self.server.research else {"enabled": False, "available": False},
                    "access": self.server.gateway.status() if self.server.gateway else {"mode": "loopback", "scope": "single_owner_shared_workspace"},
                    "updates": {"transport": "server_sent_events", "model_token_streaming": False, "stream_seconds": self.server.stream_seconds}})
            if path == "/api/settings":
                return self.send_data({"settings": app.current_settings(), "models": app.probe_result.get("models", [])})
            if path == "/api/conversations":
                return self.send_data({"conversations": app.store.conversations()})
            if path.startswith("/api/conversations/"):
                return self.send_data({"conversation": app.store.conversation(path.rsplit("/", 1)[1])})
            if path.startswith("/api/runs/") and path.count("/") == 3:
                run = app.store.run(path.rsplit("/", 1)[1])
                return self.send_data({"run": run, "conversation": app.store.conversation(run["conversation_id"])})
            if path.startswith("/api/runs/") and path.count("/") == 4 and path.endswith("/events"):
                if url.query:
                    raise ValueError("Event stream does not accept query parameters")
                return self.stream_run(path.split("/")[3])
            if path == "/api/workspace":
                folder = urllib.parse.parse_qs(url.query).get("path", ["."])[0]
                return self.send_data(app.tools().execute("list_files", {"path": folder}, "workspace-read"))
            return self.send_data({"error": "Not found"}, 404)
        except Exception as exc:
            self._error(exc)

    def do_POST(self):
        try:
            self.boundary(mutation=True)
            if urllib.parse.urlsplit(self.path).path in RESEARCH_PATHS:
                return self.send_data({"error": "research_http_is_read_only"}, 405)
            value = self.read_json()
            path = urllib.parse.urlsplit(self.path).path
            app = self.server.app
            if path == "/api/conversations":
                return self.send_data({"conversation": app.store.create_conversation(value.get("title", "New conversation"))}, 201)
            if path == "/api/chat":
                return self.send_data({"run_id": app.start_run(value["conversation_id"], value["message"])}, 202)
            if path == "/api/settings":
                return self.send_data({"settings": app.save_settings(value)})
            if path == "/api/model/probe":
                return self.send_data(app.model_probe())
            if path.startswith("/api/runs/") and path.count("/") == 4:
                run_id, action = path.split("/")[3:]
                if action == "approve":
                    app.store.approve(run_id, value["approval_id"], value["approved"])
                    return self.send_data({"accepted": True})
                if action == "cancel":
                    app.cancel(run_id)
                    return self.send_data({"accepted": True})
            if path == "/api/tool":
                # Manual editor endpoints are limited to workspace data operations.
                if value.get("tool") not in ("list_files", "read_file", "write_file"):
                    raise PermissionError("Use a chat request and action approval for this tool")
                result = app.tools().execute(value["tool"], value.get("args", {}), "manual-" + identity())
                return self.send_data({"result": result})
            return self.send_data({"error": "Not found"}, 404)
        except Exception as exc:
            self._error(exc)

    def do_OPTIONS(self):
        self.send_data({"error": "Cross-origin access is disabled"}, 403)

    def _error(self, exc):
        status = 403 if isinstance(exc, PermissionError) else 404 if isinstance(exc, (KeyError, FileNotFoundError)) else 400 if isinstance(exc, (ValueError, TypeError)) else 500
        self.send_data({"error": str(exc)[:1200], "error_type": type(exc).__name__}, status)


def create_server(host="127.0.0.1", port=0, data_dir=None, *, model_factory=None, start_bundled=True,
                  security_report=None, research_state_dir=None, gateway_config=None):
    if host != "127.0.0.1":
        raise ValueError("Studio binds only to 127.0.0.1")
    snapshot = load_snapshot(security_report) if security_report is not None else None
    gateway = load_gateway_contract(gateway_config)
    app = Application(ROOT, data_dir or ROOT / "data", model_factory=model_factory, start_bundled=start_bundled)
    research = None
    try:
        research = ResearchIntegration(app.store, research_state_dir) if research_state_dir is not None else None
        return StudioServer((host, port), app, snapshot, research=research, gateway=gateway)
    except BaseException:
        if research:
            research.close()
        app.close()
        raise


def main():
    parser = argparse.ArgumentParser(description="Merlin Studio offline-first local agent workspace")
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("MERLIN_DATA_DIR", str(ROOT / "data"))))
    parser.add_argument("--open", action="store_true", help="Open Studio in the default web browser")
    parser.add_argument("--security-report", type=Path, help="Optional trusted host synthetic security summary (read once at startup)")
    parser.add_argument("--research-state-dir", type=Path, help="Explicit canonical research registry, graph and outbox (writable by runtime; GET-only HTTP)")
    parser.add_argument("--gateway-config", type=Path, help="Explicit single-owner HTTPS origin contract; requires a verifying Cloudflare Access gateway")
    args = parser.parse_args()
    server = create_server(port=args.port, data_dir=args.data_dir, security_report=args.security_report,
                           research_state_dir=args.research_state_dir, gateway_config=args.gateway_config)
    url = "http://127.0.0.1:" + str(server.server_port) + "/studio/"
    print("Merlin Studio: " + url, flush=True)
    print("Workspace: " + str(server.app.workspace), flush=True)
    if args.open:
        webbrowser.open(url)
    def stop_server(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGINT, stop_server)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop_server)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
