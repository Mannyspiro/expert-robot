#!/usr/bin/env python3
"""Native, Docker-backed OpenSandbox acceptance test on an isolated CI runner.

Uses the actual pinned OpenSandbox server and SDK, not a mocked model or fake
network policy. Read-only Docker inspection verifies resource configuration
and lifecycle cleanup. No user workspaces, secrets, or real accounts are used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.request

from opensandbox_eval import execute_approved, read_approved_source

SANDBOX_LABEL = "opensandbox.io/id"
EGRESS_LABEL = "opensandbox.io/egress-sidecar-for"
MEMORY_LIMIT_BYTES = 512 * 1024 * 1024


def docker(*args, timeout=25):
    command = subprocess.run(["docker", *args], text=True, capture_output=True,
                             timeout=timeout, check=False)
    if command.returncode:
        raise RuntimeError("Docker inspection/control failed: " + " ".join(args[:3])
                           + " exit=" + str(command.returncode))
    return command.stdout.strip()


def matching_containers(label):
    output = docker("ps", "-aq", "--filter", "label=" + label)
    return {x.strip() for x in output.splitlines() if x.strip()}


def all_managed_containers():
    return matching_containers(SANDBOX_LABEL) | matching_containers(EGRESS_LABEL)


def runtime_volumes():
    return {item for item in docker("volume", "ls", "-q").splitlines()
            if item.startswith("opensandbox-runtime-")}


def confirm_absent(sandbox_id):
    if (matching_containers(SANDBOX_LABEL + "=" + sandbox_id)
            or matching_containers(EGRESS_LABEL + "=" + sandbox_id)):
        raise AssertionError("OpenSandbox left a main or egress container after destroy")
    if "opensandbox-runtime-" + sandbox_id in runtime_volumes():
        raise AssertionError("OpenSandbox left its runtime volume after destroy")


def validate_runtime_mounts(inspected):
    """Allow exactly the runtime's named volume, never an arbitrary host bind."""
    sandbox_id = inspected.get("label_sandbox_id")
    if not isinstance(sandbox_id, str) or not sandbox_id:
        raise AssertionError("Managed Docker sandbox ID label is missing")
    name = "opensandbox-runtime-" + sandbox_id
    expected_bind = name + ":/opt/opensandbox:rw"
    if inspected.get("binds") != [expected_bind]:
        raise AssertionError("Unexpected container mount in Docker HostConfig")
    mounts = inspected.get("mounts") or []
    if len(mounts) != 1 or mounts[0] != {
        "type": "volume", "name": name, "destination": "/opt/opensandbox", "rw": True
    }:
        raise AssertionError("Docker mount must be exactly the OpenSandbox managed runtime volume")
    return name


def run_source(source, *, image, timeout=10):
    if not isinstance(source, bytes):
        raise TypeError("fixture source must be bytes")
    with tempfile.TemporaryDirectory(prefix="merlin-native-fixture-") as folder:
        path = Path(folder) / "approved.py"
        path.write_bytes(source)
        approved_hash = hashlib.sha256(source).hexdigest()
        approved_bytes = read_approved_source(path, approved_hash)
        result = execute_approved(approved_bytes, image=image, timeout=timeout)
    if result.get("script_sha256") != approved_hash:
        raise AssertionError("OpenSandbox returned the wrong approved script identity")
    sandbox_id = result.get("sandbox_id")
    if not isinstance(sandbox_id, str) or not sandbox_id:
        raise AssertionError("Native sandbox identity missing")
    confirm_absent(sandbox_id)
    return result


class CanaryHandler(BaseHTTPRequestHandler):
    count = 0
    lock = threading.Lock()
    marker = "MERLIN_CANARY_POSITIVE_CONTROL"

    def log_message(self, *_):
        pass

    def do_GET(self):
        with self.lock:
            type(self).count += 1
        body = self.marker.encode("ascii")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def gateway_address():
    items = json.loads(docker("network", "inspect", "bridge"))
    if not isinstance(items, list) or len(items) != 1:
        raise AssertionError("Missing unique Docker bridge")
    for config in items[0].get("IPAM", {}).get("Config", []):
        value = config.get("Gateway")
        if isinstance(value, str) and "." in value:
            return value
    raise AssertionError("Docker bridge has no IPv4 gateway")


