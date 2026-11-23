#!/usr/bin/env python3
"""Native real-Docker cancellation while a Studio-approved Python process runs.

The test waits for independent Docker-top evidence of the actual script
process, then cancels the ToolSet call and verifies remote kill and cleanup.
No model, external network account or user-owned workspace is accessed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

STUDIO = Path(__file__).resolve().parents[2] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
from tools import ToolSet
from native_sandbox_acceptance import (
    SANDBOX_LABEL, all_managed_containers, confirm_absent, docker,
    matching_containers, runtime_volumes
)


def main():
    if os.environ.get("MERLIN_PYTHON_BACKEND") != "opensandbox":
        raise AssertionError("Explicit local OpenSandbox opt-in is required")
    if "@sha256:" not in os.environ.get("MERLIN_SANDBOX_IMAGE", ""):
        raise AssertionError("Immutable Docker image is required")
    initial = all_managed_containers()
    if initial or runtime_volumes():
        raise AssertionError("Native CI host was not clean before cancellation test")
    with tempfile.TemporaryDirectory(prefix="merlin-native-cancel-") as directory:
        root = Path(directory)
        code = b"import time\nprint('MERLIN_LONG_RUNNING', flush=True)\ntime.sleep(90)\n"
        (root / "long.py").write_bytes(code)
        settings = {"python_enabled": True, "network_enabled": False, "desktop_enabled": False}
        tool = ToolSet(root, object(), settings)
        binding = tool.approval_details("run_python", {"path": "long.py"})
        if binding["script_sha256"] != hashlib.sha256(code).hexdigest():
            raise AssertionError("Approved source bytes differ")
        signal = threading.Event()
        outcome = {}
        def execute():
            try:
                outcome["result"] = tool.execute(
                    "run_python", {"path": "long.py"}, "native-cancel-test",
                    cancelled=signal.is_set, approved=True,
                    approval_binding=binding, timeout=25)
            except BaseException as error:
                outcome["error"] = error
        thread = threading.Thread(target=execute)
        thread.start()
        sandbox_id = None
        container_id = None
        observed_at = None
        deadline = time.monotonic() + 45
        try:
            while time.monotonic() < deadline and thread.is_alive():
                for container in matching_containers(SANDBOX_LABEL) - initial:
                    try:
                        command_table = docker("top", container, timeout=5)
                        inspected = json.loads(docker("inspect", container, timeout=5))[0]
                    except (RuntimeError, ValueError, IndexError):
                        continue
                    if "/tmp/merlin_approved.py" not in command_table:
                        continue
                    container_id = container
                    sandbox_id = (inspected.get("Config", {}).get("Labels") or {}).get(SANDBOX_LABEL)
                    if sandbox_id:
                        observed_at = time.monotonic()
                        break
                if observed_at is not None:
                    break
                time.sleep(0.15)
        finally:
            signal.set()
            thread.join(timeout=15)
        if observed_at is None or not sandbox_id:
            raise AssertionError("Independent Docker-top inspection never saw the running approved Python process")
        if thread.is_alive():
            raise AssertionError("Studio cancellation monitor did not terminate")
        if not isinstance(outcome.get("error"), InterruptedError) or "result" in outcome:
            raise AssertionError("Studio did not report an interrupted, uncompleted tool result")
        cleanup_deadline = time.monotonic() + 15
        while time.monotonic() < cleanup_deadline:
            if (not matching_containers(SANDBOX_LABEL + "=" + sandbox_id)
                    and not matching_containers("opensandbox.io/egress-sidecar-for=" + sandbox_id)
                    and "opensandbox-runtime-" + sandbox_id not in runtime_volumes()):
                break
            time.sleep(0.2)
        confirm_absent(sandbox_id)
        if all_managed_containers() != initial or runtime_volumes():
            raise AssertionError("Canceled script left behind managed Docker resources")
        elapsed = time.monotonic() - observed_at
        if elapsed >= 15:
            raise AssertionError("Cancellation took too long after process observation")
        print(json.dumps({
            "schema": "merlin-native-active-sandbox-cancel/1",
            "real_docker": True, "real_studio_toolset": True,
            "observed_running_python_process": True,
            "approved_script_sha256": binding["script_sha256"],
            "sandbox_id": sandbox_id,
            "remote_resources_removed": True,
            "reported_interruption": True,
            "elapsed_after_cancel_observation_s": round(elapsed, 2),
            "test_isolation_scope": "ephemeral Ubuntu Docker with OpenSandbox",
            "production_host_qualified": False,
        }, sort_keys=True))


if __name__ == "__main__":
    main()
