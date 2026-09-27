#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid
from dataclasses import dataclass

from cace_headless import CACEHeadlessClient, HeadlessConfig


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
    def __init__(self, executable: str) -> None:
        self._proc = subprocess.Popen(
            [executable],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
        )

    def request(self, role: str, task: str) -> dict:
        if self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("runtime pipes unavailable")

        payload = {
            "id": str(uuid.uuid4()),
            "role": role,
            "task": task,
        }
        self._proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self._proc.stdin.flush()

        line = self._proc.stdout.readline()
        if not line:
            raise RuntimeError("C++ runtime exited before returning a response")
        return json.loads(line)

    def close(self) -> None:
        if self._proc.stdin:
            self._proc.stdin.close()
        self._proc.terminate()
        self._proc.wait(timeout=5)


def _default_cace_config() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "cace_headless_local.json"


def cace_reasoned_response(
    runtime_response: dict,
    *,
    role: str,
    task: str,
    config_path: str | Path,
    timeout: float = 30.0,
) -> dict:
    """Attach local CACE/Qwen reasoning after the C++ runtime admits a task.

    The C++ runtime remains the admission/control boundary. The local model is
    an untrusted reasoning backend and cannot manufacture verification.
    """
    if not runtime_response.get("ok"):
        return runtime_response

    config = HeadlessConfig.load(config_path)
    client = CACEHeadlessClient(config, timeout=timeout)
    assistant = client.research_turn(
        "Expert Robot admitted this task.\n"
        f"Role: {role}\n"
        f"Task: {task}\n\n"
        "Respond as the local research assistant. Propose typed CACE actions when "
        "useful, but do not claim they executed or were verified."
    )
    return {
        "id": runtime_response.get("id", ""),
        "ok": True,
        "role": role,
        "reasoning_backend": "cace-headless-local",
        "runtime_admission": runtime_response,
        "assistant": assistant,
        "authority_expanded": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Expert Robot Python orchestrator")
    parser.add_argument("--runtime", required=True, help="Path to C++ expert_robot_runtime")
    parser.add_argument("--role", choices=sorted(ROLES), default="controller")
    parser.add_argument("--task", default="health check")
    parser.add_argument(
        "--reasoning-backend",
        choices=("runtime-stub", "cace-headless"),
        default="runtime-stub",
        help=(
            "runtime-stub preserves the existing deterministic smoke path; "
            "cace-headless uses the local CACE/Qwen reasoning service after runtime admission"
        ),
    )
    parser.add_argument("--cace-config", default=str(_default_cace_config()))
    parser.add_argument("--cace-timeout", type=float, default=30.0)
    args = parser.parse_args()

    runtime = RuntimeProcess(args.runtime)
    try:
        response = runtime.request(args.role, args.task)
        if args.reasoning_backend == "cace-headless":
            response = cace_reasoned_response(
                response,
                role=args.role,
                task=args.task,
                config_path=args.cace_config,
                timeout=args.cace_timeout,
            )
        print(json.dumps(response, indent=2))
        return 0 if response.get("ok") else 1
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
