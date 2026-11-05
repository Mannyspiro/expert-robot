#!/usr/bin/env python3

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path
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
    parser.add_argument("--plan", type=Path, help="Validated Merlin engineering/research plan JSON; required for every non-health-check task")
    args = parser.parse_args()

    # The sole planless exception is the exact, non-mutating runtime health check.
    if args.task.strip().lower() != "health check" and args.plan is None:
        parser.error("--plan is required for every task other than the exact 'health check'")

    if args.plan is not None:
        plan_path = Path(__file__).resolve().parents[1] / "scripts" / "merlin_engineering_plan.py"
        validation = subprocess.run(
            [sys.executable, str(plan_path), "--validate", str(args.plan)],
            capture_output=True, text=True, check=False,
        )
        if validation.returncode != 0:
            print(validation.stdout or validation.stderr, file=sys.stderr)
            return 2
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        plan_raw = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        plan_digest = hashlib.sha256(plan_raw).hexdigest()
        args.task = (
            "MANDATORY MERLIN ENGINEERING PLAN (validated; sha256=" + plan_digest + ")\\n"
            + json.dumps(plan, ensure_ascii=False, indent=2)
            + "\\nFollow this plan. Do not silently change scope, requirements, assumptions, budgets, or acceptance criteria. "
              "If the plan is infeasible or incomplete, stop and return the discrepancy rather than improvising.\\n\\n"
            + "TASK:\\n" + args.task
        )

    runtime = RuntimeProcess(args.runtime)
    try:
        response = runtime.request(args.role, args.task)
        print(json.dumps(response, indent=2))
        return 0 if response.get("ok") else 1
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
