#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
import uuid
from dataclasses import dataclass

from research_protocol import prepare_research_task


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Expert Robot Python orchestrator")
    parser.add_argument("--runtime", required=True, help="Path to C++ expert_robot_runtime")
    parser.add_argument("--role", choices=sorted(ROLES), default="controller")
    parser.add_argument("--task", default="health check")
    parser.add_argument(
        "--research-protocol", choices=("auto", "always", "off"),
        default="auto", help="Apply the versioned research protocol automatically, always, or never",
    )
    args = parser.parse_args()

    runtime = RuntimeProcess(args.runtime)
    try:
        runtime_task, protocol_status = prepare_research_task(
            args.task, mode=args.research_protocol
        )
        print(
            json.dumps({"event": "research_protocol_activation", **protocol_status}),
            file=sys.stderr,
        )
        response = runtime.request(args.role, runtime_task)
        print(json.dumps(response, indent=2))
        return 0 if response.get("ok") else 1
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