def assert_reachable_from_regular_container(image, url):
    # A positive control is essential: an unavailable server must not count
    # as proof of blocked sandbox traffic.
    code = ("import urllib.request; "
            "opener=urllib.request.build_opener(urllib.request.ProxyHandler({})); "
            "print(opener.open(" + repr(url) + ",timeout=6).read().decode())")
    output = docker("run", "--rm", "--network", "bridge", image,
                    "python", "-I", "-c", code, timeout=55)
    if CanaryHandler.marker not in output:
        raise AssertionError("Positive-control container did not reach test endpoint")
    return {"control": "docker_bridge_canary_reached", "marker_present": True}


def assert_network_denied(image, url, canary):
    script = (
        "import json, urllib.request\n"
        "opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))\n"
        "try:\n"
        "  r=opener.open(" + repr(url) + ",timeout=4)\n"
        "  print(json.dumps({'network':'LEAK','body':r.read(1024).decode('utf-8','replace')}))\n"
        "except (OSError,TimeoutError) as exc:\n"
        "  print(json.dumps({'network':'DENIED','error_class':type(exc).__name__}))\n"
    ).encode("utf-8")
    before = canary.count
    result = run_source(script, image=image, timeout=12)
    if result["exit_code"] != 0 or result["truncated"]:
        raise AssertionError("Sandbox network-denial fixture did not finish cleanly")
    try:
        probe = json.loads(result["stdout"].strip())
    except (ValueError, TypeError):
        raise AssertionError("Sandbox network fixture produced unparseable output") from None
    if probe.get("network") != "DENIED" or canary.count != before:
        raise AssertionError("Sandbox reached a destination denied by default policy")
    return {"network": "blocked_from_sandbox", "error_class": probe["error_class"],
            "sandbox_id": result["sandbox_id"], "script_sha256": result["script_sha256"]}


def inspect_running_container(image, prior):
    script = b"import time\nprint('MERLIN_RESOURCE_FIXTURE', flush=True)\ntime.sleep(5)\n"
    captured = {}
    errors = []
    before = matching_containers(SANDBOX_LABEL)
    def worker():
        try:
            captured["response"] = run_source(script, image=image, timeout=12)
        except Exception as exc:
            errors.append(str(type(exc).__name__) + ": " + str(exc))
    thread = threading.Thread(target=worker)
    thread.start()
    inspected = None
    deadline = time.monotonic() + 75
    try:
        while time.monotonic() < deadline and thread.is_alive():
            new_ids = matching_containers(SANDBOX_LABEL) - prior - before
            for identifier in new_ids:
                raw = docker("inspect", identifier)
                attrs = json.loads(raw)[0]
                host = attrs.get("HostConfig") or {}
                if not host.get("Memory"):
                    continue
                inspected = {
                    "container_id": identifier,
                    "memory_bytes": host.get("Memory"),
                    "nano_cpus": host.get("NanoCpus"),
                    "pids_limit": host.get("PidsLimit"),
                    "privileged": host.get("Privileged"),
                    "security_options": host.get("SecurityOpt"),
                    "network_mode": host.get("NetworkMode"),
                    "binds": host.get("Binds"),
                    "label_sandbox_id": (attrs.get("Config", {}).get("Labels") or {}).get(SANDBOX_LABEL),
                    "mounts": [
                        {"type": m.get("Type"), "name": m.get("Name"),
                         "destination": m.get("Destination"), "rw": m.get("RW")}
                        for m in attrs.get("Mounts", [])
                    ],
                    "cap_drop": host.get("CapDrop"),
                }
                break
            if inspected is not None:
                break
            time.sleep(0.15)
    finally:
        thread.join(timeout=40)
    if thread.is_alive():
        raise AssertionError("Sandbox resource fixture failed to terminate")
    if errors:
        raise AssertionError("Sandbox resource fixture failed: " + "; ".join(errors))
    result = captured.get("response")
    if not result or result["exit_code"] != 0 or "MERLIN_RESOURCE_FIXTURE" not in result["stdout"]:
        raise AssertionError("Sandbox resource fixture failed")
    if inspected is None:
        raise AssertionError("Could not independently inspect a running sandbox container")
    if not (0 < inspected["memory_bytes"] <= MEMORY_LIMIT_BYTES):
        raise AssertionError("Runtime memory limit missing or exceeds 512 MiB")
    if inspected["privileged"] is not False:
        raise AssertionError("Main sandbox container is privileged")
    inspected["managed_runtime_volume"] = validate_runtime_mounts(inspected)
    if inspected["nano_cpus"] != 1000000000:
        raise AssertionError("Main sandbox must enforce exactly one CPU")
    if not isinstance(inspected["security_options"], list) or not any(
        opt.lower().startswith("no-new-privileges") for opt in inspected["security_options"]
    ):
        raise AssertionError("Main sandbox must prohibit privilege escalation")
    drops = {str(x).upper().removeprefix("CAP_") for x in (inspected.get("cap_drop") or [])}
    if not {"NET_ADMIN", "NET_RAW", "SYS_ADMIN"}.issubset(drops):
        raise AssertionError("Main sandbox is missing required dropped capabilities")
    if not str(inspected["network_mode"]).startswith("container:"):
        raise AssertionError("Main sandbox must use the protected egress sidecar namespace")
    if inspected["pids_limit"] is None or not 0 < inspected["pids_limit"] <= 128:
        raise AssertionError("Runtime PID limit is missing or too high")
    inspected["sandbox_id"] = result["sandbox_id"]
    inspected["script_sha256"] = result["script_sha256"]
    # No reliance on the test script's own statement about resource limits.
    confirm_absent(result["sandbox_id"])
    return inspected


