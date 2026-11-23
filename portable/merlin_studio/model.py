"""Bounded local model protocol. No account login, hosted API or proxy use."""
from __future__ import annotations

import http.client
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import socket
import subprocess
import threading
import time
import urllib.parse
from contextlib import suppress


class ModelError(RuntimeError):
    pass


def endpoint_parts(endpoint):
    if not isinstance(endpoint, str) or len(endpoint) > 2048:
        raise ValueError("Invalid model endpoint")
    if not endpoint:
        return None
    parsed = urllib.parse.urlsplit(endpoint)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1", "localhost")
            or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment):
        raise ValueError("Model endpoint must be loopback HTTP without credentials or query parameters")
    path = parsed.path.rstrip("/")
    if path in ("", "/v1"):
        path = "/v1/chat/completions"
    if path != "/v1/chat/completions":
        raise ValueError("Use the local server's /v1/chat/completions endpoint")
    port = 80 if parsed.port is None else parsed.port
    if not 1 <= port <= 65535:
        raise ValueError("Invalid model port")
    return ("127.0.0.1" if parsed.hostname == "localhost" else parsed.hostname, port, path)


_READ_ONLY_COMPAT_TOOLS = frozenset(("read_file", "list_files"))
_COMPAT_JSON_FENCE = re.compile(r"\A\x60{3}(?:json)?\r?\n([\s\S]*?)\r?\n\x60{3}\Z", re.IGNORECASE)
_COMPAT_PATH = re.compile(r"[A-Za-z0-9._/-]{1,256}\Z")


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _read_only_json_tool_call(content, declared_tools):
    """Opt-in bridge for local models emitting a textual JSON function call.

    Only an exact top-level read-only envelope may be adapted. Unrecognized,
    ambiguous, malformed, or potentially mutating content remains text, not
    a tool call. The existing ToolSet policy still validates and executes it.
    """
    if not isinstance(content, str) or not 1 <= len(content) <= 4096:
        return None
    body = content.strip()
    if body.startswith("```"):
        match = _COMPAT_JSON_FENCE.fullmatch(body)
        if match is None:
            return None
        body = match.group(1)
    try:
        obj = json.loads(body, object_pairs_hook=_reject_duplicate_json_keys)
    except (TypeError, ValueError):
        return None
    if not isinstance(obj, dict) or set(obj) != {"name", "arguments"}:
        return None
    name, args = obj["name"], obj["arguments"]
    if (not isinstance(name, str) or name not in _READ_ONLY_COMPAT_TOOLS
            or not isinstance(args, dict)
            or set(args) - {"path"}
            or (name == "read_file" and set(args) != {"path"})):
        return None
    if not any(isinstance(t, dict) and isinstance(t.get("function"), dict)
               and t["function"].get("name") == name for t in declared_tools):
        return None
    path = args.get("path", ".")
    if (not isinstance(path, str) or not _COMPAT_PATH.fullmatch(path)
            or (name == "read_file" and path == ".")
            or PurePosixPath(path).is_absolute()
            or PurePosixPath(path).as_posix() != path
            or ".." in PurePosixPath(path).parts):
        return None
    return {"id": "merlin-readonly-" + secrets.token_hex(16),
            "type": "function",
            "function": {"name": name,
                         "arguments": json.dumps(args, sort_keys=True, ensure_ascii=False)}}


