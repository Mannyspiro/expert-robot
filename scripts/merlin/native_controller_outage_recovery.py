#!/usr/bin/env python3
"""Real controller-outage recovery test against a disposable OpenSandbox server.

No new sandbox may start while durable owned work exists and the controller
cannot verify cleanup. The script pauses only the ephemeral test controller,
then resumes it and demonstrates owner-scoped recovery after another restart.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
import time

from native_studio_orphan_recovery import (
    start_owned_process, stop, wait_running_script
)
from native_studio_http_approval_acceptance import (
    request, wait_for, start_run, require
)
from native_sandbox_acceptance import (
    SANDBOX_LABEL, matching_containers, runtime_volumes,
    all_managed_containers, confirm_absent
)
from storage import Store


def main():
    parser = argparse.ArgumentParser(description="Test fail-closed Studio recovery during a real OpenSandbox controller outage")
    parser.add_argument("--controller-pid-file", required=True)
    args = parser.parse_args()
    require(os.environ.get("MERLIN_PYTHON_BACKEND") == "opensandbox",
            "Native controller test requires an opted-in sandbox backend")
    require("@sha256:" in os.environ.get("MERLIN_SANDBOX_IMAGE", ""),
            "A pinned image is required")
    require(not all_managed_containers() and not runtime_volumes(),
            "Expected clean runner before outage test")
    controller_pid = int(Path(args.controller_pid_file).read_text().strip())
    require(controller_pid not in (os.getpid(), os.getppid()) and controller_pid > 1,
            "Controller PID must identify an independent test process")
    os.kill(controller_pid, 0)

    original = None
    blocked = None
    recovered = None
    paused = False
    with tempfile.TemporaryDirectory(prefix="merlin-controller-offline-") as directory:
        data_dir = Path(directory) / "studio-data"
        try:
            original, port = start_owned_process(data_dir)
            code, status = request(port, "GET", "/api/status")
            require(code == 200 and status["capabilities"]["python_sandbox"],
                    "Healthy first Studio had no sandbox backend")
            token = status["session_token"]
            code, value = request(port, "POST", "/api/conversations",
                                  {"title": "Controlled offline controller"}, token=token)
            require(code == 201, "Cannot create controller-outage conversation")
            cid = value["conversation"]["id"]
            source = "import time\nprint('MERLIN_CONTROLLER_OUTAGE_FIXTURE',flush=True)\ntime.sleep(90)\n"
            code, _ = request(port, "POST", "/api/tool",
                              {"tool": "write_file", "args": {"path": "offline.py", "content": source}}, token=token)
            require(code == 200, "Cannot create controlled fixture")
            run_id = start_run(port, token, cid, "/python offline.py")
            pending = wait_for(port, run_id, {"waiting_approval"}, timeout=12)
            approval = pending["pending_approval"]
            require(approval["arguments"]["script_sha256"] == hashlib.sha256(source.encode()).hexdigest(),
                    "Source identity mismatch")
            code, _ = request(port, "POST", "/api/runs/" + run_id + "/approve",
                              {"approval_id": approval["id"], "approved": True}, token=token)
            require(code == 200, "Approved fixture denied")
            sandbox_id = wait_running_script(set())
            require(len(Store(data_dir).sandbox_pending()) == 1,
                    "Running sandbox had no persisted intent")
            stop(original)
            original = None
            require(bool(matching_containers(SANDBOX_LABEL + "=" + sandbox_id)),
                    "Remote sandbox did not survive the Studio crash")

            # Make the controller genuinely unreachable while Docker continues
            # to run. A blocked process should not be mistaken for terminated.
            os.kill(controller_pid, signal.SIGSTOP)
            paused = True
            blocked, offline_port = start_owned_process(data_dir)
            code, snapshot = request(offline_port, "GET", "/api/status")
            require(code == 200, "Blocked Studio should still serve its local API")
            caps = snapshot["capabilities"]
            recovery = snapshot["sandbox_recovery"]
            require(not caps["python"] and not caps["python_sandbox"]
                    and caps["python_setup_required"]
                    and not recovery["ready"] and recovery["pending_count"] == 1
                    and recovery["last_error"],
                    "Controller outage falsely left sandbox execution enabled")
            require(bool(matching_containers(SANDBOX_LABEL + "=" + sandbox_id)),
                    "The test controller outage did not leave remote script observable")
            code, run = request(offline_port, "GET", "/api/runs/" + run_id)
            require(code == 200 and run["run"]["status"] == "interrupted",
                    "Crashed run was not marked interrupted")
            old, _ = request(offline_port, "POST", "/api/runs/" + run_id + "/approve",
                             {"approval_id": approval["id"], "approved": True},
                             token=snapshot["session_token"])
            require(old == 400, "Old approval accepted during controller outage")
            stop(blocked)
            blocked = None

            # Restore the *same* local controller; the next startup must
            # reconcile the prior sandbox without replaying the script.
            os.kill(controller_pid, signal.SIGCONT)
            paused = False
            time.sleep(.3)
            recovered, recovery_port = start_owned_process(data_dir)
            code, snapshot = request(recovery_port, "GET", "/api/status")
            require(code == 200 and snapshot["sandbox_recovery"]["ready"]
                    and snapshot["sandbox_recovery"]["pending_count"] == 0
                    and snapshot["capabilities"]["python_sandbox"],
                    "Reconnected controller did not unblock only after cleanup")
            for _ in range(70):
                if (not matching_containers(SANDBOX_LABEL + "=" + sandbox_id)
                        and not runtime_volumes()):
                    break
                time.sleep(.2)
            confirm_absent(sandbox_id)
            require(not all_managed_containers() and not runtime_volumes(),
                    "Owned sandbox resources were not removed after controller recovery")
            require(not Store(data_dir).sandbox_pending(),
                    "Pending ownership record was incorrectly retained after verified cleanup")
            code, run = request(recovery_port, "GET", "/api/runs/" + run_id)
            require(code == 200 and run["run"]["status"] == "interrupted"
                    and not any(x["type"] == "tool_result" for x in run["run"]["events"]),
                    "Controller recovery replayed the abandoned script")
            print(json.dumps({
                "schema": "merlin-studio-native-controller-outage-recovery/1",
                "real_docker": True,
                "test_controller_sigstop": True,
                "remote_script_survived_process_crash": True,
                "controller_unreachable_during_recovery": True,
                "python_sandbox_disabled_while_unverified": True,
                "owner_intent_preserved_while_offline": True,
                "controller_restored": True,
                "orphan_resources_removed": True,
                "pending_intents_after_recovery": 0,
                "stale_approval_accepted": False,
                "abandoned_script_replayed": False,
                "sandbox_id": sandbox_id,
                "model_calls": 0,
                "target_host_qualified": False
            }, sort_keys=True))
        finally:
            if paused:
                os.kill(controller_pid, signal.SIGCONT)
            stop(original)
            stop(blocked)
            stop(recovered)
    require(not all_managed_containers() and not runtime_volumes(),
            "Controller outage test left managed resources")


if __name__ == "__main__":
    main()
