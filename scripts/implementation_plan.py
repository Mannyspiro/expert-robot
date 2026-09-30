#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config" / "implementation_plan.json"


def main() -> int:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    phases = plan["phases"]
    by_id = {p["id"]: p for p in phases}

    complete_states = {"complete", "implemented", "verified", "rsi_ready"}

    def complete(phase_id: str) -> bool:
        return by_id[phase_id].get("status") in complete_states

    candidates = []
    for phase in sorted(phases, key=lambda p: p["rank"]):
        status = phase.get("status", "planned")
        if status in complete_states:
            continue
        requires = phase.get("requires", [])
        unmet = [req for req in requires if not complete(req)]
        if unmet:
            continue
        candidates.append(phase)

    result = {
        "schema_version": 1,
        "stop_condition": plan["stop_condition"],
        "rsi_start_allowed": False,
        "all_complete": not candidates,
        "next": candidates[0] if candidates else None,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
