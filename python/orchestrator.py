#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentRole:
    name: str
    model_id: str


ROLES = {
    "controller": AgentRole("controller", "Qwen/Qwen3.5-4B"),
    "coder": AgentRole("coder", "Qwen/Qwen3-Coder-30B-A3B-Instruct"),
    "learner": AgentRole("learner", "Qwen/Qwen3-30B-A3B-Base"),
    "math": AgentRole("math", "Qwen/Qwen2.5-Math-7B-Instruct"),
}


class RuntimeProcess:
    """A bounded JSONL process connection. This is supervision, not an OS sandbox.

    Every request owns the connection until its response arrives. On timeout or
    protocol failure the process is stopped, so a late response cannot be used
    for another request. Python worker argv is supported for portable tests.
    """

    def __init__(self, executable: str | list[str] | tuple[str, ...], *,
                 request_timeout: float = 30.0, shutdown_timeout: float = 2.0,
                 max_response_bytes: int = 1024 * 1024,
                 max_request_bytes: int = 256 * 1024) -> None:
        for value in (request_timeout, shutdown_timeout):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 300:
                raise ValueError("runtime timeouts must be finite seconds between 0 and 300")
        for value in (max_response_bytes, max_request_bytes):
            if type(value) is not int or not 1 <= value <= 16 * 1024 * 1024:
                raise ValueError("runtime message limits must be between 1 and 16777216 bytes")
        command = [executable] if isinstance(executable, str) else list(executable)
        if not command or any(not isinstance(part, str) or not part for part in command):
            raise ValueError("runtime command must contain nonempty strings")
        self.request_timeout = float(request_timeout)
        self.shutdown_timeout = float(shutdown_timeout)
        self.max_response_bytes = max_response_bytes
        self.max_request_bytes = max_request_bytes
        self._request_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._closed = False
        self._stopped = False
        self._exchange_thread = None
        self._proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            start_new_session=(os.name == "posix"),
        )

    def request(self, role: str, task: str, *, timeout: float | None = None) -> dict:
        limit = self.request_timeout if timeout is None else timeout
        if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or not 0 < limit <= 300:
            raise ValueError("request timeout must be finite seconds between 0 and 300")
        if not isinstance(role, str) or not role or not isinstance(task, str):
            raise ValueError("role and task must be strings")
        payload = {
            "id": str(uuid.uuid4()),
            "role": role,
            "task": task,
        }
        encoded = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        if len(encoded) > self.max_request_bytes:
            raise ValueError("runtime request exceeds byte limit")
        deadline = time.monotonic() + limit
        if not self._request_lock.acquire(timeout=limit):
            raise TimeoutError("runtime request queue timed out")
        try:
            if self._closed or self._proc.poll() is not None:
                raise RuntimeError("runtime process is not running")
            results = queue.Queue(maxsize=1)
            def exchange():
                try:
                    self._proc.stdin.write(encoded)
                    self._proc.stdin.flush()
                    line = self._proc.stdout.readline(self.max_response_bytes + 1)
                    if not line:
                        raise RuntimeError("runtime exited before returning a response")
                    if len(line) > self.max_response_bytes:
                        raise RuntimeError("runtime response exceeds byte limit")
                    if not line.endswith(b"\n"):
                        raise RuntimeError("runtime response is not a complete JSONL record")
                    response = json.loads(line)
                    if not isinstance(response, dict):
                        raise RuntimeError("runtime response must be an object")
                    if response.get("id") != payload["id"]:
                        raise RuntimeError("runtime response identity mismatch")
                    if type(response.get("ok")) is not bool:
                        raise RuntimeError("runtime response ok must be bool")
                    results.put((response, None))
                except Exception as exc:
                    results.put((None, exc))
            self._exchange_thread = threading.Thread(target=exchange, daemon=True)
            self._exchange_thread.start()
            try:
                response, error = results.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty:
                self.close()
                raise TimeoutError("runtime response timed out; process stopped") from None
            if error is not None:
                self.close()
                raise error
            return response
        finally:
            self._request_lock.release()

    @property
    def pid(self) -> int:
        return self._proc.pid

    @property
    def running(self) -> bool:
        return not self._closed and self._proc.poll() is None

    def close(self) -> None:
        # Stop before closing stdin: flushing a full pipe can itself block.
        with self._close_lock:
            if self._stopped:
                return
            self._closed = True
            def stop(force=False):
                try:
                    if os.name == "posix":
                        os.killpg(self._proc.pid, signal.SIGKILL if force else signal.SIGTERM)
                    elif self._proc.poll() is None:
                        self._proc.kill() if force else self._proc.terminate()
                except ProcessLookupError:
                    pass
            stop()
            try:
                self._proc.wait(timeout=self.shutdown_timeout)
            except subprocess.TimeoutExpired:
                stop(force=True)
                self._proc.wait(timeout=self.shutdown_timeout)
            # POSIX children may outlive the direct parent or ignore SIGTERM.
            if os.name == "posix":
                stop(force=True)
            worker = self._exchange_thread
            if worker is not None and worker is not threading.current_thread():
                worker.join(timeout=self.shutdown_timeout)
            # Never wait for a stream lock held by an uninterruptible reader.
            if worker is None or not worker.is_alive():
                for stream in (self._proc.stdin, self._proc.stdout):
                    if stream:
                        try:
                            stream.close()
                        except (OSError, ValueError):
                            pass
            self._stopped = True


def main() -> int:
    parser = argparse.ArgumentParser(description="Expert Robot Python orchestrator")
    parser.add_argument("--runtime", required=True, help="Path to C++ expert_robot_runtime")
    parser.add_argument("--role", choices=sorted({"health", *ROLES}), default="health")
    parser.add_argument("--task", default="check")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request deadline in seconds")
    args = parser.parse_args()

    runtime = RuntimeProcess(args.runtime, request_timeout=args.timeout)
    try:
        response = runtime.request(args.role, args.task)
        print(json.dumps(response, indent=2))
        return 0 if response.get("ok") else 1
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())

