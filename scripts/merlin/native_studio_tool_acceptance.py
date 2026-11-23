#!/usr/bin/env python3
"""Native Studio ToolSet -> approved OpenSandbox -> Docker cleanup smoke.

CI fixture supplies a synthetic affirmative approval; this is not a test of
interactive UI consent. It does exercise the real Studio tool dispatcher,
source bytes, backend and Docker execution, without running host Python.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

STUDIO = Path(__file__).resolve().parents[2] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
from tools import ToolSet
from storage import Store
from sandbox_recovery import SandboxRecovery
from native_sandbox_acceptance import all_managed_containers, confirm_absent, runtime_volumes


def main():
    if os.environ.get("MERLIN_PYTHON_BACKEND") != "opensandbox":
        raise RuntimeError("Native test requires explicit OpenSandbox backend selection")
    image = os.environ.get("MERLIN_SANDBOX_IMAGE")
    if not image or "@sha256:" not in image:
        raise RuntimeError("Native Studio test requires an immutable container image digest")
    before_containers, before_volumes = all_managed_containers(), runtime_volumes()
    if before_containers or before_volumes:
        raise AssertionError("Expected a clean isolated CI runner before native Studio test")
    with tempfile.TemporaryDirectory(prefix="merlin-studio-native-") as directory:
        workspace = Path(directory) / "workspace"
        workspace.mkdir()
        data = b"print('MERLIN_STUDIO_NATIVE_OK')\n"
        (workspace / "answer.py").write_bytes(data)
        settings = {"python_enabled": True, "desktop_enabled": False, "network_enabled": False}
        store = Store(Path(directory) / "state")
        store.acquire_sandbox_lease()
        tracker = SandboxRecovery(store, 8080)
        store.sandbox_recovery = tracker
        tracker.reconcile()
        tool = ToolSet(workspace, store, settings)
        run_id = "a" * 32
        if not tool.capabilities()["python_sandbox"]:
            raise AssertionError("Studio did not advertise explicit configured sandbox")
        approval = tool.approval_details("run_python", {"path": "answer.py"})
        if approval.get("backend") != "opensandbox" or approval.get("script_sha256") != hashlib.sha256(data).hexdigest():
            raise AssertionError("Studio sandbox approval did not bind bytes and backend")
        try:
            tool.execute("run_python", {"path": "answer.py"}, run_id,
                         approved=False, approval_binding=approval)
        except PermissionError:
            pass
        else:
            raise AssertionError("Studio accepted a Python action without approval")
        started = time.monotonic()
        result = tool.execute("run_python", {"path": "answer.py"}, run_id,
                              approved=True, approval_binding=approval, timeout=15)
        elapsed = time.monotonic() - started
        if (result["exit_code"] != 0 or "MERLIN_STUDIO_NATIVE_OK" not in result["stdout"]
                or result.get("script_sha256") != approval["script_sha256"]
                or result.get("os_sandbox") is not True
                or not result.get("sandbox_id")
                or result.get("sandbox_provider") != "OpenSandbox"):
            raise AssertionError("Actual Studio ToolSet sandbox result failed expected contract")
        if store.sandbox_pending():
            raise AssertionError("Durable sandbox ownership intent was not cleared")
        store.release_sandbox_lease()
        confirm_absent(result["sandbox_id"])
        if all_managed_containers() != before_containers or runtime_volumes() != before_volumes:
            raise AssertionError("Studio ToolSet left containers or volumes after native execution")
        print(json.dumps({"schema": "merlin-studio-native-tool-acceptance/1",
                          "real_docker": True, "manual_fixture_approval": True,
                          "interactive_user_consent_qualified": False,
                          "sandbox_id": result["sandbox_id"],
                          "image": image, "stdout_sentinel": "MERLIN_STUDIO_NATIVE_OK",
                          "script_sha256": approval["script_sha256"],
                          "elapsed_seconds": round(elapsed, 2),
                          "cleanup_verified": True, "host_python_fallback": False},
                         sort_keys=True))


if __name__ == "__main__":
    main()
