"""Deterministic, synthetic-only security triage for Merlin's review queue.

No live scanning, LLM inference, production actions, or automated remediation.
"""
from dataclasses import dataclass
from .security_monitor import KINDS

@dataclass(frozen=True)
class Finding:
    kind: str
    count: int
    priority: str
    recommendation: str
    environment: str = "demo"
    data_class: str = "synthetic"

RECOMMENDATIONS = {
    "integrity_failure": ("critical", "Investigate integrity failure; preserve evidence and test recovery."),
    "provenance_rejected": ("high", "Review synthetic-data ingestion boundaries and regression tests."),
    "unexpected_tool": ("high", "Review tool allowlist and prompt/tool-injection fixtures."),
    "auth_failure": ("medium", "Review authentication failure trends using redacted metadata."),
    "tool_denied": ("medium", "Review authorization denials and test expected policy behavior."),
    "rate_limit": ("medium", "Review rate-limit thresholds and synthetic load tests."),
    "artex_guard_marker": ("high", "Review passive runtime audit lead; do not infer compromise."),
    "artex_recording_ca": ("medium", "Review authorized proxy configuration and provenance."),
    "artex_update_indicator": ("medium", "Review approved software inventory and egress policy."),
    "artex_inbound_indicator": ("high", "Review passive inbound indicator with independent evidence."),
}
if set(RECOMMENDATIONS)!=KINDS:
    raise RuntimeError("triage coverage must match typed event kinds")
ORDER = {"critical": 0, "high": 1, "medium": 2}

def triage(summary, *, max_findings=6):
    if not isinstance(summary, dict) or summary.get("environment") != "demo" or summary.get("data_class") != "synthetic":
        raise PermissionError("synthetic demo summary required")
    counts = summary.get("counts")
    if not isinstance(counts, dict) or set(counts) - KINDS:
        raise ValueError("invalid event summary")
    if type(max_findings) is not int or not 1 <= max_findings <= 6:
        raise ValueError("invalid review budget")
    findings = []
    for kind, count in counts.items():
        if type(count) is not int or count < 0:
            raise ValueError("invalid event count")
        if count:
            priority, recommendation = RECOMMENDATIONS[kind]
            findings.append(Finding(kind, count, priority, recommendation))
    findings.sort(key=lambda item: (ORDER[item.priority], -item.count, item.kind))
    return findings[:max_findings]
