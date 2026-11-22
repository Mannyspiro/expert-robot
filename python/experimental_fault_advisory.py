"""Deterministic, non-authoritative fault-pattern advisory for Merlin.

Advisories cannot invoke repair or change policy. Evidence remains the source of
truth; predictions are heuristics requiring later measurement.
"""
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class FaultAdvisory:
    subsystem: str
    observed_failures: int
    category: str
    action: str


def summarize_faults(events: list[dict], *, minimum_recurrences: int = 3) -> list[FaultAdvisory]:
    if minimum_recurrences < 2:
        raise ValueError("minimum_recurrences must be at least 2")
    counts = Counter()
    for event in events:
        if not isinstance(event, dict):
            continue
        subsystem = event.get("subsystem")
        state = event.get("state")
        if isinstance(subsystem, str) and subsystem and state in (
            "probe_error", "repair_failed", "rollback_failed", "fault_detected"
        ):
            counts[(subsystem, state)] += 1
    return [
        FaultAdvisory(subsystem, count, state, "investigate_recurrence")
        for (subsystem, state), count in sorted(counts.items())
        if count >= minimum_recurrences
    ]
