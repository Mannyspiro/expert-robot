"""Explicit, monotonic Merlin research lifecycle contracts."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping

STAGES = (
    "hypothesis", "literature_evidence", "experiment",
    "counterexample_search", "formalization", "independent_verification",
)
_ALLOWED = {stage: STAGES[i + 1] for i, stage in enumerate(STAGES[:-1])}


@dataclass(frozen=True)
class StageEvidence:
    stage: str
    artifact_sha256: str
    source_ids: tuple[str, ...]
    repository_commit: str
    tool_name: str
    tool_version: str
    status: str


@dataclass(frozen=True)
class ResearchLifecycle:
    hypothesis_id: str
    current_stage: str = "hypothesis"
    evidence: tuple[StageEvidence, ...] = ()
    terminal_status: str = "active"

    def advance(self, evidence: StageEvidence) -> "ResearchLifecycle":
        expected = _ALLOWED.get(self.current_stage)
        if self.terminal_status != "active":
            raise ValueError("terminal research lifecycle cannot advance")
        if expected is None or evidence.stage != expected:
            raise ValueError("research lifecycle stage transition is out of order")
        if len(evidence.artifact_sha256) != 64 or any(c not in "0123456789abcdef" for c in evidence.artifact_sha256):
            raise ValueError("evidence must bind a lowercase SHA-256 artifact digest")
        if not evidence.source_ids or not all(isinstance(x, str) and x.strip() for x in evidence.source_ids):
            raise ValueError("evidence must identify at least one source")
        if not evidence.repository_commit or not evidence.tool_name or not evidence.tool_version:
            raise ValueError("commit, tool name and tool version are mandatory provenance")
        if evidence.status not in {"recorded", "completed", "compiled", "verified", "rejected", "blocked"}:
            raise ValueError("unsupported evidence status")
        if evidence.stage == "independent_verification" and evidence.status != "verified":
            return ResearchLifecycle(self.hypothesis_id, evidence.stage, self.evidence + (evidence,), "verification_blocked")
        if evidence.stage == "formalization" and evidence.status != "compiled":
            raise ValueError("formalization stage must carry a compiled Lean result")
        if evidence.stage == "independent_verification" and evidence.status == "verified":
            return ResearchLifecycle(self.hypothesis_id, evidence.stage, self.evidence + (evidence,), "independently_verified")
        return ResearchLifecycle(self.hypothesis_id, evidence.stage, self.evidence + (evidence,), "active")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "merlin-research-lifecycle/1",
            "hypothesis_id": self.hypothesis_id,
            "current_stage": self.current_stage,
            "terminal_status": self.terminal_status,
            "evidence": [asdict(item) for item in self.evidence],
            "promotion_authority": False,
        }


__all__ = ["STAGES", "StageEvidence", "ResearchLifecycle"]
