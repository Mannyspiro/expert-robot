#!/usr/bin/env python3

import json
import pathlib
import subprocess
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: smoke.py <runtime>")
        return 2

    runtime = pathlib.Path(sys.argv[1])
    proc = subprocess.Popen(
        [str(runtime)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    proc.stdin.write(json.dumps({"id": "smoke-1", "role": "math", "task": "2+2"}) + "\n")
    proc.stdin.flush()

    response = json.loads(proc.stdout.readline())
    proc.terminate()
    proc.wait(timeout=5)

    assert response["id"] == "smoke-1"
    # The generic protocol runtime is deliberately model-stateless. Model-backed
    # math research belongs to expert_robot_research, so fail closed here rather
    # than pretending an unavailable model response is healthy.
    assert response["ok"] is False
    assert "use expert_robot_research" in response.get("error", "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
