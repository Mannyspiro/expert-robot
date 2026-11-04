"""Validated Lean/Avrea proof receipts for Merlin's evidence-gated hypothesis ledger.

This module validates a CI-produced receipt's structure and qualification claims.
It does not call GitHub, compile Lean, or independently authenticate a workflow run.
The receipt must be produced by a trusted CI workflow; its run URL and source hash
are retained as provenance for later review.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re

from merlin.hypothesis_ledger import Evidence, HypothesisLedger

_ALLOWED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUN_PATH = re.compile(r"^https://github\.com/[^/]+/[^/]+/actions/runs/[1-9][0-9]*$")


@dataclass(frozen=True)
class LeanProofReceipt:
    repository: str
    commit_sha: str
    workflow_run_id: int
    workflow_run_url: str
    workflow_name: str
    conclusion: str
    theorem: str
    theorem_compiled: bool
    axiom_audit_passed: bool
    axioms: tuple[str, ...]
    source_sha256: str

    @classmethod
    def from_mapping(cls, payload: dict) -> "LeanProofReceipt":
        try:
            return cls(
                repository=str(payload["repository"]),
                commit_sha=str(payload["commit_sha"]),
                workflow_run_id=int(payload["workflow_run_id"]),
                workflow_run_url=str(payload["workflow_run_url"]),
                workflow_name=str(payload["workflow_name"]),
                conclusion=str(payload["conclusion"]),
                theorem=str(payload["theorem"]),
                theorem_compiled=payload["theorem_compiled"] is True,
                axiom_audit_passed=payload["axiom_audit_passed"] is True,
                axioms=tuple(str(item) for item in payload["axioms"]),
                source_sha256=str(payload["source_sha256"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("malformed Lean proof receipt") from exc

    def validate(self) -> None:
        if not self.repository or "/" not in self.repository:
            raise ValueError("repository must be owner/name")
        if not _SHA40.fullmatch(self.commit_sha):
            raise ValueError("commit_sha must be a lowercase 40-character Git SHA")
        if self.workflow_run_id <= 0:
            raise ValueError("workflow_run_id must be positive")
        if not _RUN_PATH.fullmatch(self.workflow_run_url):
            raise ValueError("workflow_run_url must be a GitHub Actions run URL")
        expected_url = f"https://github.com/{self.repository}/actions/runs/{self.workflow_run_id}"
        if self.workflow_run_url != expected_url:
            raise ValueError("workflow_run_url does not match repository and workflow_run_id")
        if not self.workflow_name.strip() or not self.theorem.strip():
            raise ValueError("workflow_name and theorem must be non-empty")
        if self.conclusion != "success":
            raise ValueError("only successful workflow runs can provide proof evidence")
        if not self.theorem_compiled:
            raise ValueError("the theorem must have compiled successfully")
        if not self.axiom_audit_passed:
            raise ValueError("the theorem's axiom audit must have passed")
        if not _SHA256.fullmatch(self.source_sha256):
            raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
        if len(set(self.axioms)) != len(self.axioms):
            raise ValueError("axiom list must not contain duplicates")
        unknown = set(self.axioms) - _ALLOWED_AXIOMS
        if unknown:
            raise ValueError(f"unapproved axiom dependencies: {sorted(unknown)}")

    def digest(self) -> str:
        payload = asdict(self)
        payload["axioms"] = sorted(self.axioms)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_lean_proof(
    ledger: HypothesisLedger,
    hypothesis_id: str,
    receipt: LeanProofReceipt,
) -> Evidence:
    """Record a validated proof receipt; deliberately does not promote status."""
    receipt.validate()
    description = (
        f"Lean theorem {receipt.theorem} compiled and axiom-audited in "
        f"{receipt.workflow_name} run {receipt.workflow_run_id} on commit "
        f"{receipt.commit_sha}; source SHA-256 {receipt.source_sha256}; "
        f"axioms: {', '.join(sorted(receipt.axioms)) or '(none)'}."
    )
    return ledger.add_evidence(
        hypothesis_id,
        "proof",
        description,
        source_url=receipt.workflow_run_url,
        artifact_hash=receipt.digest(),
    )
