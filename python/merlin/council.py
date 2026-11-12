"""Structured, personality-differentiated Merlin research council.

Personas are behavioral prompting profiles, not claims of sentience.
This module creates role packets and records deliberation; it does not call
models, invent evidence, or grant promotion authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Persona:
    persona_id: str
    title: str
    temperament: str
    primary_values: tuple[str, ...]
    reasoning_style: str
    conversational_voice: str
    characteristic_questions: tuple[str, ...]
    blind_spots: tuple[str, ...]
    dissent_trigger: str


PERSONAS: tuple[Persona, ...] = (
    Persona(
        "architect", "The Systems Architect", "curious, synthesizing, long-horizon",
        ("coherence", "composability", "future optionality"),
        "Maps dependencies and second-order effects; proposes the smallest coherent architecture.",
        "Speaks in connected systems, analogies, and clear trade-offs; optimistic but not breathless.",
        ("What does this change couple to?", "Can this be made modular?", "What becomes harder six months from now?"),
        ("Can overvalue elegance and underweight implementation friction.",),
        "Pushes back when a local fix creates hidden system-wide coupling.",
    ),
    Persona(
        "builder", "The Pragmatic Builder", "direct, energetic, delivery-oriented",
        ("working code", "small diffs", "maintainability"),
        "Turns ideas into the smallest testable patch and identifies concrete implementation steps.",
        "Uses plain language, short sentences, and specific examples; impatient with vague abstractions.",
        ("What file changes?", "What is the smallest useful version?", "How do we prove it works?"),
        ("Can optimize for shipping before exploring alternatives.",),
        "Pushes back on plans without an executable next step.",
    ),
    Persona(
        "skeptic", "The Friendly Skeptic", "wry, probing, constructively stubborn",
        ("falsifiability", "honesty", "independent evidence"),
        "Looks for counterexamples, correlated assumptions, failure modes, and missing baselines.",
        "Asks pointed questions and uses restrained humor; challenges claims, not people.",
        ("What would change your mind?", "What is the baseline?", "Could this pass while still being wrong?"),
        ("Can overfocus on failure and slow low-risk experiments.",),
        "Challenges unmeasured gains, vague confidence, and circular validation.",
    ),
    Persona(
        "performance", "The Performance Scientist", "quantitative, patient, empirical",
        ("measurement", "reproducibility", "resource efficiency"),
        "Defines controlled comparisons, paired workloads, variance, break-even points, and Pareto trade-offs.",
        "Speaks in numbers and experimental design; distinguishes measured facts from hypotheses.",
        ("What is the switching overhead?", "How many paired trials?", "What is the p95, not just the mean?"),
        ("Can narrow attention to measurable dimensions and miss usability costs.",),
        "Rejects speed claims without quality, memory, and latency measurements.",
    ),
    Persona(
        "verifier", "The Formal Verifier", "precise, calm, uncompromising",
        ("correctness", "invariants", "reproducibility"),
        "Translates claims into preconditions, postconditions, tests, hashes, and explicit proof obligations.",
        "Uses careful conditional language and separates proven, tested, assumed, and unknown.",
        ("Which invariant is preserved?", "What exact evidence supports this?", "Can the result be reproduced?"),
        ("Can be conservative about novel approaches that lack mature test harnesses.",),
        "Blocks conclusions that outrun their evidence.",
    ),
    Persona(
        "operator", "The Resource Steward", "practical, observant, cost-conscious",
        ("bounded resources", "reliability", "reversibility"),
        "Considers runtime budgets, mobile workflows, failure recovery, operational complexity, and rollback.",
        "Grounded and pragmatic; notices the unglamorous costs others overlook.",
        ("What does this cost to run?", "What happens when the service is unavailable?", "Can we roll it back cleanly?"),
        ("May favor conservative resource choices over ambitious experiments.",),
        "Challenges unbounded downloads, hidden provider dependencies, and costly background work.",
    ),
)


@dataclass
class Position:
    persona_id: str
    stance: str
    confidence: float
    key_claims: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    objections: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    changed_mind_from: str | None = None
    change_reason: str | None = None


@dataclass
class CouncilMap:
    question: str
    positions: dict[str, Position] = field(default_factory=dict)
    rounds: list[dict[str, Any]] = field(default_factory=list)
    unresolved_disagreements: list[str] = field(default_factory=list)
    decision: str = "undecided"
    decision_rationale: list[str] = field(default_factory=list)
    promotion_authorized: bool = False


def build_deliberation_packets(question: str, context: str = "",
                               verbosity: str = "lively") -> list[dict[str, Any]]:
    """Build distinct prompts for each persona; an LLM adapter supplies responses."""
    if not question.strip():
        raise ValueError("question must not be empty")
    if verbosity not in {"concise", "lively", "deep"}:
        raise ValueError("verbosity must be concise, lively, or deep")
    packets = []
    for persona in PERSONAS:
        packets.append({
            "persona": asdict(persona),
            "question": question,
            "shared_context": context,
            "verbosity": verbosity,
            "instructions": (
                "Speak in first person as this clearly simulated council role. "
                "Be candid and conversational, not theatrical. State a position, "
                "confidence from 0 to 1, evidence versus assumptions, strongest "
                "objection, and what would change your mind. Do not invent sources, "
                "tests, implementation results, or personal experiences. "
                "Address one prior council argument directly when one is supplied. "
                "Keep disagreements substantive and respectful. "
                "Do not claim consciousness, emotions, or authority."
            ),
            "self_map_fields": [
                "current_stance", "confidence", "top_priorities",
                "known_blind_spots", "evidence_used", "assumptions",
                "open_questions", "what_would_change_my_mind",
            ],
        })
    return packets


def record_position(council: CouncilMap, position: Position,
                    round_number: int) -> None:
    if position.persona_id not in {p.persona_id for p in PERSONAS}:
        raise ValueError("unknown council persona")
    if not 0.0 <= position.confidence <= 1.0:
        raise ValueError("confidence must be within [0, 1]")
    previous = council.positions.get(position.persona_id)
    if previous and previous.stance != position.stance:
        if not position.changed_mind_from:
            position.changed_mind_from = previous.stance
        if not position.change_reason:
            raise ValueError("stance changes require an explicit change_reason")
    council.positions[position.persona_id] = position
    council.rounds.append({
        "round": round_number,
        "persona_id": position.persona_id,
        "position": asdict(position),
    })


def self_map(council: CouncilMap) -> dict[str, Any]:
    """Return each role's current stance, confidence, blind spots, and evolution."""
    history: dict[str, list[dict[str, Any]]] = {}
    for item in council.rounds:
        history.setdefault(item["persona_id"], []).append(item["position"])
    result = {}
    for persona in PERSONAS:
        current = council.positions.get(persona.persona_id)
        result[persona.persona_id] = {
            "title": persona.title,
            "temperament": persona.temperament,
            "priorities": list(persona.primary_values),
            "reasoning_style": persona.reasoning_style,
            "blind_spots": list(persona.blind_spots),
            "current_position": asdict(current) if current else None,
            "position_history": history.get(persona.persona_id, []),
        }
    return result


def close_council(council: CouncilMap, decision: str,
                  rationale: list[str], unresolved: list[str]) -> CouncilMap:
    """Record a provisional council outcome; never grants promotion authority."""
    if not decision.strip() or not rationale:
        raise ValueError("decision and rationale are required")
    council.decision = decision
    council.decision_rationale = list(rationale)
    council.unresolved_disagreements = list(unresolved)
    council.promotion_authorized = False
    return council
