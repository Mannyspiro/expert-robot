"""Bounded synthetic security research tasks for Merlin; no execution authority."""
from dataclasses import dataclass
from hashlib import sha256
from .security_triage import triage

HYPOTHESES = {
    "integrity_failure": ("A corrupted synthetic case is rejected before returning data.",
                          "Mutate a demo case history and assert fail-closed read."),
    "provenance_rejected": ("Cross-environment demo imports are rejected.",
                            "Try a mislabeled synthetic fixture and assert rejection."),
    "unexpected_tool": ("Unlisted tool names cannot invoke business operations.",
                         "Submit a forbidden tool name and assert denial."),
    "auth_failure": ("Missing credentials cannot access demo API results.",
                      "Request a protected demo endpoint without a token."),
    "tool_denied": ("Insufficient scopes prevent a demo business read.",
                    "Attempt a read with an identity lacking cases:read."),
    "rate_limit": ("A future gateway rejects requests over a bounded rate.",
                    "Implement and test a deterministic synthetic rate-limit fixture."),
}

@dataclass(frozen=True)
class ResearchTask:
    task_id: str
    finding_kind: str
    priority: str
    hypothesis: str
    falsification_test: str
    requires_independent_review: bool = True
    environment: str = "demo"
    data_class: str = "synthetic"

def build_research_queue(summary, *, max_tasks=3):
    if type(max_tasks) is not int or not 1 <= max_tasks <= 6:
        raise ValueError("invalid research budget")
    findings = triage(summary,max_findings=max_tasks)
    tasks = []
    for finding in findings:
        hypothesis, test = HYPOTHESES[finding.kind]
        identifier = sha256(("wilborn-demo-research-v1:"+finding.kind).encode()).hexdigest()[:16]
        tasks.append(ResearchTask("wilborn-"+identifier,finding.kind,finding.priority,
                                  hypothesis,test))
    return tasks
