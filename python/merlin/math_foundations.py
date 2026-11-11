"""First-principles mathematics curriculum for Merlin's existing learning core.

This is content and lesson orchestration, not a parallel learner database.
Learner attempts, mastery telemetry, spaced repetition, and lesson sessions
remain in merlin.learning_core.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence

from merlin.learning_core import (
    Concept,
    ConceptRegistry,
    DEFAULT_CONCEPTS,
    LessonSpec,
    LessonStage,
    LearnerStore,
    MASTERY_DIMENSIONS,
    select_next_lesson,
)


PATHS = frozenset({
    "mathematician",
    "mathematics_programmer",
    "computational_hacker",
})
ANSWER_FORMATS = frozenset({
    "written_explanation",
    "table_and_explanation",
    "python_code_and_explanation",
    "conjecture_and_counterexample_search",
    "proof",
    "python_code_and_tests",
    "python_experiment_and_explanation",
})


@dataclass(frozen=True)
class RubricCriterion:
    dimension: str
    description: str
    points: int

    def validate(self) -> None:
        if not self.dimension or not self.description.strip():
            raise ValueError("rubric dimension and description are required")
        if isinstance(self.points, bool) or not isinstance(self.points, int) or self.points < 1:
            raise ValueError("rubric points must be a positive integer")


@dataclass(frozen=True)
class ExerciseSpec:
    task_id: str
    objective: str
    prompt: str
    answer_format: str
    hints: tuple[str, ...]
    rubric: tuple[RubricCriterion, ...]
    transfer_prompt: str
    allowed_tools: tuple[str, ...] = ()

    def validate(self) -> None:
        for field_name in ("task_id", "objective", "prompt", "transfer_prompt"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"exercise {field_name} is required")
        if self.answer_format not in ANSWER_FORMATS:
            raise ValueError(f"{self.task_id}: unsupported answer format")
        if len(self.hints) < 2 or any(not isinstance(hint, str) or not hint.strip() for hint in self.hints):
            raise ValueError(f"{self.task_id}: at least two non-empty hints are required")
        if not self.rubric:
            raise ValueError(f"{self.task_id}: rubric cannot be empty")
        dimensions: set[str] = set()
        for criterion in self.rubric:
            criterion.validate()
            if criterion.dimension in dimensions:
                raise ValueError(f"{self.task_id}: duplicate rubric dimension {criterion.dimension}")
            dimensions.add(criterion.dimension)
        if len(set(self.allowed_tools)) != len(self.allowed_tools) or any(
            not isinstance(tool, str) or not tool.strip() for tool in self.allowed_tools
        ):
            raise ValueError(f"{self.task_id}: allowed tools must be unique non-empty strings")


@dataclass(frozen=True)
class FoundationLesson:
    lesson: LessonSpec
    exercise: ExerciseSpec
    historical_context: str = ""
    source_refs: tuple[str, ...] = ()
    interest_tags: tuple[str, ...] = ()
    estimated_minutes: int = 20
    learning_value: float = 0.5
    transfer_value: float = 0.5

    def validate(self, concepts: ConceptRegistry) -> None:
        self.lesson.validate()
        self.exercise.validate()
        known = {concept.concept_id for concept in concepts.all()}
        missing = (set(self.lesson.target_concepts) | set(self.lesson.prerequisites)) - known
        if missing:
            raise ValueError(f"{self.lesson.lesson_id}: unknown concepts {sorted(missing)}")
        if not set(self.lesson.path_tags).issubset(PATHS):
            raise ValueError(f"{self.lesson.lesson_id}: unknown learning path")
        if any(not isinstance(ref, str) or not ref.strip() for ref in self.source_refs):
            raise ValueError(f"{self.lesson.lesson_id}: source refs must be non-empty strings")
        if any(not isinstance(tag, str) or not tag.strip() for tag in self.interest_tags):
            raise ValueError(f"{self.lesson.lesson_id}: interest tags must be non-empty strings")
        if isinstance(self.estimated_minutes, bool) or not isinstance(self.estimated_minutes, int) or self.estimated_minutes < 1:
            raise ValueError(f"{self.lesson.lesson_id}: estimated_minutes must be a positive integer")
        for label, value in (("learning_value", self.learning_value), ("transfer_value", self.transfer_value)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{self.lesson.lesson_id}: {label} must be between zero and one")


FOUNDATION_CONCEPTS = ConceptRegistry((
    *DEFAULT_CONCEPTS.all(),
    Concept("whole-number-structure", "Whole-number structure", "Counting, order, and additive patterns."),
    Concept("divisibility", "Divisibility and factors", "Factor pairs and exact divisibility.", ("whole-number-structure",)),
    Concept("prime-numbers", "Prime numbers", "Integers greater than one with exactly two positive factors.", ("divisibility",)),
    Concept("proof-by-contradiction", "Proof by contradiction", "Derive a contradiction from an assumed negation.", ("prime-numbers",)),
    Concept("variables-and-expressions", "Variables and expressions", "Represent changing or unknown quantities with symbols."),
    Concept("algorithmic-loops", "Loops and repeated computation", "Repeat a bounded operation with explicit state.", ("variables-and-expressions",)),
    Concept("finite-experiment-design", "Finite experiments and counterexamples", "Test a conjecture over a declared finite domain.", ("algorithmic-loops",)),
))


def _rubric(*items: tuple[str, str, int]) -> tuple[RubricCriterion, ...]:
    return tuple(RubricCriterion(*item) for item in items)


FOUNDATION_LESSONS: tuple[FoundationLesson, ...] = (
    FoundationLesson(
        LessonSpec(
            "math.foundations.counting-patterns.v1",
            "Find the pattern in odd numbers",
            ("whole-number-structure",), (),
            (
                LessonStage("objects", "concrete", "Lay out a row of objects, then add one more pair. What changes?"),
                LessonStage("notice", "observation", "Compare 1, 3, 5, 7, and 9. Describe the change from one number to the next."),
                LessonStage("picture", "visual", "Draw or arrange the numbers as growing groups. What stays the same?"),
                LessonStage("explain", "language", "Explain why each new odd number is two more than the previous one."),
                LessonStage("generalize", "symbol", "Now describe the nth odd number with a rule, after the pattern is understood.", True),
            ),
            path_tags=("mathematician", "mathematics_programmer", "computational_hacker"),
            priority=1.5,
        ),
        ExerciseSpec(
            "discover-counting-patterns",
            "Recognize additive structure and express a pattern in general form.",
            "For 1, 3, 5, 7, 9, ... find the 10th term, state a rule for the nth odd number, and check it at three positions.",
            "written_explanation",
            ("Compare consecutive terms.", "The difference is constant.", "Start at 1 and add 2 for every step after the first."),
            _rubric(("pattern", "Identifies the constant difference of two.", 2),
                    ("general_rule", "States a correct nth-term rule.", 3),
                    ("verification", "Checks at least three positions.", 2)),
            "Start at 4 and add 3 each time. Give the nth-term rule and compare it with the odd-number rule.",
            ("paper", "calculator"),
        ),
        interest_tags=["patterns","puzzles"],
        estimated_minutes=20,
        learning_value=0.9,
        transfer_value=0.8,
    ),
    FoundationLesson(
        LessonSpec(
            "math.foundations.variables.v1",
            "What is a variable?",
            ("variables-and-expressions",), (),
            (
                LessonStage("changing-quantity", "concrete", "Imagine a jar receiving one coin each minute. The amount changes as time passes."),
                LessonStage("make-a-table", "observation", "Record the amount after zero, one, two, and three minutes."),
                LessonStage("draw-the-change", "visual", "Plot time against the amount in the jar."),
                LessonStage("name-the-relationship", "language", "Explain which quantity changes and which quantity is being measured."),
                LessonStage("introduce-symbol", "symbol", "Use a letter as a name for the changing amount only after describing the relationship.", True),
            ),
            path_tags=("mathematician", "mathematics_programmer", "computational_hacker"),
            priority=1.4,
        ),
        ExerciseSpec(
            "introduce-variables",
            "Interpret a variable as a name for a changing or unknown quantity.",
            "A jar starts with 4 coins and receives 3 more coins each minute. Make a table for the first five minutes, describe the pattern, and write a rule for the number of coins after m minutes.",
            "table_and_explanation",
            ("Separate the starting amount from the amount added each minute.", "The amount added is the same each minute.", "A letter can stand for any allowed number of minutes."),
            _rubric(("table", "Builds an accurate table.", 2),
                    ("interpretation", "Explains the starting amount and repeated increase.", 2),
                    ("expression", "Writes and interprets the rule 4 + 3m.", 3)),
            "Change the jar so it starts with 7 coins and receives 2 coins per minute. Write and explain the new rule.",
            ("paper", "calculator"),
        ),
        interest_tags=["modeling","real_world"],
        estimated_minutes=20,
        learning_value=0.8,
        transfer_value=0.8,
    ),
    FoundationLesson(
        LessonSpec(
            "math.foundations.divisibility.v1",
            "Build a factor table",
            ("divisibility",), ("whole-number-structure",),
            (
                LessonStage("equal-groups", "concrete", "Arrange 12 counters into equal rows without leftovers."),
                LessonStage("record-arrangements", "observation", "List the row and column counts that use all 12 counters."),
                LessonStage("compare-numbers", "visual", "Repeat for 13 and 18. Compare how many equal arrangements each allows."),
                LessonStage("define-factor", "language", "Explain what it means for one number to divide another exactly."),
                LessonStage("factor-notation", "symbol", "Use factor notation after you can explain the equal-group idea.", True),
            ),
            path_tags=("mathematician", "mathematics_programmer"),
            priority=1.2,
        ),
        ExerciseSpec(
            "build-factor-table",
            "Use divisibility and factor pairs to classify whole numbers.",
            "For each integer from 1 through 30, list all positive factor pairs. Classify each number greater than 1 as prime or composite, and explain why 1 is neither.",
            "table_and_explanation",
            ("A factor pair multiplies to the target number.", "Test divisors up to the square root; pairs then repeat in reverse.", "A prime has exactly two positive factors."),
            _rubric(("factor_pairs", "Lists correct factor pairs.", 4),
                    ("classification", "Correctly classifies primes and composites.", 3),
                    ("definition", "Explains why 1 is neither prime nor composite.", 2)),
            "Choose a composite number between 31 and 50, list all factor pairs, and justify that the list is complete.",
            ("paper", "calculator"),
        ),
        interest_tags=["number_theory","tables"],
        estimated_minutes=25,
        learning_value=0.8,
        transfer_value=0.7,
    ),
    FoundationLesson(
        LessonSpec(
            "math.foundations.prime-conjecture.v1",
            "Conjecture a pattern in prime numbers",
            ("prime-numbers",), ("divisibility",),
            (
                LessonStage("sort-number-cards", "concrete", "Sort number cards into prime and composite groups using factor pairs."),
                LessonStage("inspect-primes", "observation", "List primes greater than 3 and below 50. Look for a repeated pattern."),
                LessonStage("remainders-wheel", "visual", "Place each prime on a remainder wheel for division by 6."),
                LessonStage("state-conjecture", "language", "State what remainders seem possible and identify what would disprove the pattern."),
                LessonStage("write-general-form", "symbol", "Express the possible forms using 6k plus or minus 1.", True),
            ),
            path_tags=("mathematician", "mathematics_programmer"),
            priority=1.15,
        ),
        ExerciseSpec(
            "conjecture-prime-pattern",
            "Form a conjecture from examples and distinguish evidence from proof.",
            "List primes greater than 3 and below 50. Find each remainder after division by 6. Conjecture which remainders are possible, search for counterexamples, and explain why the finite list is not a proof.",
            "conjecture_and_counterexample_search",
            ("There are six possible remainders.", "A prime greater than 3 cannot be divisible by 2 or 3.", "Remainders 0, 2, 3, and 4 force divisibility by 2 or 3."),
            _rubric(("data", "Computes the remainders accurately.", 2),
                    ("conjecture", "States the 6k plus or minus 1 condition.", 3),
                    ("reasoning", "Distinguishes finite evidence from proof.", 3)),
            "Find a composite number of the form 6k + 1. Explain why the form is necessary but not sufficient for primes greater than 3.",
            ("paper", "python"),
        ),
        interest_tags=["number_theory","patterns"],
        estimated_minutes=25,
        learning_value=0.9,
        transfer_value=0.8,
    ),
    FoundationLesson(
        LessonSpec(
            "math.foundations.prime-checker.v1",
            "Turn the definition of prime into code",
            ("prime-numbers",), ("divisibility",),
            (
                LessonStage("test-small-numbers", "concrete", "Try to divide small numbers into equal groups."),
                LessonStage("record-divisors", "observation", "Record which candidate divisors leave no remainder."),
                LessonStage("pair-factors", "visual", "Pair small and large factors. Notice where the pairs meet."),
                LessonStage("explain-search-bound", "language", "Explain why a factor larger than the square root has a smaller partner."),
                LessonStage("write-condition", "symbol", "Translate the divisor condition into a loop bound.", True),
                LessonStage("implement", "code", "Implement and test a primality checker."),
            ),
            path_tags=("mathematics_programmer", "computational_hacker"),
            priority=1.1,
        ),
        ExerciseSpec(
            "write-prime-checker",
            "Translate primality into a tested algorithm.",
            "Write is_prime(n) in Python. Handle integers below 2, test divisors only as far as necessary, and test 0, 1, 2, 9, 17, and 49. Explain the loop bound.",
            "python_code_and_explanation",
            ("A prime is greater than 1 and has no divisors except 1 and itself.", "If n has a factor above its square root, it has a paired factor below it.", "Test divisors through the integer square root, inclusive."),
            _rubric(("correctness", "Handles the required edge cases and examples.", 4),
                    ("algorithm", "Uses a justified divisor bound.", 3),
                    ("explanation", "Explains why the algorithm decides primality.", 2)),
            "Return the smallest non-trivial factor for composite n, or None when n is prime.",
            ("python", "calculator"),
        ),
        interest_tags=["python","number_theory"],
        estimated_minutes=30,
        learning_value=0.9,
        transfer_value=0.9,
    ),
    FoundationLesson(
        LessonSpec(
            "math.foundations.euclid-infinite-primes.v1",
            "Why there cannot be a last prime",
            ("proof-by-contradiction",), ("prime-numbers",),
            (
                LessonStage("finite-list", "concrete", "Imagine someone claims to have written down every prime number."),
                LessonStage("inspect-product", "observation", "Multiply the listed primes and ask what happens after adding one."),
                LessonStage("divisibility-picture", "visual", "Show why every listed prime leaves remainder one when dividing the new number."),
                LessonStage("explain-contradiction", "language", "Explain why the new number has a prime divisor that is not on the list."),
                LessonStage("formalize-proof", "symbol", "Write the product-plus-one argument with symbols.", True),
            ),
            path_tags=("mathematician",),
            priority=1.0,
        ),
        ExerciseSpec(
            "prove-infinite-primes",
            "Construct and explain Euclid's proof that there are infinitely many primes.",
            "Assume there are finitely many primes p₁ through pₙ. Construct N as their product plus one. Explain why no listed prime divides N, and why a prime divisor of N contradicts the complete-list assumption. Do not assume N itself is prime.",
            "proof",
            ("Assume a finite complete list p₁, p₂, ..., pₙ.", "Consider N = p₁p₂...pₙ + 1.", "If N is composite, it still has a prime divisor; none of the listed primes divides it."),
            _rubric(("assumption", "States the finite complete-list assumption.", 2),
                    ("construction", "Constructs the product-plus-one number.", 2),
                    ("divisibility", "Shows no listed prime divides the new number.", 3),
                    ("conclusion", "Uses a prime divisor to derive a contradiction.", 3)),
            "Explain why the argument still works when the product-plus-one number is composite.",
            ("paper",),
        ),
        interest_tags=["number_theory","history"],
        estimated_minutes=35,
        learning_value=1,
        transfer_value=1,
        historical_context="Euclid's Elements, Book IX, Proposition 20, gives the classical proof that prime numbers are more than any assigned multitude.",
        source_refs=("Euclid, Elements, Book IX, Proposition 20",),
    ),
    FoundationLesson(
        LessonSpec(
            "math.foundations.repeated-addition.v1",
            "Build multiplication from repeated addition",
            ("algorithmic-loops",), ("variables-and-expressions",),
            (
                LessonStage("equal-groups", "concrete", "Make several equal groups of objects and count the total."),
                LessonStage("repeat-the-addition", "observation", "Write the same addend repeatedly and compare it with the total."),
                LessonStage("track-running-total", "visual", "Draw a counter that increases once for each group."),
                LessonStage("describe-the-loop", "language", "Explain the starting value, repeated action, and stopping condition."),
                LessonStage("express-loop-state", "symbol", "Name the running total and the number of repetitions.", True),
                LessonStage("implement-loop", "code", "Implement multiplication using a loop and addition."),
            ),
            path_tags=("mathematics_programmer", "computational_hacker"),
            priority=1.0,
        ),
        ExerciseSpec(
            "implement-repeated-addition",
            "Represent multiplication as repeated addition and implement it with a loop.",
            "Write multiply_by_addition(a, b) using a loop and repeated addition. Do not use the multiplication operator inside the function. Define behavior for zero and negative inputs and test at least five cases.",
            "python_code_and_tests",
            ("For positive b, add a to a running total b times.", "Start the running total at zero.", "For negative b, count abs(b) repetitions and apply the sign."),
            _rubric(("implementation", "Uses repeated addition and a loop.", 3),
                    ("edge_cases", "Handles zero and negative inputs.", 3),
                    ("tests", "Includes at least five meaningful tests.", 2)),
            "Explain how repeated addition relates to the distributive property and count the additions performed.",
            ("python",),
        ),
        interest_tags=["python","programming"],
        estimated_minutes=20,
        learning_value=0.8,
        transfer_value=0.8,
    ),
    FoundationLesson(
        LessonSpec(
            "math.foundations.counterexample-search.v1",
            "Find the first counterexample",
            ("finite-experiment-design",), ("algorithmic-loops",),
            (
                LessonStage("test-the-claim", "concrete", "Examine several values of n in the expression n squared plus n plus 41."),
                LessonStage("make-a-table", "observation", "Record n, the expression value, and whether it is prime."),
                LessonStage("plot-the-results", "visual", "Visualize the sequence and mark the first composite value."),
                LessonStage("separate-evidence", "language", "Explain what a finite search can disprove and what it cannot prove."),
                LessonStage("write-search-domain", "symbol", "State the domain and loop condition explicitly.", True),
                LessonStage("run-the-search", "code", "Search in increasing order and report the first counterexample."),
            ),
            path_tags=("mathematician", "mathematics_programmer", "computational_hacker"),
            priority=0.95,
        ),
        ExerciseSpec(
            "search-small-counterexamples",
            "Use a finite computational search to find a counterexample.",
            "Investigate the conjecture that n² + n + 41 is prime for every non-negative integer n. Search upward from zero, find the first counterexample, factor it, and state exactly what the finite search establishes.",
            "python_experiment_and_explanation",
            ("Start at n = 0 and increase by one.", "Use the earlier primality checker or a separate divisor search.", "Look for a value that makes the expression a perfect square."),
            _rubric(("experiment", "Runs a reproducible finite search.", 3),
                    ("counterexample", "Finds n = 40 and factors 1681 as 41 × 41.", 3),
                    ("interpretation", "Explains the logical scope of a counterexample.", 3)),
            "Replace 41 with 43 and search the first 50 non-negative integers. Explain what the result does and does not prove.",
            ("python", "calculator"),
        ),
        interest_tags=["python","puzzles","experiments"],
        estimated_minutes=30,
        learning_value=0.9,
        transfer_value=1,
    ),
)


def validate_foundation_curriculum() -> dict[str, FoundationLesson]:
    FOUNDATION_CONCEPTS.validate()
    lessons: dict[str, FoundationLesson] = {}
    task_ids: set[str] = set()
    for item in FOUNDATION_LESSONS:
        item.validate(FOUNDATION_CONCEPTS)
        lesson_id = item.lesson.lesson_id
        if lesson_id in lessons:
            raise ValueError(f"duplicate lesson id: {lesson_id}")
        if item.exercise.task_id in task_ids:
            raise ValueError(f"duplicate exercise task id: {item.exercise.task_id}")
        lessons[lesson_id] = item
        task_ids.add(item.exercise.task_id)
    return lessons


def select_foundation_lesson(
    learner_id: str,
    store: LearnerStore,
    *,
    path: str = "mathematician",
    mastery_threshold: float = 0.70,
) -> LessonSpec | None:
    """Use the existing SQLite learner model and deterministic lesson selector."""
    catalogue = validate_foundation_curriculum()
    return select_next_lesson(
        learner_id,
        store,
        tuple(item.lesson for item in catalogue.values()),
        FOUNDATION_CONCEPTS,
        path=path,
        mastery_threshold=mastery_threshold,
    )


def recommend_foundation_lessons(
    learner_id: str,
    store: LearnerStore,
    *,
    path_weights: Mapping[str, float],
    interests: Iterable[str] = (),
    max_minutes: int | None = None,
    mastery_threshold: float = 0.70,
    limit: int = 5,
    completed_task_ids: Iterable[str] = (),
) -> dict[str, object]:
    """Rank eligible foundation lessons using learner history and interests.

    This is a deterministic pedagogical recommendation, not a mastery or proof
    decision. Prerequisites use the existing learner store's core dimensions.
    """
    if not isinstance(learner_id, str) or not learner_id:
        raise ValueError("learner_id is required")
    if not isinstance(path_weights, Mapping) or not path_weights:
        raise ValueError("path_weights must be a non-empty mapping")
    unknown_paths = set(path_weights) - PATHS
    if unknown_paths:
        raise ValueError(f"unknown learning paths: {sorted(unknown_paths)}")
    normalized: dict[str, float] = {}
    for path, value in path_weights.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"path weight for {path} must be between zero and one")
        normalized[path] = float(value)
    total_weight = sum(normalized.values())
    if total_weight <= 0:
        raise ValueError("at least one path weight must be greater than zero")
    normalized = {path: value / total_weight for path, value in normalized.items()}

    if isinstance(interests, str):
        raise ValueError("interests must be an iterable of strings, not a string")
    interest_set = set(interests)
    if any(not isinstance(tag, str) or not tag.strip() for tag in interest_set):
        raise ValueError("interests must contain non-empty strings")
    if max_minutes is not None and (
        isinstance(max_minutes, bool) or not isinstance(max_minutes, int) or max_minutes < 1
    ):
        raise ValueError("max_minutes must be a positive integer")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    if isinstance(mastery_threshold, bool) or not isinstance(mastery_threshold, (int, float)) or not math.isfinite(mastery_threshold) or not 0 <= mastery_threshold <= 1:
        raise ValueError("mastery_threshold must be between zero and one")
    completed = set(completed_task_ids)
    if any(not isinstance(task_id, str) or not task_id for task_id in completed):
        raise ValueError("completed_task_ids must contain non-empty strings")

    catalogue = validate_foundation_curriculum()
    max_priority = max(item.lesson.priority for item in catalogue.values())
    ranked: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    for item in catalogue.values():
        task_id = item.exercise.task_id
        if task_id in completed:
            continue
        if max_minutes is not None and item.estimated_minutes > max_minutes:
            blocked.append({
                "task_id": task_id,
                "lesson_id": item.lesson.lesson_id,
                "blocked_reason": "exceeds_time_budget",
                "estimated_minutes": item.estimated_minutes,
            })
            continue
        pathway_fit = sum(
            weight for path, weight in normalized.items()
            if path in item.lesson.path_tags
        )
        if pathway_fit <= 0:
            continue
        missing_prerequisites = []
        for prerequisite in item.lesson.prerequisites:
            mastery = store.mastery(learner_id, prerequisite)
            core_average = sum(
                mastery[dimension]
                for dimension in ("conceptual", "procedural", "representational")
            ) / 3.0
            if core_average < mastery_threshold:
                missing_prerequisites.append(prerequisite)
        if missing_prerequisites:
            blocked.append({
                "task_id": task_id,
                "lesson_id": item.lesson.lesson_id,
                "blocked_reason": "prerequisites_not_yet_demonstrated",
                "missing_prerequisites": sorted(missing_prerequisites),
            })
            continue

        target_gaps = []
        for concept_id in item.lesson.target_concepts:
            mastery = store.mastery(learner_id, concept_id)
            target_gaps.append(
                1.0 - sum(mastery[dimension] for dimension in MASTERY_DIMENSIONS) / len(MASTERY_DIMENSIONS)
            )
        concept_need = sum(target_gaps) / len(target_gaps) if target_gaps else 0.0
        interest_fit = (
            len(interest_set.intersection(item.interest_tags)) / len(item.interest_tags)
            if item.interest_tags else 0.0
        )
        time_fit = (
            0.5 if max_minutes is None
            else max(0.0, 1.0 - item.estimated_minutes / max_minutes)
        )
        priority_fit = min(item.lesson.priority / max_priority, 1.0)
        components = {
            "pathway_fit": round(pathway_fit, 6),
            "interest_fit": round(interest_fit, 6),
            "learning_value": round(item.learning_value, 6),
            "transfer_value": round(item.transfer_value, 6),
            "concept_need": round(concept_need, 6),
            "time_fit": round(time_fit, 6),
            "priority_fit": round(priority_fit, 6),
        }
        score = (
            0.30 * pathway_fit
            + 0.20 * interest_fit
            + 0.15 * item.learning_value
            + 0.15 * item.transfer_value
            + 0.10 * concept_need
            + 0.05 * time_fit
            + 0.05 * priority_fit
        )
        reasons = []
        if pathway_fit > 0:
            reasons.append("matches_selected_learning_paths")
        if interest_fit > 0:
            reasons.append("matches_learner_interests")
        if concept_need >= 0.7:
            reasons.append("addresses_unsettled_concepts")
        if item.learning_value >= 0.8:
            reasons.append("high_learning_value")
        if item.transfer_value >= 0.8:
            reasons.append("supports_transfer")
        if max_minutes is not None:
            reasons.append("fits_time_budget")
        ranked.append({
            "task_id": task_id,
            "lesson_id": item.lesson.lesson_id,
            "score": round(score, 6),
            "score_components": components,
            "reason_codes": reasons,
            "estimated_minutes": item.estimated_minutes,
            "planner_version": "1.0.0",
        })

    ranked.sort(key=lambda entry: (-float(entry["score"]), str(entry["task_id"])))
    blocked.sort(key=lambda entry: (str(entry["task_id"]), str(entry["blocked_reason"])))
    return {
        "planner_version": "1.0.0",
        "ranked_lessons": ranked[:limit],
        "blocked_lessons": blocked,
        "eligible_count": len(ranked),
        "returned_count": min(len(ranked), limit),
    }
