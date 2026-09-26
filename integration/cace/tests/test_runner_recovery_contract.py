#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "integration" / "cace" / "scripts" / "recover_cace_runner.sh"


def main() -> int:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "mode=status" in text
    assert '--repair' in text
    assert 'registration_required' in text
    assert 'repository_mutation' in text
    assert 'instance_lifecycle_mutation' in text
    assert '"repository_mutation": False' in text
    assert '"instance_lifecycle_mutation": False' in text

    for root in (
        "/opt/actions-runner",
        "/home/morganaspi/actions-runner",
        "/home/github-runner/actions-runner",
    ):
        assert root in text

    assert "systemctl restart" in text
    assert "cace-runner-watchdog.service" in text
    assert "./svc.sh install" in text

    forbidden = (
        "oci compute instance action",
        "oci compute instance launch",
        "actions/runners/registration-token",
        "config.sh --unattended",
        "curl ",
        "wget ",
        "git push",
        "git clone",
        "0.0.0.0",
    )
    for marker in forbidden:
        assert marker not in text, f"forbidden recovery capability: {marker}"

    print("CACE runner recovery contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
