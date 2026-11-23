#!/usr/bin/env python3
"""Optional AirLLM -> loopback chat-completions bridge for Merlin Studio.

No dependency is imported, model downloaded, or process started until run.
This adapter is original Merlin code; AirLLM remains an external Apache-2.0
submodule. It does not implement native function calling or cancellation.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time

MODEL_ID = "merlin-airllm"
MAX_BODY = 128 * 1024
MAX_PROMPT_CHARS = 32768
MAX_MESSAGES = 64
MAX_NEW_TOKENS = 2048


class BridgeError(ValueError):
    pass


def validate_messages(messages):
    if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_MESSAGES:
        raise BridgeError("messages must be a nonempty bounded list")
    normalized = []
    total = 0
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in ("system", "user", "assistant", "tool"):
            raise BridgeError("unsupported chat role")
        content = message.get("content")
        if not isinstance(content, str):
            raise BridgeError("only text content is supported")
        total += len(content)
        if total > MAX_PROMPT_CHARS:
            raise BridgeError("prompt exceeds the text budget")
        normalized.append({"role": message["role"], "content": content})
    return normalized


def prepare_request(request):
    if not isinstance(request, dict) or request.get("stream", False) is not False:
        raise BridgeError("only non-streaming JSON chat requests are supported")
    if request.get("model", MODEL_ID) != MODEL_ID:
        raise BridgeError("unknown model id")
    count = request.get("max_tokens", request.get("max_completion_tokens", 128))
    if type(count) is not int or not 1 <= count <= MAX_NEW_TOKENS:
        raise BridgeError("max_tokens must be an integer in 1..2048")
    messages = validate_messages(request.get("messages"))
    tools = request.get("tools", [])
    if not isinstance(tools, list) or len(tools) > 16:
        raise BridgeError("tool declarations must be a bounded list")
    # In Merlin Studio a model text envelope is interpreted as read-only
    # only when the operator selected that compatibility mode. Never produce
    # native tool calls or execute a tool in this service.
    if tools:
        names = []
        for tool in tools:
            if not isinstance(tool, dict) or not isinstance(tool.get("function"), dict):
                raise BridgeError("invalid tool declaration")
            name = tool["function"].get("name")
            if not isinstance(name, str) or len(name) > 64:
                raise BridgeError("invalid tool name")
            names.append(name)
        hint = ("Available declared tool names: " + ", ".join(names) + ". "
                "The host enforces its own approvals and tool policy. "
                "If requesting a tool, respond with exactly one JSON object "
                '{"name":"read_file","arguments":{"path":"notes.txt"}} '
                "or answer normally. Do not claim a tool ran until the host confirms it.")
        messages = [{"role": "system", "content": hint}] + messages
    response_format = request.get("response_format")
    if response_format is not None:
        if response_format != {"type": "json_object"}:
            raise BridgeError("unsupported response format")
        messages = [{"role": "system", "content": "Respond with one valid JSON object only."}] + messages
    return messages, count


class AirLLMBackend:
    def __init__(self, local_model_path, loader=None):
        self.path = Path(local_model_path).expanduser().resolve(strict=True)
        if not self.path.is_dir() or not (self.path / "config.json").is_file():
            raise BridgeError("model path must be a local model directory with config.json")
        # Load only locally provided model material. Remote model IDs are not accepted.
        if loader is None:
            from airllm import AutoModel  # optional package; never imported by Studio
            loader = AutoModel.from_pretrained
        self.model = loader(str(self.path))
        self.tokenizer = self.model.tokenizer
        self.lock = threading.Lock()

    def generate(self, messages, max_new_tokens):
        if not hasattr(self.tokenizer, "apply_chat_template"):
            raise BridgeError("model tokenizer needs a supported chat template")
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        if not isinstance(prompt, str) or len(prompt) > 131072:
            raise BridgeError("invalid or oversized tokenizer prompt")
        tokens = self.tokenizer(prompt, return_tensors="pt", return_attention_mask=False,
                                truncation=True, max_length=4096, padding=False)["input_ids"]
        output = self.model.generate(tokens.to(self.model.device), max_new_tokens=max_new_tokens,
                                     use_cache=True, return_dict_in_generate=True)
        text = self.tokenizer.decode(output.sequences[0][tokens.shape[-1]:], skip_special_tokens=True)
        if not isinstance(text, str) or len(text) > 65536:
            raise BridgeError("invalid or oversized model text")
        return text


def make_handler(backend):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *_):
            pass

        def response(self, status, payload):
            body = json.dumps(payload, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            self.wfile.write(body)

        def allowed(self):
            port = self.server.server_port
            return self.headers.get("Host", "").lower() in {
                "localhost:" + str(port), "127.0.0.1:" + str(port)
            } and self.client_address[0] in ("127.0.0.1", "::1")

        def do_GET(self):
            if not self.allowed():
                return self.response(403, {"error": "loopback Host required"})
            if self.path != "/v1/models":
                return self.response(404, {"error": "not found"})
            return self.response(200, {"object": "list", "data": [{"id": MODEL_ID, "object": "model"}]})

        def do_POST(self):
            if not self.allowed():
                return self.response(403, {"error": "loopback Host required"})
            if self.path != "/v1/chat/completions":
                return self.response(404, {"error": "not found"})
            if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Type", "").split(";", 1)[0].lower() != "application/json":
                return self.response(400, {"error": "invalid request framing"})
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or len(lengths[0]) > 20 or not lengths[0].isascii() or not lengths[0].isdecimal():
                return self.response(400, {"error": "invalid content length"})
            length = int(lengths[0])
            if not 1 <= length <= MAX_BODY:
                return self.response(413, {"error": "request too large"})
            try:
                request = json.loads(self.rfile.read(length))
                messages, count = prepare_request(request)
            except (ValueError, UnicodeError, TypeError):
                return self.response(400, {"error": "invalid chat request"})
            if not backend.lock.acquire(blocking=False):
                return self.response(503, {"error": "model busy"})
            try:
                reply = backend.generate(messages, count)
            except Exception:
                # Never leak model internals, local paths, or tokens via HTTP.
                return self.response(502, {"error": "local model generation failed"})
            finally:
                backend.lock.release()
            return self.response(200, {"id": "merlin-airllm-local", "object": "chat.completion",
                                       "created": int(time.time()), "model": MODEL_ID,
                                       "choices": [{"index": 0, "finish_reason": "stop",
                                                    "message": {"role": "assistant", "content": reply}}]})

    return Handler


class LocalBridgeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local optional AirLLM inference bridge")
    parser.add_argument("--model-path", required=True, help="Trusted model directory already downloaded locally")
    parser.add_argument("--port", type=int, default=8772)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("port must be in 1024..65535")
    backend = AirLLMBackend(args.model_path)
    server = LocalBridgeHTTPServer(("127.0.0.1", args.port), make_handler(backend))
    print("Merlin AirLLM model endpoint: http://127.0.0.1:%d/v1" % args.port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
