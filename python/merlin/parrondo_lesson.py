"""Canonical zero-first Parrondo lesson, shared by all three learning paths."""
from __future__ import annotations

from .learning_core import DEFAULT_CONCEPTS
from .lesson_schema import LessonBlock, LessonDocument


PARRONDO_LESSON = LessonDocument(
    lesson_id="math.parrondo.zero_first.v1",
    version=1,
    title="Can two losing games make a winning combination?",
    concept_ids=(
        "quantity", "change", "probability", "state", "transition",
        "expected_value", "markov_chain", "stationary_distribution",
    ),
    prerequisites=(),
    path_tags=("mathematician", "mathematics_programmer", "computational_hacker"),
    metadata={
        "design": "concrete-before-symbolic",
        "simulation_engine": "parrondo.v1",
        "epsilon": 0.005,
        "mix_probability": 0.5,
        "starting_tokens": 30,
        "default_turns": 3000,
        "default_trials": 1000,
        "seed_policy": "explicit-and-reproducible",
    },
    blocks=(
        LessonBlock(
            "story", "story",
            {"narration": "Two games each tend to lose over many turns. Could randomly mixing them make the long-run average grow?",
             "prompt": "Does that sound impossible, or could the way we combine the games matter?"},
        ),
        LessonBlock(
            "tokens", "manipulative",
            {"initial_tokens": 30, "actions": ["play_A", "play_B", "choose_randomly"],
             "visual_state_track": 3, "state_label": "three-position remainder track",
             "hide_numeric_rules_until_prediction": True},
        ),
        LessonBlock(
            "predict", "choice",
            {"prompt": "Which strategy do you predict will have the highest long-run average?",
             "options": ["Game A only", "Game B only", "Choose randomly between A and B"],
             "capture_confidence": True, "capture_explanation": True},
        ),
        LessonBlock(
            "experiment", "simulation",
            {"engine": "parrondo.v1",
             "parameters": {"epsilon": 0.005, "mix_probability": 0.5,
                            "start": 30, "turns": 3000, "trials": 1000,
                            "game_A_base_win_probability": 0.5,
                            "game_B_base_win_probability_by_remainder": [0.1, 0.75, 0.75]},
             "seed": 20261111, "compare": ["A", "B", "mixed"],
             "show_individual_runs": True, "show_aggregate_distribution": True},
        ),
        LessonBlock(
            "outcomes", "chart",
            {"series": [{"name": "A only", "source": "simulation.A"},
                        {"name": "B only", "source": "simulation.B"},
                        {"name": "random mixture", "source": "simulation.mixed"}],
             "metrics": ["mean_change", "sample_standard_deviation",
                         "fraction_profitable", "confidence_interval"],
             "show_uncertainty": True,
             "accessible_description": "Compare individual paths and distributions of ending balances."},
        ),
        LessonBlock(
            "mechanism", "explanation",
            {"text": "Game B depends on the current remainder state. The two games move between states differently. Mixing changes how often each state occurs, changing the long-run weighted average.",
             "glossary": ["remainder", "state", "probability", "expected change"],
             "progressive_disclosure": True},
        ),
        LessonBlock(
            "formal-model", "explanation",
            {"text": "Now represent the three remainder states as a Markov chain. Derive its transition matrix and stationary distribution, then calculate the expected gain per turn.",
             "notation": ["modular arithmetic", "transition matrix", "stationary distribution", "expected value"],
             "path_extensions": {
                 "mathematician": "Derive and justify the stationary distribution.",
                 "mathematics_programmer": "Implement the simulator and compare it with the analytic model.",
                 "computational_hacker": "Probe random seeds, state encodings, and sampling error."
             }},
            introduces_symbols=True,
        ),
        LessonBlock(
            "reflection", "reflection",
            {"prompt": "Explain in your own words why mixing the games changes the long-run result.",
             "capture_confidence": True, "accept_audio_or_text": True},
        ),
        LessonBlock(
            "retrieval", "retrieval",
            {"prompt": "Without using equations, explain what makes Game B state-dependent.",
             "concept_ids": ["state", "probability", "expected_value"],
             "initial_intervals_days": [0, 1, 3, 7, 14, 30]},
        ),
        LessonBlock(
            "assessment", "assessment",
            {"rubric_dimensions": ["conceptual", "representational", "transfer", "proof", "retention"],
             "mastery_requires_multiple_evidence_types": True,
             "exposure_alone_is_not_mastery": True},
        ),
    ),
)

DEFAULT_CONCEPTS.validate()
PARRONDO_LESSON.validate([concept.concept_id for concept in DEFAULT_CONCEPTS.all()])
