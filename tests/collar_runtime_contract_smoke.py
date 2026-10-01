#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_collared.sh"
text = RUNNER.read_text(encoding="utf-8")
assert RUNNER.stat().st_mode & 0o111, "run_collared.sh must remain executable in git checkout"

required = [
    "--key-file",
    "/dev/shm/",
    "systemd-detect-virt",
    "@sha256:",
    "docker image inspect",
    "local container image id is missing or does not match requested sha256",
    "timeout 5s docker inspect",
    "--network none",
    "--read-only",
    "--cap-drop ALL",
    "--security-opt no-new-privileges:true",
    "--pids-limit 128",
    "--memory 8g",
    "--cpus 8",
    "--user 65532:65532",
    "supervisor_canary_tamper",
    "unexpected_host_mount",
    "tmpfs_mount_drift",
    "tmpfs_config_ok",
    "generation key must remain outside candidate-writable workspace",
    "sealed core must remain outside candidate-writable workspace",
    'rm -rf -- "$EVIDENCE"',
    '"promotion_authority": False',
    '"external_policy_may_promote_after_all_gates": True',
    'scripts/collar_vault.sh destroy-key "$KEY"',
]
for needle in required:
    assert needle in text, needle

assert "docker.sock" not in text
assert "--privileged" not in text
assert 'keygen "$KEY"' not in text

# Execute the exact embedded Python used to normalize Docker mount inspection.
# bash -n cannot catch quoting errors inside python3 -c strings.
def embedded_code(prefix: str) -> str:
    line = next(
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith(prefix)
    )
    marker = "python3 -c '"
    assert marker in line
    return line.split(marker, 1)[1].rsplit("')\"", 1)[0]


fixture = [{
    "HostConfig": {
        "Tmpfs": {
            "/tmp": "rw,noexec,nosuid,nodev,size=512m",
            "/run/expert-robot": "rw,noexec,nosuid,nodev,size=64m",
        }
    },
    "Mounts": [
        {"Type": "bind", "Destination": "/work", "RW": True},
        {"Type": "bind", "Destination": "/opt/expert-robot/core", "RW": False},
        {"Type": "tmpfs", "Destination": "/tmp", "RW": True},
        {"Type": "tmpfs", "Destination": "/run/expert-robot", "RW": True},
    ],
}]

def run_embedded(prefix: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", embedded_code(prefix)],
        input=json.dumps(fixture),
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout.strip()


assert run_embedded('host_mounts="$(printf') == (
    "bind:/opt/expert-robot/core:false|bind:/work:true"
)
assert run_embedded('tmpfs_mounts="$(printf') == (
    "/run/expert-robot:true|/tmp:true"
)
assert run_embedded('tmpfs_config_ok="$(printf') == "true"
print("collar runtime contract: PASS")