class LocalModel:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    def _request(self, method, path, payload=None, timeout=45):
        parts = endpoint_parts(self.settings.get("model_url", ""))
        if parts is None:
            raise ModelError("No local model is configured")
        allowed_timeout = self.settings.get("model_timeout_seconds", 45)
        if type(allowed_timeout) is not int or not 10 <= allowed_timeout <= 120:
            raise ModelError("Configured model timeout must be an integer between 10 and 120 seconds")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= allowed_timeout:
            raise ModelError("Model request timeout exceeds its configured deadline")
        if self.transport is not None:
            return self.transport(method, path, payload, timeout)
        deadline = time.monotonic() + timeout
        connection = http.client.HTTPConnection(parts[0], parts[1], timeout=timeout)
        channel = None
        response = None
        timer = None
        expired = threading.Event()

        def remaining():
            value = deadline - time.monotonic()
            if value <= 0 or expired.is_set():
                raise ModelError("Local model exceeded the total response deadline")
            return value

        def interrupt():
            expired.set()
            # Retain the original socket even when HTTPConnection transfers it
            # to a Connection: close response and clears connection.sock.
            if channel is not None:
                with suppress(OSError):
                    channel.shutdown(socket.SHUT_RDWR)
                with suppress(OSError):
                    channel.close()
            with suppress(OSError):
                connection.close()

        try:
            body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
            connection.timeout = remaining()
            connection.connect()
            channel = connection.sock
            timer = threading.Timer(remaining(), interrupt)
            timer.daemon = True
            timer.start()
            connection.request(method, path, body=body, headers={"Content-Type": "application/json", "Connection": "close"})
            if channel is not None:
                channel.settimeout(remaining())
            response = connection.getresponse()
            if response.status != 200:
                raise ModelError("Local model returned HTTP " + str(response.status))
            pairs = response.getheaders()
            if sum(len(name) + len(value) for name, value in pairs) > 32768:
                raise ModelError("Local model response headers exceeded 32 KiB")
            lengths = [value.strip() for name, value in pairs if name.lower() == "content-length"]
            transfers = [value.strip().lower() for name, value in pairs if name.lower() == "transfer-encoding"]
            encodings = [value.strip().lower() for name, value in pairs if name.lower() == "content-encoding"]
            if (len(lengths) > 1 or len(transfers) > 1 or (lengths and transfers)
                    or (transfers and transfers != ["chunked"]) or (encodings and encodings != ["identity"])):
                raise ModelError("Local model returned ambiguous or unsupported response framing")
            declared_length = None
            if lengths:
                if not lengths[0].isascii() or not lengths[0].isdecimal() or len(lengths[0]) > 20:
                    raise ModelError("Local model returned an invalid response length")
                declared_length = int(lengths[0])
                if declared_length > 2 * 1024 * 1024:
                    raise ModelError("Model response exceeded 2 MiB")
            chunks = []
            received = 0
            while received <= 2 * 1024 * 1024:
                remaining()
                if response.isclosed():
                    break
                if channel is not None:
                    channel.settimeout(remaining())
                part = response.read1(min(65536, 2 * 1024 * 1024 + 1 - received))
                if not part:
                    break
                chunks.append(part)
                received += len(part)
            remaining()
            if received > 2 * 1024 * 1024:
                raise ModelError("Model response exceeded 2 MiB")
            if declared_length is not None and received != declared_length:
                raise ModelError("Local model response ended before its declared length")
            raw = b"".join(chunks)
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ModelError("Local model returned an invalid JSON object")
            remaining()
            return value
        except (OSError, http.client.HTTPException, ValueError) as exc:
            if expired.is_set() or time.monotonic() >= deadline:
                raise ModelError("Local model exceeded the total response deadline") from exc
            if isinstance(exc, ModelError):
                raise
            raise ModelError("Local model connection failed: " + str(exc)[:300]) from exc
        finally:
            if timer is not None:
                timer.cancel()
            if response is not None:
                response.close()
            connection.close()

    def probe(self):
        if not self.settings.get("model_url"):
            return {"reachable": False, "models": [], "error": "Choose a local model endpoint"}
        try:
            result = self._request("GET", "/v1/models", timeout=min(10, self.settings.get("model_timeout_seconds", 45)))
            values = result.get("data")
            if not isinstance(values, list):
                raise ModelError("Local server did not return a models list")
            models = [{"id": x["id"]} for x in values[:100] if isinstance(x, dict) and isinstance(x.get("id"), str)]
            return {"reachable": bool(models), "models": models,
                    **({} if models else {"error": "The local server has no loaded model"})}
        except (ModelError, ValueError) as exc:
            return {"reachable": False, "models": [], "error": str(exc)}

    def complete(self, messages, tools, *, timeout=45):
        max_tokens = self.settings.get("max_output_tokens", 2048)
        if type(max_tokens) is not int or not 16 <= max_tokens <= 2048:
            raise ModelError("Output token budget must be an integer between 16 and 2048")
        payload = {"model": self.settings.get("model_id") or "local", "messages": messages,
                   "stream": False, "max_tokens": max_tokens, "temperature": 0.3}
        if tools:
            payload.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
        result = self._request("POST", "/v1/chat/completions", payload, timeout=timeout)
        try:
            message = result["choices"][0]["message"]
            content = message.get("content")
            calls = message.get("tool_calls", [])
            if not isinstance(message, dict) or (content is not None and not isinstance(content, str)):
                raise ValueError("invalid assistant content")
            if not isinstance(calls, list) or len(calls) > 4:
                raise ValueError("invalid tool call count")
            if content is not None and len(content) > 65536:
                raise ValueError("assistant content too long")
            ids = set()
            normalized = []
            for call in calls:
                fn = call["function"]
                cid = call["id"]
                if (not isinstance(cid, str) or not 0 < len(cid) <= 200 or cid in ids
                        or not isinstance(fn["name"], str) or not isinstance(fn["arguments"], str)
                        or len(fn["arguments"]) > 65536):
                    raise ValueError("invalid tool call")
                arguments = json.loads(fn["arguments"])
                if not isinstance(arguments, dict):
                    raise ValueError("tool arguments must be an object")
                ids.add(cid)
                normalized.append({"id": cid, "type": "function", "function": {
                    "name": fn["name"], "arguments": fn["arguments"]}})
            if not normalized and self.settings.get("tool_compatibility", "native") == "read_only_json":
                adapted = _read_only_json_tool_call(content, tools)
                if adapted is not None:
                    normalized.append(adapted)
                    content = ""
                    return {"role": "assistant", "content": content,
                            "tool_calls": normalized,
                            "_compatibility_adapter": "read_only_json"}
            return {"role": "assistant", "content": content or "", **({"tool_calls": normalized} if normalized else {})}
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
            raise ModelError("Local model returned an invalid chat/tool response") from exc