def assert_timeout_bounded(image, prior):
    source = b"import time\ntime.sleep(120)\n"
    before = time.monotonic()
    caught = None
    response = None
    try:
        response = run_source(source, image=image, timeout=2)
    except Exception as exc:
        caught = type(exc).__name__
    elapsed = time.monotonic() - before
    if elapsed >= 50:
        raise AssertionError("Native sandbox timed task exceeded wall-time acceptance")
    if response is not None and response["exit_code"] == 0:
        raise AssertionError("120-second sleep completed under a 2-second command budget")
    if all_managed_containers() - prior or runtime_volumes():
        raise AssertionError("Timeout left a managed container or runtime volume behind")
    return {"elapsed_s": round(elapsed, 2), "timeout_enforced": True,
            "outcome": caught if caught else response["termination"]}


def main():
    parser = argparse.ArgumentParser(description="Native Docker-backed Merlin isolation acceptance")
    parser.add_argument("--image", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    baseline = all_managed_containers()
    if baseline or runtime_volumes():
        raise AssertionError("CI runner must start without preexisting managed sandboxes or volumes")
    image = args.image
    if "@sha256:" not in image:
        raise AssertionError("Container image must be an immutable OCI digest")
    canary = ThreadingHTTPServer(("0.0.0.0", 0), CanaryHandler)
    thread = threading.Thread(target=canary.serve_forever, daemon=True)
    thread.start()
    started = time.monotonic()
    receipt = {"schema": "merlin-native-sandbox-acceptance/1",
               "utc": datetime.now(timezone.utc).isoformat(),
               "image": image,
               "execution_kind": "native_docker_opensandbox",
               "checks": {}, "complete": False}
    try:
        gateway = gateway_address()
        url = "http://" + gateway + ":" + str(canary.server_port) + "/canary"
        receipt["checks"]["positive_control"] = assert_reachable_from_regular_container(image, url)
        receipt["checks"]["network_deny"] = assert_network_denied(image, url, CanaryHandler)
        receipt["checks"]["resource_inspection"] = inspect_running_container(image, baseline)
        receipt["checks"]["timeout_cleanup"] = assert_timeout_bounded(image, baseline)
        if all_managed_containers() != baseline or runtime_volumes():
            raise AssertionError("Managed container/volume set differs from initial baseline")
        receipt["complete"] = True
    finally:
        receipt["elapsed_s"] = round(time.monotonic() - started, 2)
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        canary.shutdown()
        canary.server_close()
        thread.join(timeout=5)
    if receipt["complete"]:
        print(json.dumps({"native_sandbox_acceptance": "pass",
                          "checks": sorted(receipt["checks"]),
                          "elapsed_s": receipt["elapsed_s"]}, sort_keys=True))


if __name__ == "__main__":
    main()
