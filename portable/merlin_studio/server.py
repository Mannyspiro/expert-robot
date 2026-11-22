#!/usr/bin/env python3
"""Merlin Studio loopback server. Standard library; no remote account required."""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import threading
import urllib.parse
import webbrowser

from engine import Application
from storage import identity

ROOT = Path(__file__).resolve().parent
MAX_BODY = 384 * 1024


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, app):
        self.app = app
        self.session_token = secrets.token_urlsafe(32)
        super().__init__(address, Handler)

    def server_close(self):
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
            token = self.headers.get("X-Merlin-Token", "")
            if not hmac.compare_digest(token, self.server.session_token):
                raise PermissionError("Reload Studio to obtain the current local session")
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise ValueError("Content-Type must be application/json")
            if self.headers.get("Transfer-Encoding") is not None:
                raise ValueError("Chunked request bodies are not accepted")

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
            if path == "/api/health":
                return self.send_data({"ready": True, "service": "merlin-studio", "version": "0.2.0"})
            if path == "/api/status":
                return self.send_data({**app.status(), "session_token": self.server.session_token})
            if path == "/api/settings":
                return self.send_data({"settings": app.current_settings(), "models": app.probe_result.get("models", [])})
            if path == "/api/conversations":
                return self.send_data({"conversations": app.store.conversations()})
            if path.startswith("/api/conversations/"):
                return self.send_data({"conversation": app.store.conversation(path.rsplit("/", 1)[1])})
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


def create_server(host="127.0.0.1", port=0, data_dir=None, *, model_factory=None, start_bundled=True):
    if host != "127.0.0.1":
        raise ValueError("Studio binds only to 127.0.0.1")
    app = Application(ROOT, data_dir or ROOT / "data", model_factory=model_factory, start_bundled=start_bundled)
    try:
        return StudioServer((host, port), app)
    except BaseException:
        app.close()
        raise


def main():
    parser = argparse.ArgumentParser(description="Merlin Studio offline-first local agent workspace")
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("MERLIN_DATA_DIR", str(ROOT / "data"))))
    parser.add_argument("--open", action="store_true", help="Open Studio in the default web browser")
    args = parser.parse_args()
    server = create_server(port=args.port, data_dir=args.data_dir)
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
