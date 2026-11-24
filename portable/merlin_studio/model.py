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


MAX_MODEL_BYTES = 2 * 1024 * 1024
MAX_STREAM_FRAME_BYTES = 256 * 1024
MAX_STREAM_FRAMES = 8192


class _ChatStream:
    """Incremental SSE decoder; no tool is actionable before finish()."""
    def __init__(self, on_delta):
        self.on_delta = on_delta
        self.pending = bytearray()
        self.data = []
        self.frame_bytes = 0
        self.frames = 0
        self.delta_count = 0
        self.content = []
        self.content_length = 0
        self.calls = {}
        self.finish_reason = None
        self.done = False

    def feed(self, raw):
        self.pending.extend(raw)
        while True:
            end = self.pending.find(b"\n")
            if end < 0:
                if len(self.pending) + self.frame_bytes > MAX_STREAM_FRAME_BYTES:
                    raise ModelError("Local model stream frame exceeded 256 KiB")
                return
            line = bytes(self.pending[:end])
            del self.pending[:end + 1]
            self.frame_bytes += end + 1
            if self.frame_bytes > MAX_STREAM_FRAME_BYTES:
                raise ModelError("Local model stream frame exceeded 256 KiB")
            line = line.removesuffix(b"\r")
            if not line:
                if self.data:
                    self._frame(b"\n".join(self.data))
                self.data = []
                self.frame_bytes = 0
            elif line.startswith(b"data:"):
                self.data.append(line[5:].removeprefix(b" "))
            elif not line.startswith((b":", b"event:", b"id:", b"retry:")):
                raise ModelError("Local model returned an unsupported SSE field")

    def _frame(self, raw):
        self.frames += 1
        if self.frames > MAX_STREAM_FRAMES:
            raise ModelError("Local model stream exceeded its event budget")
        if self.done:
            raise ModelError("Local model sent data after stream completion")
        if raw == b"[DONE]":
            if self.finish_reason is None:
                raise ModelError("Local model stream omitted its finish reason")
            self.done = True
            return
        try:
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_json_keys,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
            if not isinstance(value, dict) or "error" in value:
                raise ValueError("invalid stream object")
            choices = value.get("choices")
            # OpenAI-compatible servers may send a trailing usage-only frame.
            if choices == [] and isinstance(value.get("usage"), dict):
                return
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("one streamed choice is required")
            choice = choices[0]
            if not isinstance(choice, dict) or type(choice.get("index", 0)) is not int or choice.get("index", 0) != 0:
                raise ValueError("invalid choice index")
            if self.finish_reason is not None:
                raise ValueError("choice received after finish reason")
            delta = choice.get("delta")
            if not isinstance(delta, dict) or delta.get("role", "assistant") != "assistant":
                raise ValueError("invalid assistant delta")
            if "function_call" in delta:
                raise ValueError("legacy function calls are unsupported")
            content = delta.get("content")
            if content is not None and not isinstance(content, str):
                raise ValueError("invalid text delta")
            if content:
                self.content_length += len(content)
                self.delta_count += 1
                if self.content_length > 65536 or self.delta_count > 4096:
                    raise ValueError("streamed assistant content exceeded its budget")
                self.content.append(content)
                self.on_delta(content)
            calls = delta.get("tool_calls", [])
            if not isinstance(calls, list) or len(calls) > 4:
                raise ValueError("invalid streamed tool call count")
            for fragment in calls:
                index = fragment.get("index")
                if type(index) is not int or not 0 <= index < 4:
                    raise ValueError("invalid tool call index")
                if fragment.get("type", "function") != "function":
                    raise ValueError("invalid tool call type")
                call = self.calls.setdefault(index, {"id": "", "type": "function",
                                                     "function": {"name": "", "arguments": ""}})
                fn = fragment.get("function", {})
                if not isinstance(fn, dict):
                    raise ValueError("invalid tool function delta")
                for target, key, addition, bound in (
                    (call, "id", fragment.get("id"), 200),
                    (call["function"], "name", fn.get("name"), 200),
                    (call["function"], "arguments", fn.get("arguments"), 65536),
                ):
                    if addition is not None:
                        if not isinstance(addition, str) or len(target[key]) + len(addition) > bound:
                            raise ValueError("streamed tool field exceeded its budget")
                        target[key] += addition
            finish = choice.get("finish_reason")
            if finish is not None:
                if finish not in ("stop", "length", "tool_calls"):
                    raise ValueError("unsupported stream finish reason")
                self.finish_reason = finish
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ModelError("Local model returned an invalid chat stream") from exc

    def finish(self):
        if self.pending or self.data or not self.done:
            raise ModelError("Local model stream ended before its completion marker")
        if set(self.calls) != set(range(len(self.calls))):
            raise ModelError("Local model stream has incomplete tool call indices")
        if self.calls and self.finish_reason != "tool_calls":
            raise ModelError("Local model did not finish its streamed tool calls")
        if self.finish_reason == "tool_calls" and not self.calls:
            raise ModelError("Local model omitted its streamed tool calls")
        return {"content": "".join(self.content), "tool_calls": [self.calls[i] for i in range(len(self.calls))]}


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

    def _request(self, method, path, payload=None, timeout=45, *, stream=None, cancelled=None):
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
        interrupted = threading.Event()
        finished = threading.Event()
        watcher = None

        def remaining():
            if interrupted.is_set() or (cancelled is not None and cancelled()):
                raise InterruptedError("Request cancelled")
            value = deadline - time.monotonic()
            if value <= 0 or expired.is_set():
                raise ModelError("Local model exceeded the total response deadline")
            return value

        def close_channel():
            # Retain the original socket even when HTTPConnection transfers it
            # to a Connection: close response and clears connection.sock.
            if channel is not None:
                with suppress(OSError):
                    channel.shutdown(socket.SHUT_RDWR)
                with suppress(OSError):
                    channel.close()
            with suppress(OSError):
                connection.close()

        def interrupt():
            expired.set()
            close_channel()

        def watch_cancel():
            while not finished.wait(0.05):
                if cancelled():
                    interrupted.set()
                    close_channel()
                    return

        try:
            body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
            connection.timeout = remaining()
            connection.connect()
            channel = connection.sock
            # Closing a cancelled channel must not make request() silently
            # open a replacement connection and submit the same prompt.
            connection.auto_open = 0
            timer = threading.Timer(remaining(), interrupt)
            timer.daemon = True
            timer.start()
            if cancelled is not None:
                watcher = threading.Thread(target=watch_cancel, daemon=True, name="merlin-model-cancel")
                watcher.start()
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
                if declared_length > MAX_MODEL_BYTES:
                    raise ModelError("Model response exceeded 2 MiB")
            content_types = [value.split(";", 1)[0].strip().lower()
                             for name, value in pairs if name.lower() == "content-type"]
            streaming = stream is not None and content_types == ["text/event-stream"]
            if stream is not None and content_types not in ([], ["application/json"], ["text/event-stream"]):
                raise ModelError("Local model returned an unsupported stream content type")
            chunks = []
            received = 0
            while received <= MAX_MODEL_BYTES:
                remaining()
                if response.isclosed():
                    break
                if channel is not None:
                    channel.settimeout(remaining())
                part = response.read1(min(65536, MAX_MODEL_BYTES + 1 - received))
                if not part:
                    break
                received += len(part)
                if received > MAX_MODEL_BYTES:
                    raise ModelError("Model response exceeded 2 MiB")
                if streaming:
                    stream.feed(part)
                    if stream.done and declared_length is None:
                        break  # [DONE] ends SSE even if the peer keeps TCP open.
                else:
                    chunks.append(part)
            remaining()
            if declared_length is not None and received != declared_length:
                raise ModelError("Local model response ended before its declared length")
            value = {"choices": [{"message": stream.finish()}]} if streaming else json.loads(b"".join(chunks))
            if not isinstance(value, dict):
                raise ModelError("Local model returned an invalid JSON object")
            remaining()
            return value
        except (OSError, http.client.HTTPException, ValueError) as exc:
            if interrupted.is_set() or (cancelled is not None and cancelled()):
                raise InterruptedError("Request cancelled") from exc
            if expired.is_set() or time.monotonic() >= deadline:
                raise ModelError("Local model exceeded the total response deadline") from exc
            if isinstance(exc, ModelError):
                raise
            raise ModelError("Local model connection failed: " + str(exc)[:300]) from exc
        finally:
            finished.set()
            if timer is not None:
                timer.cancel()
            if watcher is not None:
                watcher.join(timeout=0.2)
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

    def _payload(self, messages, tools, *, stream):
        max_tokens = self.settings.get("max_output_tokens", 2048)
        if type(max_tokens) is not int or not 16 <= max_tokens <= 2048:
            raise ModelError("Output token budget must be an integer between 16 and 2048")
        payload = {"model": self.settings.get("model_id") or "local", "messages": messages,
                   "stream": stream, "max_tokens": max_tokens, "temperature": 0.3}
        if tools:
            payload.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
        return payload

    def complete(self, messages, tools, *, timeout=45):
        payload = self._payload(messages, tools, stream=False)
        result = self._request("POST", "/v1/chat/completions", payload, timeout=timeout)
        return self._normalize(result, tools)

    def stream(self, messages, tools, *, on_delta, cancelled, timeout=45):
        """Emit genuine received text only; legacy JSON replies remain whole."""
        if not callable(on_delta) or not callable(cancelled):
            raise TypeError("Streaming requires text and cancellation callbacks")
        if cancelled():
            raise InterruptedError("Request cancelled")
        payload = self._payload(messages, tools, stream=True)
        result = self._request("POST", "/v1/chat/completions", payload, timeout=timeout,
                               stream=_ChatStream(on_delta), cancelled=cancelled)
        if cancelled():
            raise InterruptedError("Request cancelled")
        return self._normalize(result, tools)

    def _normalize(self, result, tools):
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


