"""Workspace, evidence, explicitly approved scripts, and optional desktop tools."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time

from public_web import fetch_public
from senses import sensory_fusion

MAX_FILE = 256 * 1024


def read_regular(path, limit=MAX_FILE):
    """Reject pipes/devices and leaf symlinks without blocking on open."""
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Workspace tools accept regular files only")
        if info.st_size > limit:
            raise ValueError("File exceeds 256 KiB limit")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            value = stream.read(limit + 1)
        if len(value) > limit:
            raise ValueError("File exceeds 256 KiB limit")
        return value
    finally:
        os.close(descriptor)


def schema(name, description, properties, required=()):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}}}


STRING = {"type": "string"}


class ToolSet:
    APPROVAL = frozenset({"run_python", "analyze_sensory_file", "desktop_screenshot", "desktop_click", "desktop_type", "desktop_key"})

    def __init__(self, workspace, store, settings):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = store
        self.settings = settings

    def path(self, value):
        if not isinstance(value, str) or len(value) > 1024 or "\x00" in value:
            raise ValueError("Invalid workspace path")
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Path must remain inside the workspace")
        target = self.workspace
        for part in relative.parts:
            target = target / part
            if target.is_symlink():
                raise ValueError("Workspace symlinks are not followed")
        resolved = target.resolve()
        if resolved != self.workspace and self.workspace not in resolved.parents:
            raise ValueError("Path must remain inside the workspace")
        return resolved

    def capabilities(self):
        desktop = bool(importlib.util.find_spec("pyautogui")) and (os.name == "nt" or sys.platform == "darwin" or bool(os.environ.get("DISPLAY")))
        return {"workspace": True, "python": bool(self.settings["python_enabled"]),
                "python_sandbox": False, "network": bool(self.settings["network_enabled"]),
                "browser": False, "desktop": bool(self.settings["desktop_enabled"] and desktop),
                "desktop_installed": desktop, "research_transport": "public_https",
                "sensory_features": True, "sensor_capture": "browser_prompt_only",
                "sensory_semantic_recognition": False}

    def schemas(self):
        values = [schema("list_files", "List a directory inside the user's workspace", {"path": STRING}),
                  schema("read_file", "Read a UTF-8 text file inside the workspace", {"path": STRING}, ["path"]),
                  schema("write_file", "Save a UTF-8 file in the workspace; returns canonical artifact identity",
                         {"path": STRING, "content": STRING}, ["path", "content"]),
                  schema("analyze_sensory_file", "Analyze a bounded workspace PNG/PCM WAV after explicit approval. Returns low-level features and artificial color/tone cues, not object recognition or speech transcription.", {"path": STRING}, ["path"])]
        if self.settings["python_enabled"]:
            values.append(schema("run_python", "Run a workspace Python script after the user approves this exact action. Full host access; not an OS sandbox.", {"path": STRING}, ["path"]))
        if self.settings["network_enabled"]:
            values.append(schema("fetch_url", "Retrieve a public HTTPS page and retain raw source evidence. HTTP retrieval; no JavaScript or account login.", {"url": STRING}, ["url"]))
        if self.capabilities()["desktop"]:
            values.extend([
                schema("desktop_screenshot", "Capture the desktop after explicit approval", {}),
                schema("desktop_click", "Click a known desktop location after explicit approval", {"x": {"type": "integer"}, "y": {"type": "integer"}}, ["x", "y"]),
                schema("desktop_type", "Type text into the focused application after explicit approval", {"text": STRING}, ["text"]),
                schema("desktop_key", "Press a single keyboard key after explicit approval", {"key": STRING}, ["key"])])
        return values

    def approval_details(self, name, arguments):
        if name == "analyze_sensory_file":
            p = self.path(arguments["path"])
            if p.suffix.lower() not in (".png", ".wav") or not p.is_file():
                raise ValueError("Choose an existing workspace PNG or WAV file")
            data = read_regular(p)
            return {"media_sha256": hashlib.sha256(data).hexdigest(), "media_bytes": len(data)}
        if name == "run_python":
            p = self.path(arguments["path"])
            if p.suffix != ".py" or not p.is_file():
                raise ValueError("Choose an existing workspace .py file")
            source = read_regular(p)
            if len(source) > MAX_FILE:
                raise ValueError("Script exceeds 256 KiB limit")
            return {"script_sha256": hashlib.sha256(source).hexdigest(), "script_bytes": len(source)}
        return {}

    def execute(self, name, arguments, run_id, cancelled=lambda: False, *, approved=False, approval_binding=None, timeout=15):
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object")
        allowed = {s["function"]["name"]: s["function"]["parameters"] for s in self.schemas()}
        if name not in allowed:
            raise ValueError("Tool is unavailable or disabled: " + name)
        spec = allowed[name]
        if set(arguments) - set(spec["properties"]) or not set(spec["required"]).issubset(arguments):
            raise ValueError("Tool arguments do not match the declared contract")
        if name in self.APPROVAL and not approved:
            raise PermissionError("This action requires approval")
        if cancelled():
            raise InterruptedError("Request cancelled")
        if name == "list_files":
            folder = self.path(arguments.get("path", "."))
            if not folder.is_dir():
                raise ValueError("Folder does not exist")
            files = []
            for p in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:200]:
                if p.is_symlink():
                    continue
                files.append({"name": p.name, "path": p.relative_to(self.workspace).as_posix(),
                              "directory": p.is_dir(), "size": p.stat().st_size if p.is_file() else 0})
            return {"files": files, "path": folder.relative_to(self.workspace).as_posix()}
        if name == "read_file":
            p = self.path(arguments["path"])
            data = read_regular(p)
            if len(data) > MAX_FILE:
                raise ValueError("File exceeds 256 KiB text limit")
            return {"content": data.decode("utf-8"), "path": p.relative_to(self.workspace).as_posix(),
                    "sha256": hashlib.sha256(data).hexdigest()}
        if name == "analyze_sensory_file":
            p = self.path(arguments["path"])
            if p.suffix.lower() not in (".png", ".wav") or not p.is_file():
                raise ValueError("Choose a PNG or WAV file")
            if not isinstance(approval_binding, dict) or not isinstance(approval_binding.get("media_sha256"), str):
                raise PermissionError("Sensory file analysis requires exact-source approval")
            data = read_regular(p)
            if hashlib.sha256(data).hexdigest() != approval_binding["media_sha256"]:
                raise PermissionError("Sensory file changed after approval")
            return sensory_fusion(image=data if p.suffix.lower() == ".png" else None,
                                  audio=data if p.suffix.lower() == ".wav" else None,
                                  source="workspace_file", consent=approved)
        if name == "write_file":
            p = self.path(arguments["path"])
            content = arguments["content"]
            if not isinstance(content, str):
                raise ValueError("File content must be text")
            data = content.encode()
            if len(data) > MAX_FILE:
                raise ValueError("File exceeds 256 KiB limit")
            if p == self.workspace or p.is_dir():
                raise ValueError("Choose a filename")
            previous = None
            if p.exists():
                old = read_regular(p)
                if len(old) > MAX_FILE:
                    raise ValueError("Existing file exceeds backup limit")
                previous = self.store.artifact("studio/backups/" + run_id + "/" + p.relative_to(self.workspace).as_posix(), old, "application/octet-stream")
            p.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix=".merlin-", dir=str(p.parent))
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, p)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            ref = self.store.artifact("studio/workspace/" + p.relative_to(self.workspace).as_posix(), data, "text/plain")
            return {"written": p.relative_to(self.workspace).as_posix(), "bytes": len(data), "artifact_ref": ref, "previous_artifact_ref": previous}
        if name == "fetch_url":
            result = fetch_public(arguments["url"], timeout=timeout)
            body = result.pop("body")
            logical = "studio/sources/" + run_id + "/" + result["sha256"]
            ref = self.store.artifact(logical + "/body", body, result["content_type"])
            result["artifact_ref"] = ref
            result["source_receipt"] = self.store.artifact(logical + "/receipt.json", {k: v for k, v in result.items() if k != "text"})
            result["text"] = result["text"][:45000]
            return result
        if name == "run_python":
            p = self.path(arguments["path"])
            if p.suffix != ".py" or not p.is_file():
                raise ValueError("Choose an existing workspace .py file")
            if not isinstance(approval_binding, dict) or "script_sha256" not in approval_binding:
                raise PermissionError("Script approval must bind the exact source bytes")
            source = read_regular(p)
            if len(source) > MAX_FILE or hashlib.sha256(source).hexdigest() != approval_binding["script_sha256"]:
                raise PermissionError("Script changed after approval; request a new approval")
            # Execute immutable approved bytes, even if the workspace path changes next.
            with tempfile.TemporaryDirectory(prefix="merlin-approved-") as folder:
                snapshot = Path(folder) / p.name
                snapshot.write_bytes(source)
                return {**self._python(snapshot, cancelled, timeout=timeout), "script_sha256": approval_binding["script_sha256"]}
        return self._desktop(name, arguments)

    def _python(self, script, cancelled, *, timeout=15):
        # Environment credentials are not forwarded to generated scripts.
        environment = {k: v for k, v in os.environ.items() if k in ("PATH", "SystemRoot", "TEMP", "TMP", "LANG")}
        environment["PYTHONIOENCODING"] = "utf-8"
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            proc = subprocess.Popen([sys.executable, "-I", str(Path(__file__).with_name("worker.py")), str(script)],
                                    cwd=str(self.workspace), env=environment, stdin=subprocess.DEVNULL,
                                    stdout=stdout, stderr=stderr, start_new_session=(os.name != "nt"))
            deadline = time.monotonic() + min(15.0, max(0.01, timeout))
            reason = None
            try:
                while proc.poll() is None:
                    if os.fstat(stdout.fileno()).st_size > 128 * 1024 or os.fstat(stderr.fileno()).st_size > 128 * 1024:
                        reason = "output_limit"
                        self._kill(proc)
                        break
                    if cancelled() or time.monotonic() >= deadline:
                        reason = "cancelled" if cancelled() else "timeout"
                        self._kill(proc)
                        break
                    time.sleep(0.05)
                proc.wait(timeout=3)
            finally:
                # Also terminate descendants in this process group after the worker exits.
                self._kill(proc)
            stdout.seek(0)
            stderr.seek(0)
            out, err = stdout.read(65537), stderr.read(65537)
            return {"exit_code": proc.returncode, "stdout": out[:65536].decode("utf-8", "replace"),
                    "stderr": err[:65536].decode("utf-8", "replace"), "termination": reason or "completed",
                    "truncated": len(out) > 65536 or len(err) > 65536, "os_sandbox": False}

    @staticmethod
    def _kill(proc):
        try:
            if os.name != "nt":
                os.killpg(proc.pid, signal.SIGKILL)
            elif proc.poll() is None:
                proc.kill()
        except ProcessLookupError:
            pass

    def _desktop(self, name, arguments):
        if not self.capabilities()["desktop"]:
            raise PermissionError("Desktop control is unavailable")
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.2
        if name == "desktop_screenshot":
            folder = self.workspace / "captures"
            folder.mkdir(exist_ok=True)
            from storage import identity
            target = folder / (identity() + ".png")
            pyautogui.screenshot().save(target)
            return {"path": target.relative_to(self.workspace).as_posix()}
        if name == "desktop_click":
            x, y = arguments["x"], arguments["y"]
            width, height = pyautogui.size()
            if type(x) is not int or type(y) is not int or not 0 <= x < width or not 0 <= y < height:
                raise ValueError("Click is outside the desktop")
            pyautogui.click(x, y)
        elif name == "desktop_type":
            value = arguments["text"]
            if not isinstance(value, str) or len(value) > 2000 or not value.isascii():
                raise ValueError("Desktop typing accepts at most 2000 ASCII characters")
            pyautogui.write(value, interval=0.01)
        elif name == "desktop_key":
            key = arguments["key"]
            if key not in pyautogui.KEYBOARD_KEYS:
                raise ValueError("Unknown keyboard key")
            pyautogui.press(key)
        else:
            raise ValueError("Unknown desktop action")
        return {"completed": name}
