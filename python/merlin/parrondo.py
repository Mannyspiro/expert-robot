"""Reproducible Parrondo-paradox simulator and three-state analytic model.

No third-party dependencies. A fixed seed and configuration reproduce every run.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable, Literal

Game = Literal["A", "B", "mixed"]


@dataclass(frozen=True)
class Parameters:
    epsilon: float = 0.005
    mix_probability: float = 0.5

    def validate(self) -> None:
        if not 0 <= self.epsilon < 0.1:
            raise ValueError("epsilon must be in [0, 0.1)")
        if not 0 <= self.mix_probability <= 1:
            raise ValueError("mix_probability must be in [0, 1]")


@dataclass(frozen=True)
class Trial:
    game: Game
    start: int
    end: int
    turns: int
    seed: int


@dataclass(frozen=True)
class Summary:
    game: Game
    trials: int
    turns_per_trial: int
    mean_change: float
    sample_stddev: float
    fraction_profitable: float


def win_probability(game: Literal["A", "B"], capital: int, p: Parameters) -> float:
    p.validate()
    if game == "A":
        return 0.5 - p.epsilon
    return (0.1 if capital % 3 == 0 else 0.75) - p.epsilon


def play_trial(
    game: Game,
    *,
    start: int = 30,
    turns: int = 3000,
    seed: int = 0,
    parameters: Parameters = Parameters(),
) -> Trial:
    parameters.validate()
    if turns < 0:
        raise ValueError("turns must be non-negative")
    rng = random.Random(seed)
    capital = int(start)
    for _ in range(turns):
        selected: Literal["A", "B"]
        if game == "mixed":
            selected = "A" if rng.random() < parameters.mix_probability else "B"
        else:
            selected = game
        capital += 1 if rng.random() < win_probability(selected, capital, parameters) else -1
    return Trial(game, int(start), capital, turns, seed)


def summarize(trials: Iterable[Trial]) -> Summary:
    rows = tuple(trials)
    if not rows:
        raise ValueError("at least one trial is required")
    game = rows[0].game
    turns = rows[0].turns
    if any(row.game != game or row.turns != turns for row in rows):
        raise ValueError("all trials must use the same game and turn count")
    changes = [row.end - row.start for row in rows]
    mean = sum(changes) / len(changes)
    variance = (
        sum((value - mean) ** 2 for value in changes) / (len(changes) - 1)
        if len(changes) > 1 else 0.0
    )
    return Summary(
        game=game,
        trials=len(rows),
        turns_per_trial=turns,
        mean_change=mean,
        sample_stddev=variance ** 0.5,
        fraction_profitable=sum(value > 0 for value in changes) / len(changes),
    )


def _transition(game: Literal["A", "B"], state: int, p: Parameters) -> tuple[float, ...]:
    win = win_probability(game, state, p)
    result = [0.0, 0.0, 0.0]
    result[(state + 1) % 3] += win
    result[(state - 1) % 3] += 1.0 - win
    return tuple(result)


def stationary_distribution(game: Game, parameters: Parameters = Parameters()) -> tuple[float, ...]:
    """Stationary distribution over capital modulo three."""
    parameters.validate()
    if game not in ("A", "B", "mixed"):
        raise ValueError(f"unknown game: {game}")
    distribution = [1.0 / 3.0] * 3
    for _ in range(100_000):
        updated = [0.0, 0.0, 0.0]
        for state, mass in enumerate(distribution):
            if game == "mixed":
                transitions = [
                    (parameters.mix_probability, _transition("A", state, parameters)),
                    (1.0 - parameters.mix_probability, _transition("B", state, parameters)),
                ]
            else:
                transitions = [(1.0, _transition(game, state, parameters))]
            for weight, probabilities in transitions:
                for destination, probability in enumerate(probabilities):
                    updated[destination] += mass * weight * probability
        if max(abs(updated[i] - distribution[i]) for i in range(3)) < 1e-14:
            return tuple(updated)
        distribution = updated
    raise RuntimeError("stationary distribution did not converge")


def expected_gain_per_turn(game: Game, parameters: Parameters = Parameters()) -> float:
    """Long-run expected capital change per turn from the stationary state mix."""
    distribution = stationary_distribution(game, parameters)
    gains = []
    for state in range(3):
        a_gain = 2.0 * win_probability("A", state, parameters) - 1.0
        b_gain = 2.0 * win_probability("B", state, parameters) - 1.0
        gains.append(
            a_gain if game == "A" else
            b_gain if game == "B" else
            parameters.mix_probability * a_gain + (1.0 - parameters.mix_probability) * b_gain
        )
    return sum(distribution[state] * gains[state] for state in range(3))
