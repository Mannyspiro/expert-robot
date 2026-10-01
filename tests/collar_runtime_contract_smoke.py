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
    "scripts/validate_docker_mounts.py",
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

validator = ROOT / "scripts" / "validate_docker_mounts.py"

base_mounts = [
    {"Type": "bind", "Source": "/trusted/core", "Destination": "/opt/expert-robot/core", "RW": False},
    {"Type": "bind", "Source": "/trusted/work", "Destination": "/work", "RW": True},
    {"Type": "tmpfs", "Source": "", "Destination": "/tmp", "RW": True},
    {"Type": "tmpfs", "Source": "", "Destination": "/run/expert-robot", "RW": True},
    {"Type": "bind", "Source": "/docker/hosts", "Destination": "/etc/hosts", "RW": True},
    {"Type": "bind", "Source": "/docker/hostname", "Destination": "/etc/hostname", "RW": True},
    {"Type": "bind", "Source": "/docker/resolv.conf", "Destination": "/etc/resolv.conf", "RW": True},
]
host_tmpfs = {
    "/tmp": "rw,noexec,nosuid,nodev,size=512m",
    "/run/expert-robot": "rw,noexec,nosuid,nodev,size=64m",
}

def validate(mounts, tmpfs=host_tmpfs, expect_ok=True):
    fixture = [{"Mounts": mounts, "HostConfig": {"Tmpfs": tmpfs}}]
    proc = subprocess.run(
        [sys.executable, str(validator),
         "--expected-core", "/trusted/core",
         "--expected-workspace", "/trusted/work"],
        input=json.dumps(fixture), text=True, capture_output=True,
    )
    assert (proc.returncode == 0) is expect_ok, proc.stderr
    return proc

validate(base_mounts)
validate(base_mounts + [
    {"Type": "bind", "Source": "/host/secret", "Destination": "/secret", "RW": False}
], expect_ok=False)
validate([
    dict(m, RW=True) if m["Destination"] == "/opt/expert-robot/core" else m
    for m in base_mounts
], expect_ok=False)
validate([
    dict(m, Source="/wrong/core") if m["Destination"] == "/opt/expert-robot/core" else m
    for m in base_mounts
], expect_ok=False)
validate(base_mounts, {"/tmp": host_tmpfs["/tmp"]}, expect_ok=False)

print("collar runtime contract: PASS")