# A model subprocess must not inherit repository tokens, CI credentials,
# cloud keys, or arbitrary host environment variables.
_MODEL_PROCESS_ENV_ALLOWLIST = frozenset((
    "PATH", "SYSTEMROOT", "WINDIR",
    "LANG", "LC_ALL", "LC_CTYPE", "TZ",
))


def isolated_model_environment(source=None):
    """Return minimal launch environment without inherited credentials."""
    if source is None:
        source = os.environ
    return {key: value for key, value in source.items()
            if key in _MODEL_PROCESS_ENV_ALLOWLIST and isinstance(value, str)}


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
                   "--ctx-size", "4096", "--threads", "2", "--threads-batch", "2", "--jinja"]
        try:
            # Avoid directing model dependencies to the user's credential
            # stores under ~/.config, ~/.cache, or platform equivalents.
            model_home = self.data_root / "model-home"
            model_home.mkdir(mode=0o700, parents=True, exist_ok=True)
            model_home.chmod(0o700)
            child_env = isolated_model_environment()
            child_env["HOME"] = str(model_home)
            child_env["XDG_CONFIG_HOME"] = str(model_home / "config")
            child_env["XDG_CACHE_HOME"] = str(model_home / "cache")
            child_env["TMPDIR"] = str(model_home)
            child_env["TMP"] = str(model_home)
            child_env["TEMP"] = str(model_home)
            child_env["USERPROFILE"] = str(model_home)
            child_env["APPDATA"] = str(model_home / "config")
            child_env["LOCALAPPDATA"] = str(model_home / "cache")
            self.log = (self.data_root / "local-model.log").open("ab")
            self.process = subprocess.Popen(
                command, cwd=str(self.root), stdin=subprocess.DEVNULL,
                stdout=self.log, stderr=self.log,
                env=child_env)
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
