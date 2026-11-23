"""Passive, privacy-preserving security-event classifier for synthetic testing.

Not Artex. No autonomous remediation, secret access, network scanning, or LLM calls.
"""
from dataclasses import dataclass
from collections import Counter

KINDS = frozenset({
    "auth_failure", "tool_denied", "provenance_rejected",
    "rate_limit", "integrity_failure", "unexpected_tool",
})
SEVERITY = {
    "auth_failure": "medium",
    "tool_denied": "medium",
    "provenance_rejected": "high",
    "rate_limit": "medium",
    "integrity_failure": "high",
    "unexpected_tool": "high",
}

@dataclass(frozen=True)
class SecurityEvent:
    kind: str
    environment: str
    data_class: str
    # Never accept raw prompts, credentials, IPs, client names or payloads.
    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError("unrecognized event")
        if self.environment != "demo" or self.data_class != "synthetic":
            raise PermissionError("monitor is synthetic-demo only")

class SecurityMonitor:
    def __init__(self):
        self._counts = Counter()

    def observe(self, event):
        if not isinstance(event, SecurityEvent):
            raise TypeError("typed event required")
        self._counts[event.kind] += 1
        return {"kind": event.kind, "severity": SEVERITY[event.kind],
                "data_class": "synthetic", "environment": "demo",
                "requires_review": event.kind in
                {"provenance_rejected", "integrity_failure", "unexpected_tool"}}

    def summary(self):
        return {"environment": "demo", "data_class": "synthetic",
                "counts": {kind: self._counts[kind] for kind in sorted(self._counts)}}
