import math
import tempfile
import unittest
from pathlib import Path

from merlin.learning_core import (
    Attempt,
    Concept,
    ConceptRegistry,
    DERIVATIVE_DISCOVERY,
    Expr,
    LearnerStore,
    LessonSpec,
    LessonStage,
    MASTERY_DIMENSIONS,
    central_difference,
    evaluate_expression,
    forward_difference,
    backward_difference,
    select_next_lesson,
    validate_expression,
)


class ConceptRegistryTests(unittest.TestCase):
    def test_default_graph_is_valid(self):
        from merlin.learning_core import DEFAULT_CONCEPTS
        DEFAULT_CONCEPTS.validate()
        self.assertEqual(DEFAULT_CONCEPTS.get("derivative").prerequisites, ("function", "limit", "slope"))

    def test_unknown_prerequisite_fails_closed(self):
        registry = ConceptRegistry((Concept("a", "A", "A", ("missing",)),))
        with self.assertRaisesRegex(ValueError, "unknown prerequisites"):
            registry.validate()

    def test_cycle_fails_closed(self):
        registry = ConceptRegistry((Concept("a", "A", "A", ("b",)), Concept("b", "B", "B", ("a",))))
        with self.assertRaisesRegex(ValueError, "cycle"):
            registry.validate()


class ExpressionIRTests(unittest.TestCase):
    def test_evaluates_typed_scalar_expression(self):
        expr = Expr.make("mul", Expr.make("add", Expr.variable("x"), Expr.constant(2)), Expr.constant(3))
        validate_expression(expr)
        self.assertEqual(evaluate_expression(expr, {"x": 4}), 18)

    def test_bad_arity_and_unknown_variable_fail(self):
        with self.assertRaises(ValueError):
            validate_expression(Expr.make("add", Expr.constant(1)))
        with self.assertRaises(KeyError):
            evaluate_expression(Expr.variable("x"), {})

    def test_division_by_zero_fails(self):
        expr = Expr.make("div", Expr.constant(1), Expr.constant(0))
        with self.assertRaises(ZeroDivisionError):
            evaluate_expression(expr, {})


class DerivativeExperimentTests(unittest.TestCase):
    def test_three_finite_difference_methods(self):
        f = lambda x: x * x
        forward = forward_difference(f, 3.0, 1e-4)
        backward = backward_difference(f, 3.0, 1e-4)
        central = central_difference(f, 3.0, 1e-4)
        self.assertAlmostEqual(forward.estimate, 6.0, delta=2e-4)
        self.assertAlmostEqual(backward.estimate, 6.0, delta=2e-4)
        self.assertAlmostEqual(central.estimate, 6.0, delta=1e-7)
        self.assertEqual(central.method, "central")

    def test_invalid_step_fails(self):
        for h in (0, -1, math.inf, math.nan):
            with self.subTest(h=h), self.assertRaises(ValueError):
                central_difference(lambda x: x, 1.0, h)


class BeginnerLessonTests(unittest.TestCase):
    def test_symbols_are_delayed_until_after_concrete_and_visual_stages(self):
        DERIVATIVE_DISCOVERY.validate()
        self.assertEqual(DERIVATIVE_DISCOVERY.stages[0].mode, "concrete")
        self.assertFalse(DERIVATIVE_DISCOVERY.stages[0].introduces_symbols)
        symbol_index = next(i for i, stage in enumerate(DERIVATIVE_DISCOVERY.stages) if stage.introduces_symbols)
        prior_modes = {stage.mode for stage in DERIVATIVE_DISCOVERY.stages[:symbol_index]}
        self.assertIn("concrete", prior_modes)
        self.assertIn("visual", prior_modes)


class LearnerStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = LearnerStore(Path(self.temp.name) / "learner.sqlite")

    def tearDown(self):
        self.temp.cleanup()

    def test_attempts_persist_and_update_dimension_specific_mastery(self):
        scores = {dimension: 0.8 for dimension in MASTERY_DIMENSIONS}
        attempt_id = self.store.record_attempt(
            Attempt("learner-1", DERIVATIVE_DISCOVERY.lesson_id, "task-1", scores, True),
            ("quantity", "change"),
        )
        self.assertGreater(attempt_id, 0)
        self.assertEqual(self.store.attempt_count("learner-1"), 1)
        self.assertAlmostEqual(self.store.mastery("learner-1", "quantity")["conceptual"], 0.28)

    def test_hints_reduce_evidence_weight_without_erasing_performance(self):
        scores = {dimension: 1.0 for dimension in MASTERY_DIMENSIONS}
        self.store.record_attempt(
            Attempt("learner-2", "lesson", "task", scores, False, hints_used=2),
            ("quantity",),
        )
        self.assertAlmostEqual(self.store.mastery("learner-2", "quantity")["conceptual"], 0.2625)

    def test_invalid_scores_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.record_attempt(
                Attempt("learner", "lesson", "task", {"conceptual": 1.5}, True),
                ("quantity",),
            )

    def test_zero_knowledge_learner_gets_beginner_lesson(self):
        selected = select_next_lesson("new-learner", self.store, (DERIVATIVE_DISCOVERY,))
        self.assertEqual(selected.lesson_id, DERIVATIVE_DISCOVERY.lesson_id)

    def test_path_filter_is_respected(self):
        selected = select_next_lesson(
            "new-learner", self.store, (DERIVATIVE_DISCOVERY,), path="computational_hacker"
        )
        self.assertEqual(selected.lesson_id, DERIVATIVE_DISCOVERY.lesson_id)

    def test_prerequisite_uses_core_learning_dimensions_not_proof_or_retention(self):
        follow_on = LessonSpec(
            lesson_id="lesson.after.quantity",
            title="Next lesson",
            target_concepts=("change",),
            prerequisites=("quantity",),
            stages=(LessonStage("concrete", "concrete", "Explore another everyday example."),),
        )
        self.store.record_attempt(
            Attempt(
                "learner-3", "intro", "quantity-check",
                {"conceptual": 0.9, "procedural": 0.9, "representational": 0.9},
                True,
            ),
            ("quantity",),
        )
        selected = select_next_lesson("learner-3", self.store, (follow_on,))
        self.assertEqual(selected.lesson_id, follow_on.lesson_id)

    def test_prerequisite_blocks_when_core_mastery_is_below_threshold(self):
        follow_on = LessonSpec(
            lesson_id="lesson.after.quantity",
            title="Next lesson",
            target_concepts=("change",),
            prerequisites=("quantity",),
            stages=(LessonStage("concrete", "concrete", "Explore another everyday example."),),
        )
        selected = select_next_lesson("learner-4", self.store, (follow_on,))
        self.assertIsNone(selected)

    def test_unknown_prerequisite_concept_is_rejected(self):
        invalid = LessonSpec(
            lesson_id="lesson.invalid",
            title="Invalid",
            target_concepts=("quantity",),
            prerequisites=("not-in-registry",),
            stages=(LessonStage("concrete", "concrete", "Start with an object."),),
        )
        with self.assertRaisesRegex(ValueError, "unknown concepts"):
            select_next_lesson("learner", self.store, (invalid,))

    def test_attempt_history_survives_reopening_database(self):
        scores = {"conceptual": 0.7}
        self.store.record_attempt(
            Attempt("learner-5", "lesson", "task", scores, True), ("quantity",)
        )
        reopened = LearnerStore(Path(self.temp.name) / "learner.sqlite")
        self.assertEqual(reopened.attempt_count("learner-5"), 1)
        self.assertAlmostEqual(reopened.mastery("learner-5", "quantity")["conceptual"], 0.245)


if __name__ == "__main__":
    unittest.main()
