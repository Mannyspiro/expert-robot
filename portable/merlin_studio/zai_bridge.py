#!/usr/bin/env python3
"""Explicit opt-in Z.ai general API proxy for Merlin Studio.

No proxy runs by default. It requires --enable-cloud and a ZAI_API_KEY.
It only supports non-streaming text chat; model tool declarations and
tool execution are never forwarded. This is NOT an offline model.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import os
import re
import ssl
import threading

LOCAL_MODEL_ID = "merlin-zai"
ZAI_HOST = "api.z.ai"
ZAI_PATH = "/api/paas/v4/chat/completions"
MAX_REQUEST = 128 * 1024
MAX_RESPONSE = 2 * 1024 * 1024


class ZAIContractError(ValueError):
    pass


def upstream_request(request, model):
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", model):
        raise ZAIContractError("explicit upstream model ID is required")
    if not isinstance(request, dict) or request.get("model") != LOCAL_MODEL_ID or request.get("stream", False) is not False:
        raise ZAIContractError("requires non-streaming Merlin Z.ai model")
    messages = request.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 40:
        raise ZAIContractError("messages must be a bounded nonempty list")
    clean = []
    size = 0
    for m in messages:
        if not isinstance(m, dict) or m.get("role") not in ("system", "user", "assistant"):
            raise ZAIContractError("unsupported upstream role")
        if not isinstance(m.get("content"), str):
            raise ZAIContractError("Z.ai opt-in bridge accepts text messages only")
        size += len(m["content"])
        if size > 24000:
            raise ZAIContractError("cloud prompt exceeds 24000 characters")
        clean.append({"role": m["role"], "content": m["content"]})
    max_tokens = request.get("max_tokens", 128)
    if type(max_tokens) is not int or not 16 <= max_tokens <= 1024:
        raise ZAIContractError("cloud output budget must be between 16 and 1024")
    # Tool schemas and tool_choice from Studio are deliberately NOT sent to Z.ai.
    return {"model": model, "messages": clean, "stream": False,
            "max_tokens": max_tokens, "temperature": 0.3}


def call_zai(path, body, api_key, timeout=30):
    if path != ZAI_PATH:
        raise ZAIContractError("unapproved upstream path")
    context = ssl.create_default_context()
    connection = http.client.HTTPSConnection(ZAI_HOST, 443, timeout=timeout, context=context)
    try:
        connection.request("POST", path, body=json.dumps(body, allow_nan=False).encode(),
                           headers={"Authorization": "Bearer " + api_key,
                                    "Content-Type": "application/json", "Accept": "application/json",
                                    "Connection": "close"})
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ZAIContractError("upstream response too large")
        if response.status != 200:
            raise ZAIContractError("Z.ai HTTP " + str(response.status))
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ZAIContractError("invalid upstream object")
        return parsed
    finally:
        connection.close()


def validate_reply(reply):
    try:
        first = reply["choices"][0]
        message = first["message"]
        content = message["content"]
        if not isinstance(content, str) or len(content) > 65536:
            raise ValueError("invalid content")
        return {"id": "merlin-zai-proxy", "object": "chat.completion", "model": LOCAL_MODEL_ID,
                "choices": [{"index": 0, "finish_reason": first.get("finish_reason", "stop"),
                             "message": {"role": "assistant", "content": content}}]}
    except (IndexError, TypeError, KeyError, ValueError):
        raise ZAIContractError("Z.ai returned an invalid text completion") from None


class Session:
    def __init__(self, model, key, *, max_calls=4, sender=None):
        self.model = model
        self.key = key
        self.max_calls = max_calls
        self.sender = sender or call_zai
        self.lock = threading.Lock()
        self.calls = 0

    def complete(self, request):
        data = upstream_request(request, self.model)
        if not self.lock.acquire(blocking=False):
            raise ZAIContractError("one cloud request already active")
        try:
            if self.calls >= self.max_calls:
                raise ZAIContractError("session cloud call budget exhausted")
            self.calls += 1  # charge attempts, including failed upstream calls
            result = self.sender(ZAI_PATH, data, self.key)
            return validate_reply(result)
        finally:
            self.lock.release()


def make_handler(session):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *_):
            pass

        def reply(self, status, value):
            payload = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            self.wfile.write(payload)

        def allowed(self):
            port = self.server.server_port
            # The proxy is for a local Python model client, not browser origins.
            # Reject browser cross-origin requests before they can spend the
            # bounded paid-session allowance.
            if self.headers.get("Origin") is not None or self.headers.get("Sec-Fetch-Site") == "cross-site":
                return False
            return self.client_address[0] in ("127.0.0.1", "::1") and self.headers.get("Host", "").lower() in {
                "127.0.0.1:" + str(port), "localhost:" + str(port)}

        def do_GET(self):
            if not self.allowed():
                return self.reply(403, {"error": "local host required"})
            if self.path != "/v1/models":
                return self.reply(404, {"error": "not found"})
            return self.reply(200, {"object": "list", "data": [{"id": LOCAL_MODEL_ID, "object": "model"}]})

        def do_POST(self):
            if not self.allowed():
                return self.reply(403, {"error": "local host required"})
            if self.path != "/v1/chat/completions":
                return self.reply(404, {"error": "not found"})
            if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                return self.reply(400, {"error": "invalid request framing"})
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal() or len(lengths[0]) > 20:
                return self.reply(400, {"error": "invalid content length"})
            length = int(lengths[0])
            if not 0 < length <= MAX_REQUEST:
                return self.reply(413, {"error": "request too large"})
            try:
                request = json.loads(self.rfile.read(length))
                response = session.complete(request)
                return self.reply(200, response)
            except (ValueError, UnicodeError):
                return self.reply(400, {"error": "invalid or rejected cloud request"})
            except Exception:
                # Never reveal keys, upstream errors or raw user content via HTTP errors.
                return self.reply(502, {"error": "upstream cloud model request failed"})

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explicit cloud-only Z.ai general API bridge")
    parser.add_argument("--enable-cloud", action="store_true", help="I consent to sending chat text to Z.ai and possible billing")
    parser.add_argument("--model", required=True, help="Model ID supplied by the account's general API")
    parser.add_argument("--port", type=int, default=8774)
    parser.add_argument("--max-calls", type=int, default=4)
    args = parser.parse_args(argv)
    if not args.enable_cloud:
        parser.error("cloud access is disabled; --enable-cloud is required")
    key = os.environ.get("ZAI_API_KEY")
    if not key or len(key) > 4096 or any(ord(x) < 33 or ord(x) > 126 for x in key):
        parser.error("set a valid ZAI_API_KEY outside the repo")
    if not 1024 <= args.port <= 65535 or not 1 <= args.max_calls <= 20:
        parser.error("invalid local port or maximum call budget")
    session = Session(args.model, key, max_calls=args.max_calls)
    upstream_request({"model": LOCAL_MODEL_ID, "messages": [{"role": "user", "content": "preflight"}]}, args.model)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(session))
    print("Z.ai cloud proxy on http://127.0.0.1:%d/v1 (remote calls require chat requests)" % args.port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
