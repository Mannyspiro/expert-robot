"""Deterministic council orchestration contracts for Merlin.

This module models research roles and simulated compute/physics environments.
It does not pretend to emulate neural hardware or execute an LLM. Real model
adapters must implement the protocol and return attributable outputs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Protocol


class EvidenceClass(str, Enum):
    HYPOTHESIS = "hypothesis"
    LITERATURE = "literature"
    NUMERICAL = "numerical"
    EXPERIMENTAL = "experimental"
    FORMAL = "formal"
    INDEPENDENT_REVIEW = "independent_review"


@dataclass(frozen=True)
class CouncilRole:
    role_id: str
    mandate: str
    default_model: str | None = None
    must_challenge: bool = False


DEFAULT_COUNCIL = (
    CouncilRole("chair", "Frame the question, allocate work, synthesize without erasing disagreement."),
    CouncilRole("mathematician", "Derive definitions, equations, assumptions and proof obligations."),
    CouncilRole("physicist", "Check dimensional consistency, boundary conditions and physical interpretation."),
    CouncilRole("engineer", "Translate results into implementable CAD, wiring, materials and test requirements."),
    CouncilRole("coder", "Implement reproducible prototypes, tests and machine-readable artifacts."),
    CouncilRole("skeptic", "Search for counterexamples, hidden assumptions and alternative explanations.", must_challenge=True),
    CouncilRole("librarian", "Find public sources, standards metadata, provenance and contradictory evidence."),
)


@dataclass(frozen=True)
class PhysicsEnvironment:
    environment_id: str
    description: str
    model_family: str
    assumptions: tuple[str, ...] = ()
    parameters: dict[str, float] = field(default_factory=dict)
    evidence_ceiling: str = "simulation_only"
    def validate(self) -> None:
        if not self.environment_id.strip() or not self.model_family.strip():
            raise ValueError("environment identity and model family are required")
        for key, value in self.parameters.items():
            if not key.strip() or not isinstance(value, (int, float)) or not __import__("math").isfinite(value):
                raise ValueError("environment parameters must be finite numbers with names")


DEFAULT_ENVIRONMENTS = (
    PhysicsEnvironment("classical_mechanics", "Newtonian rigid-body and constrained dynamics", "ode_dae"),
    PhysicsEnvironment("electromagnetics", "Maxwell field models with declared constitutive laws", "pde_fem_fvm"),
    PhysicsEnvironment("thermal", "Heat transfer and lumped/distributed thermal models", "ode_pde"),
    PhysicsEnvironment("quantum", "Explicitly scoped quantum state and operator models", "linear_operator"),
    PhysicsEnvironment("relativistic", "Lorentzian spacetime geometry and relativistic field models", "tensor_pde"),
    PhysicsEnvironment("fluid", "Continuum fluid mechanics with declared closures", "pde_cfd"),
    PhysicsEnvironment("materials", "Constitutive and multiscale materials models", "constitutive_multiscale"),
    PhysicsEnvironment("abstract", "User-defined axiomatic or synthetic mathematical environment", "axiomatic"),
)


@dataclass(frozen=True)
class CouncilContribution:
    role_id: str
    content: str
    evidence_class: EvidenceClass
    source_refs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    confidence: float | None = None
    def __post_init__(self):
        if not self.role_id.strip() or not self.content.strip():
            raise ValueError("contribution requires role and content")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between zero and one")


@dataclass(frozen=True)
class CouncilSession:
    question: str
    environment: PhysicsEnvironment
    contributions: tuple[CouncilContribution, ...]
    session_id: str = ""
    status: str = "RESEARCH_ONLY_NOT_APPROVED"
    def canonical_receipt(self) -> dict[str, Any]:
        body = {
            "question": self.question,
            "environment": asdict(self.environment),
            "contributions": [
                {**asdict(c), "evidence_class": c.evidence_class.value}
                for c in self.contributions
            ],
            "status": self.status,
        }
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {"format": "merlin-council-session-v1", "sha256": digest, **body}


class CouncilAgent(Protocol):
    role: CouncilRole
    def contribute(self, question: str, environment: PhysicsEnvironment,
                   context: tuple[CouncilContribution, ...]) -> CouncilContribution: ...


def run_council(question: str, environment: PhysicsEnvironment,
                agents: tuple[CouncilAgent, ...], rounds: int = 1) -> CouncilSession:
    """Run explicitly supplied adapters in deterministic role order.

    No model is silently selected or called. Adapters are invoked serially so
    the skeptic can inspect prior contributions and challenge them.
    """
    if not question.strip():
        raise ValueError("research question cannot be empty")
    if rounds < 1 or rounds > 5:
        raise ValueError("rounds must be between one and five")
    environment.validate()
    contributions: list[CouncilContribution] = []
    ordered = sorted(agents, key=lambda a: a.role.role_id)
    if len({a.role.role_id for a in ordered}) != len(ordered):
        raise ValueError("council role IDs must be unique")
    for _ in range(rounds):
        for agent in ordered:
            result = agent.contribute(question, environment, tuple(contributions))
            if result.role_id != agent.role.role_id:
                raise ValueError("adapter returned a contribution for another role")
            contributions.append(result)
    return CouncilSession(question, environment, tuple(contributions))


def virtual_chip_budget(cores: int, memory_bytes: int, bandwidth_bytes_s: float,
                        power_w: float | None = None) -> dict[str, Any]:
    """Describe a virtual compute budget; this is not transistor-level simulation."""
    if cores < 1 or memory_bytes < 1 or bandwidth_bytes_s <= 0:
        raise ValueError("cores, memory and bandwidth must be positive")
    if power_w is not None and power_w <= 0:
        raise ValueError("power_w must be positive when supplied")
    return {
        "model": "abstract_resource_budget_v1",
        "cores": cores,
        "memory_bytes": memory_bytes,
        "bandwidth_bytes_s": bandwidth_bytes_s,
        "power_w": power_w,
        "evidence_ceiling": "resource_estimate_not_chip_physics",
    }