class BundledModel:
    """Start only an explicitly supplied local llama-server and GGUF file."""
    def __init__(self, root, data_root):
        self.root, self.data_root = Path(root), Path(data_root)
        self.process = None
        self.log = None

    def available(self):
        executable = Path(os.environ.get("MERLIN_LLAMA_SERVER", str(self.root / "bin" / ("llama-server.exe" if os.name == "nt" else "llama-server"))))
        supplied = os.environ.get("MERLIN_MODEL_PATH")
        models = [Path(supplied)] if supplied else sorted((self.root / "models").glob("*.gguf"))
        return (executable.resolve(), models[0].resolve()) if executable.is_file() and len(models) == 1 and models[0].is_file() else None

    def start(self):
        available = self.available()
        if not available or self.process is not None:
            return False
        # A missing/incompatible optional local engine must not prevent the
        # offline Studio UI and workspace from starting. This is not an
        # inference-ready signal; /api/settings/probe verifies actual models.
        executable, model = available
        command = [str(executable), "--model", str(model), "--alias", "local",
                   "--host", "127.0.0.1", "--port", "8772",
                   "--ctx-size", "4096", "--jinja"]
        try:
            self.log = (self.data_root / "local-model.log").open("ab")
            self.process = subprocess.Popen(
                command, cwd=str(self.root), stdin=subprocess.DEVNULL,
                stdout=self.log, stderr=self.log)
        except OSError as exc:
            # A missing shared library, executable permission or read-only
            # log path must not prevent the offline UI from starting.
            if self.log is not None:
                try:
                    self.log.write(("Local bundled model launch failed: " +
                                    type(exc).__name__ + "\n").encode("ascii"))
                except OSError:
                    pass
                finally:
                    self.log.close()
            self.log = None
            self.process = None
            return False
        return True

    def close(self):
        try:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        finally:
            if self.log is not None:
                self.log.close()
            self.log = None
            self.process = None
