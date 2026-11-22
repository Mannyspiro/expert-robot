"""Focused offline tests for synthetic practice/heldout competency scoring."""
import unittest
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin.agent_training_bench import (
    TASKS, Task, bank_identity, evaluate_holdout, practice_context,
    practice_feedback, score_answer, validate_bank
)


class TrainingBenchTests(unittest.TestCase):
    def test_bank_is_deterministic_complete_and_split(self):
        self.assertTrue(validate_bank())
        self.assertEqual(bank_identity(),bank_identity(tuple(TASKS)))
        self.assertEqual({t.domain for t in TASKS if t.split=="practice"},
                         {t.domain for t in TASKS if t.split=="holdout"})
        self.assertEqual(len(TASKS),14)

    def test_holdout_reference_never_leaks_into_practice_prompt(self):
        for task in TASKS:
            if task.split!="holdout":
                continue
            prompt=practice_context(task.domain,task_id=task.task_id)
            self.assertIn(task.question,prompt)
            self.assertNotIn("New question: "+task.question+"\nReference answer:",prompt)
            self.assertNotIn("New question: "+task.question+"\n"+task.reference,prompt)
            with self.assertRaises(ValueError):
                practice_feedback(task.task_id,task.reference)
        with self.assertRaises(ValueError):
            practice_context("arithmetic",task_id="arith.practice.1")

    def test_exact_scoring_and_no_false_mastery(self):
        response=score_answer("arith.holdout.1","91")
        self.assertTrue(response["correct"])
        self.assertEqual(response["response_sha256"],sha256(b"91").hexdigest())
        self.assertFalse(response["model_weights_updated"])
        self.assertFalse(response["mastery_qualified"])
        self.assertFalse(score_answer("arith.holdout.1","The answer is 91")["correct"])
        self.assertFalse(score_answer("arith.holdout.1","92")["correct"])
        with self.assertRaises(ValueError):
            score_answer("arith.holdout.1","")

    def test_complete_heldout_scoring_and_missing_not_counted_as_correct(self):
        responses={item.task_id:item.reference for item in TASKS if item.split=="holdout"}
        result=evaluate_holdout(responses)
        self.assertEqual(result["correct_count"],len(responses))
        self.assertEqual(result["observed_count"],len(responses))
        self.assertEqual(result["missing_count"],0)
        self.assertFalse(result["model_weights_updated"])
        self.assertFalse(result["model_quality_qualified"])
        partial=evaluate_holdout({"arith.holdout.1":"wrong"})
        self.assertEqual(partial["correct_count"],0)
        self.assertEqual(partial["observed_count"],1)
        self.assertGreater(partial["missing_count"],0)
        with self.assertRaises(ValueError):
            evaluate_holdout({"arith.practice.1":"72"})

    def test_fail_closed_corrupt_or_duplicate_bank(self):
        with self.assertRaises(ValueError):
            validate_bank(TASKS+(TASKS[0],))
        with self.assertRaises(ValueError):
            validate_bank((replace(TASKS[0],split="holdout"),)+TASKS[1:])
        with self.assertRaises(ValueError):
            validate_bank((replace(TASKS[0],task_id="../bad"),)+TASKS[1:])

    def test_practice_feedback_is_training_data_not_a_model_update(self):
        result=practice_feedback("arith.practice.1","72")
        self.assertTrue(result["correct"])
        self.assertEqual(result["reference"],"72")
        self.assertTrue(result["teaching_only"])
        self.assertFalse(result["model_weights_updated"])


if __name__=="__main__":
    unittest.main(verbosity=2)
