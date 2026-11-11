"""Reproducible finite-run experiments for the Parrondo discovery lesson.

Finite trajectories are observations, not proofs of long-run expectation.
The exact stationary calculation remains in parrondo_lesson.py.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import random

from .parrondo_lesson import Game, make_canonical_games
from .learning_core import LessonSession, LessonSpec, LessonStage


PARRONDO_LESSON_SPEC = LessonSpec(
    lesson_id="math.parrondo.discovery.zero_first.v1",
    title="Can two losing games make a winning mixture?",
    target_concepts=("quantity", "change", "rate"),
    prerequisites=(),
    path_tags=("mathematician", "mathematics_programmer", "computational_hacker"),
    priority=1.0,
    stages=(
        LessonStage("notice", "concrete", "Imagine two games that each tend to lose. Could mixing them ever help?"),
        LessonStage("play_a", "interactive", "Play Game A and observe what happens to your running total."),
        LessonStage("play_b", "interactive", "Play Game B. Notice that its coin depends on your position modulo three."),
        LessonStage("mix", "interactive", "Randomly choose A or B each turn. Compare the three experiences."),
        LessonStage("explain_state", "visual", "Explore how the mixture changes the time spent in each position."),
        LessonStage("probabilities", "symbol", "Now introduce probabilities and calculate long-run expected gain.", True),
    ),
)
PARRONDO_LESSON_SPEC.validate()


@dataclass(frozen=True)
class SimulationResult:
    game_name: str
    seed: int | str
    turns: int
    wins: int
    losses: int
    final_total: int
    empirical_gain_per_turn: float
    trajectory: tuple[int, ...]


@dataclass(frozen=True)
class TrialSummary:
    game_name: str
    trials: int
    turns_per_trial: int
    mean_gain_per_turn: float
    sample_standard_deviation: float
    standard_error: float
    approximate_95_percent_interval: tuple[float, float]


def simulate_game(
    game: Game,
    *,
    turns: int,
    seed: int | str,
    start_total: int = 0,
) -> SimulationResult:
    """Run one finite path. The modulo state is based on the current total."""
    game.validate()
    if isinstance(turns, bool) or not isinstance(turns, int) or turns <= 0:
        raise ValueError("turns must be a positive integer")
    if isinstance(start_total, bool) or not isinstance(start_total, int):
        raise ValueError("start_total must be an integer")
    rng = random.Random(seed)
    total = start_total
    wins = 0
    trajectory = [total]
    for _ in range(turns):
        state = total % 3
        if rng.random() < game.probabilities_by_state[state]:
            total += 1
            wins += 1
        else:
            total -= 1
        trajectory.append(total)
    losses = turns - wins
    return SimulationResult(
        game.name, seed, turns, wins, losses, total,
        (wins - losses) / turns, tuple(trajectory),
    )


def _trial_seed(seed: int | str, trial_index: int) -> int:
    payload = f"{seed}\x1f{trial_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def summarize_trials(
    game: Game,
    *,
    trials: int,
    turns_per_trial: int,
    seed: int | str,
) -> TrialSummary:
    """Run independent reproducible trials and report a descriptive normal CI."""
    if isinstance(trials, bool) or not isinstance(trials, int) or trials < 2:
        raise ValueError("at least two trials are required to estimate variation")
    gains = [
        simulate_game(
            game, turns=turns_per_trial, seed=_trial_seed(seed, index)
        ).empirical_gain_per_turn
        for index in range(trials)
    ]
    mean = sum(gains) / trials
    variance = sum((value - mean) ** 2 for value in gains) / (trials - 1)
    standard_deviation = math.sqrt(variance)
    standard_error = standard_deviation / math.sqrt(trials)
    margin = 1.96 * standard_error
    return TrialSummary(
        game.name, trials, turns_per_trial, mean, standard_deviation,
        standard_error, (mean - margin, mean + margin),
    )


def canonical_simulations(
    *,
    turns: int = 10_000,
    seed: int | str = "merlin-parrondo-v1",
) -> tuple[SimulationResult, SimulationResult, SimulationResult]:
    """Return same-budget A, B, and mixture trajectories for side-by-side play."""
    games = make_canonical_games()
    return tuple(simulate_game(game, turns=turns, seed=seed) for game in games)


def record_simulation_input(input_store, learner_id: str, result: SimulationResult, *, task_id: str | None = None) -> int:
    """Persist reproducible run metadata without awarding mastery.

    The trajectory digest plus seed and game parameters makes the run
    independently reproducible. A game outcome is not treated as proof of
    understanding; assessment and mastery updates remain separate operations.
    """
    from .learning_core import LearningInput

    if not learner_id:
        raise ValueError("learner_id is required")
    trajectory_bytes = ",".join(str(value) for value in result.trajectory).encode("ascii")
    trajectory_digest = hashlib.sha256(trajectory_bytes).hexdigest()
    payload = {
        "game_name": result.game_name,
        "seed": result.seed,
        "turns": result.turns,
        "wins": result.wins,
        "losses": result.losses,
        "final_total": result.final_total,
        "empirical_gain_per_turn": result.empirical_gain_per_turn,
        "trajectory_sha256": trajectory_digest,
        "mastery_awarded": False,
    }
    item = LearningInput(
        learner_id=learner_id,
        lesson_id=PARRONDO_LESSON_SPEC.lesson_id,
        task_id=task_id or f"parrondo-simulation:{trajectory_digest[:16]}",
        mode="mixed",
        response=payload,
        confidence=None,
        hints_used=0,
        elapsed_seconds=None,
        accessibility={},
        source_refs=(f"simulation-run:sha256:{trajectory_digest}",),
    )
    return input_store.record(item)
