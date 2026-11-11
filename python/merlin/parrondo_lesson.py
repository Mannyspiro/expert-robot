"""A zero-first, auditable introduction to Parrondo's paradox."""
from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class LessonStage:
    stage_id: str
    mode: str
    prompt: str
    introduces_symbols: bool = False

PARRONDO_LESSON = (
    LessonStage("notice", "concrete", "Imagine two games. Each seems to make you lose a little money over many turns. Could taking turns between them ever help?"),
    LessonStage("play_a", "interactive", "Play Game A many times. Track whether your total tends to rise or fall."),
    LessonStage("play_b", "interactive", "Play Game B. Its coin depends on whether your current total is divisible by three. Track the pattern."),
    LessonStage("mix", "interactive", "Now choose A or B at random on each turn. Compare the long-run result with each game alone."),
    LessonStage("explain_state", "visual", "Notice that Game B changes its rule with the current position. The mixture changes how often you visit each position."),
    LessonStage("probabilities", "symbolic", "Only now describe each coin with a probability and calculate the average gain.", True),
)

@dataclass(frozen=True)
class Game:
    name: str
    probabilities_by_state: tuple[float, float, float]
    def validate(self) -> None:
        if len(self.probabilities_by_state) != 3:
            raise ValueError("this lesson uses exactly three modulo states")
        if any(not 0.0 < p < 1.0 for p in self.probabilities_by_state):
            raise ValueError("win probabilities must be strictly between zero and one")

@dataclass(frozen=True)
class ParrondoResult:
    stationary_distribution: tuple[float, float, float]
    expected_gain_per_turn: float

def stationary_distribution(game: Game) -> tuple[float, float, float]:
    """Compute the modulo-3 stationary distribution by the Markov chain tree theorem.

    Each unnormalized weight is the sum of directed spanning-tree weights
    whose edges point toward that state. This is a closed-form calculation,
    avoiding convergence thresholds or a finite-run simulation.
    """
    game.validate()
    p0, p1, p2 = game.probabilities_by_state
    q0, q1, q2 = 1.0 - p0, 1.0 - p1, 1.0 - p2

    weight_0 = q1 * p2 + q1 * q2 + p1 * p2
    weight_1 = p0 * q2 + p0 * p2 + q0 * q2
    weight_2 = q0 * p1 + q0 * q1 + p0 * p1
    total = weight_0 + weight_1 + weight_2
    if not math.isfinite(total) or total <= 0.0:
        raise ArithmeticError("stationary distribution normalization failed")
    return (weight_0 / total, weight_1 / total, weight_2 / total)

def expected_gain(game: Game) -> ParrondoResult:
    distribution = stationary_distribution(game)
    gain = sum(mass * (2.0 * p - 1.0) for mass, p in zip(distribution, game.probabilities_by_state))
    return ParrondoResult(distribution, gain)

def make_canonical_games(epsilon: float = 0.005) -> tuple[Game, Game, Game]:
    """Return Game A, Game B, and a fair random A/B mixture."""
    if not 0.0 < epsilon < 0.05:
        raise ValueError("epsilon must be between zero and 0.05")
    p_a, p_bad, p_good = 0.5 - epsilon, 0.1 - epsilon, 0.75 - epsilon
    a = Game("A", (p_a, p_a, p_a))
    b = Game("B", (p_bad, p_good, p_good))
    mixed = Game("random_mix_A_B", tuple((x + y) / 2.0 for x, y in zip(a.probabilities_by_state, b.probabilities_by_state)))
    return a, b, mixed

def lesson_results(epsilon: float = 0.005) -> dict[str, ParrondoResult]:
    a, b, mixed = make_canonical_games(epsilon)
    return {game.name: expected_gain(game) for game in (a, b, mixed)}
