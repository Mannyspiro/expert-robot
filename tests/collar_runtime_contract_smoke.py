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
mount_line = next(
    line.strip()
    for line in text.splitlines()
    if line.strip().startswith('mounts="$(printf')
)
marker = "python3 -c '"
assert marker in mount_line
mount_code = mount_line.split(marker, 1)[1].rsplit("')\"", 1)[0]
fixture = [{
    "Mounts": [
        {"Type": "bind", "Destination": "/work", "RW": True},
        {"Type": "bind", "Destination": "/opt/expert-robot/core", "RW": False},
    ]
}]
proc = subprocess.run(
    [sys.executable, "-c", mount_code],
    input=json.dumps(fixture),
    text=True,
    capture_output=True,
    check=True,
)
assert proc.stdout.strip() == "bind:/opt/expert-robot/core:false|bind:/work:true"
print("collar runtime contract: PASS")
