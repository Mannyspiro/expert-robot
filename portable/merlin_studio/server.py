#!/usr/bin/env python3
"""Merlin Studio loopback server. Standard library; no remote account required."""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer
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
from second_brain import SecondBrainPanel

ROOT = Path(__file__).resolve().parent
MAX_BODY = 384 * 1024
STREAM_WINDOW_SECONDS = 30
STREAM_WINDOW_BYTES = 2 * 1024 * 1024
TERMINAL_STATUSES = frozenset(("completed", "failed", "cancelled", "interrupted"))


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        # HTTPServer.server_bind() calls socket.getfqdn() on the bound host.
        # On macOS this can block on reverse DNS despite numeric loopback.
        # We never expose the service beyond 127.0.0.1 and do not need FQDN.
        TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]

    def __init__(self, address, app, *, second_brain=None):
        self.app = app
        self.second_brain = second_brain
        self.session_token = secrets.token_urlsafe(32)
        self.stream_slots = threading.BoundedSemaphore(16)
        self.streams_closed = threading.Event()
        super().__init__(address, Handler)

    def server_close(self):
        self.streams_closed.set()
        if self.second_brain is not None:
            self.second_brain.close()
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
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def boundary(self, mutation=False):
        port = self.server.server_port
        hosts = {"127.0.0.1:" + str(port), "localhost:" + str(port)}
        if port == 80:
            hosts.update({"127.0.0.1", "localhost"})
        if self.headers.get("Host", "").lower() not in hosts:
            raise PermissionError("Unrecognized local Host header")
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {"http://" + host for host in hosts}:
            raise PermissionError("Cross-origin requests are not accepted")
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise PermissionError("Cross-site requests are not accepted")
        if mutation:
            self.require_token()
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise ValueError("Content-Type must be application/json")
            if self.headers.get("Transfer-Encoding") is not None:
                raise ValueError("Chunked request bodies are not accepted")

    def require_token(self):
        tokens = self.headers.get_all("X-Merlin-Token", [])
        if len(tokens) != 1 or not hmac.compare_digest(tokens[0], self.server.session_token):
            raise PermissionError("Reload Studio to obtain the current local session")

    def stream_events(self, run_id, query):
        """Bounded, authenticated replay of durable events, never a new run."""
        self.require_token()
        fields = urllib.parse.parse_qs(query, keep_blank_values=True, strict_parsing=True,
                                      max_num_fields=2)
        previous = self.headers.get_all("Last-Event-ID", [])
        if set(fields) - {"after"} or len(fields.get("after", [])) > 1 or len(previous) > 1:
            raise ValueError("Only one event cursor is accepted")
        after_text = fields.get("after", previous or ["0"])[0]
        if (not after_text.isascii() or not after_text.isdecimal() or len(after_text) > 19
                or int(after_text) > 9223372036854775807
                or (previous and previous[0] != after_text)):
            raise ValueError("Invalid or inconsistent event cursor")
        after = int(after_text)
        store = self.server.app.store
        store.run(run_id, include_events=False)  # Validate before sending HTTP headers.
        if not self.server.stream_slots.acquire(blocking=False):
            return self.send_data({"error": "Too many active event streams"}, 429)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            sent = 0
            def send_frame(frame):
                nonlocal sent
                if sent + len(frame) > STREAM_WINDOW_BYTES:
                    return False
                self.wfile.write(frame)
                self.wfile.flush()
                sent += len(frame)
                return True
            if not send_frame(b": connected\nretry: 1000\n\n"):
                return
            deadline = time.monotonic() + STREAM_WINDOW_SECONDS
            heartbeat = time.monotonic() + 5
            previous_status = None
            while time.monotonic() < deadline and not self.server.streams_closed.is_set():
                events = store.events_after(run_id, after)
                for event in events:
                    encoded = json.dumps(event, ensure_ascii=False, allow_nan=False).encode("utf-8")
                    frame = (b"event: merlin\nid: " + str(event["ordinal"]).encode("ascii")
                             + b"\ndata: " + encoded + b"\n\n")
                    if not send_frame(frame):
                        return
                    after = event["ordinal"]
                    if time.monotonic() >= deadline:
                        return
                if len(events) == 64:
                    continue  # Drain only bounded pages before considering terminal state.
                run = store.run(run_id, include_events=False)
                # A finish can race the first SELECT. Never close before its
                # durable terminal event is sent to this subscriber.
                if run["status"] in TERMINAL_STATUSES and store.events_after(run_id, after, limit=1):
                    continue
                if run["status"] != previous_status and run["status"] in TERMINAL_STATUSES | {"waiting_approval"}:
                    snapshot = json.dumps({"run": run, "refresh_required": True},
                                          ensure_ascii=False, allow_nan=False).encode("utf-8")
                    if not send_frame(b"event: snapshot\ndata: " + snapshot + b"\n\n"):
                        return
                previous_status = run["status"]
                if run["status"] in TERMINAL_STATUSES:
                    return
                if time.monotonic() >= heartbeat:
                    if not send_frame(b": keep-alive\n\n"):
                        return
                    heartbeat = time.monotonic() + 5
                self.server.streams_closed.wait(0.1)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            # A disappearing subscriber does not cancel or restart model work.
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
            if path in ("/", "/index.html", "/studio", "/studio/"):
                return self.send_data((ROOT / "web" / "index.html").read_bytes(), content_type="text/html; charset=utf-8")
            if path in ("/second-brain", "/second-brain/"):
                return self.send_data((ROOT / "web" / "second-brain.html").read_bytes(), content_type="text/html; charset=utf-8")
            if path == "/api/health":
                return self.send_data({"ready": True, "service": "merlin-studio", "version": "0.2.0"})
            if path == "/api/status":
                return self.send_data({**app.status(), "session_token": self.server.session_token})
            if path == "/api/resources":
                self.require_token()
                return self.send_data(app.resources())
            if path == "/api/settings":
                return self.send_data({"settings": app.current_settings(), "models": app.probe_result.get("models", [])})
            if path == "/api/conversations":
                return self.send_data({"conversations": app.store.conversations()})
            if path.startswith("/api/conversations/"):
                return self.send_data({"conversation": app.store.conversation(path.rsplit("/", 1)[1])})
            if path.startswith("/api/runs/") and path.count("/") == 4 and path.endswith("/events"):
                return self.stream_events(path.split("/")[3], url.query)
            if path.startswith("/api/runs/") and path.count("/") == 3:
                run = app.store.run(path.rsplit("/", 1)[1])
                return self.send_data({"run": run, "conversation": app.store.conversation(run["conversation_id"])})
            if path == "/api/workspace":
                folder = urllib.parse.parse_qs(url.query).get("path", ["."])[0]
                return self.send_data(app.tools().execute("list_files", {"path": folder}, "workspace-read"))
            return self.send_data({"error": "Not found"}, 404)
        except Exception as exc:
            self._error(exc)

    def do_POST(self):
        try:
            self.boundary(mutation=True)
            value = self.read_json()
            path = urllib.parse.urlsplit(self.path).path
            app = self.server.app
            if path.startswith("/api/second-brain/"):
                action = path.removeprefix("/api/second-brain/")
                panel = self.server.second_brain
                if panel is None:
                    if action == "status" and not value:
                        return self.send_data({"configured": False, "import_enabled": False, "read_only_default": True})
                    raise PermissionError("Second Brain is not enabled on this local server")
                actions = {
                    "status": lambda: panel.status() if not value else self._second_brain_invalid(),
                    "inventory": lambda: panel.inventory() if not value else self._second_brain_invalid(),
                    "search": lambda: panel.search(value),
                    "review": lambda: panel.review(value),
                    "discard": lambda: panel.discard(value),
                    "import": lambda: panel.import_reviewed(value),
                }
                if action not in actions:
                    return self.send_data({"error": "Not found"}, 404)
                return self.send_data(actions[action]())
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

    @staticmethod
    def _second_brain_invalid():
        raise ValueError("no request fields are accepted for this action")

    def do_OPTIONS(self):
        self.send_data({"error": "Cross-origin access is disabled"}, 403)

    def _error(self, exc):
        status = 403 if isinstance(exc, PermissionError) else 404 if isinstance(exc, (KeyError, FileNotFoundError)) else 400 if isinstance(exc, (ValueError, TypeError)) else 500
        self.send_data({"error": str(exc)[:1200], "error_type": type(exc).__name__}, status)


