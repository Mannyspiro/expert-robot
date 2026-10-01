#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "scripts" / "run_collared.sh").read_text(encoding="utf-8")

required = [
    "--key-file",
    "/dev/shm/",
    "systemd-detect-virt",
    "@sha256:",
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
print("collar runtime contract: PASS")