def create_server(host="127.0.0.1", port=0, data_dir=None, *, model_factory=None,
                  start_bundled=True, second_brain_vault=None, second_brain_import=False):
    if host != "127.0.0.1":
        raise ValueError("Studio binds only to 127.0.0.1")
    if type(second_brain_import) is not bool or (second_brain_import and second_brain_vault is None):
        raise ValueError("Second Brain import requires an explicit configured vault")
    app = Application(ROOT, data_dir or ROOT / "data", model_factory=model_factory, start_bundled=start_bundled)
    try:
        panel = (SecondBrainPanel(second_brain_vault, app.store, enable_import=second_brain_import)
                 if second_brain_vault is not None else None)
        return StudioServer((host, port), app, second_brain=panel)
    except BaseException:
        app.close()
        raise


def main():
    parser = argparse.ArgumentParser(description="Merlin Studio offline-first local agent workspace")
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("MERLIN_DATA_DIR", str(ROOT / "data"))))
    parser.add_argument("--open", action="store_true", help="Open Studio in the default web browser")
    parser.add_argument("--second-brain-vault", type=Path,
                        help="explicit local Obsidian Markdown folder (read-only by default)")
    parser.add_argument("--second-brain-import", action="store_true",
                        help="EXPERIMENTAL: permit review-confirmed plaintext imports into local registry")
    args = parser.parse_args()
    server = create_server(port=args.port, data_dir=args.data_dir,
                           second_brain_vault=args.second_brain_vault,
                           second_brain_import=args.second_brain_import)
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
