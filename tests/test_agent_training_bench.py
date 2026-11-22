"""Focused offline tests for synthetic practice/heldout competency scoring."""
import unittest
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin.agent_practice_runtime import local_endpoint, paired_probe, request_local_model, main
from merlin.agent_training_bench import (
    TASKS, Task, bank_identity, evaluate_holdout, practice_context,
    practice_feedback, score_answer, validate_bank, compare_practice_effect
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
            validate_bank(tuple(t for t in TASKS if not (t.domain=="arithmetic" and t.split=="practice")))
        with self.assertRaises(ValueError):
            validate_bank((replace(TASKS[0],task_id="../bad"),)+TASKS[1:])

    def test_paired_holdout_tracks_gains_and_regressions_without_mastery_claim(self):
        baseline={t.task_id:"wrong" for t in TASKS if t.split=="holdout"}
        practiced=dict(baseline)
        practiced["arith.holdout.1"]="91"
        practiced["dc.holdout.1"]="2.5"
        result=compare_practice_effect(baseline,practiced)
        self.assertEqual(result["delta_correct"],2)
        self.assertEqual(result["improved_case_ids"],["arith.holdout.1","dc.holdout.1"])
        self.assertEqual(result["regressed_case_ids"],[])
        self.assertFalse(result["model_weights_updated"])
        self.assertFalse(result["mastery_qualified"])
        baseline["arith.holdout.1"]="91"
        practiced["arith.holdout.1"]="wrong"
        changed=compare_practice_effect(baseline,practiced)
        self.assertIn("arith.holdout.1",changed["regressed_case_ids"])
        with self.assertRaises(ValueError):
            compare_practice_effect({},practiced)
        with self.assertRaises(ValueError):
            compare_practice_effect(baseline,{"x":"invalid"})

    def test_runtime_loopback_endpoint_is_fixed_and_rejects_remote(self):
        self.assertEqual(local_endpoint("http://localhost:8772/v1/chat/completions"),
                         ("127.0.0.1",8772,"/v1/chat/completions"))
        for url in ("https://localhost:8772/v1/chat/completions",
                    "http://127.0.0.2:8772/v1/chat/completions",
                    "http://example.com:8772/v1/chat/completions",
                    "http://localhost:8772/admin",
                    "http://localhost:8772/v1/chat/completions?token=secret",
                    "http://localuser@localhost:8772/v1/chat/completions"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    local_endpoint(url)

    def test_runtime_paired_probe_uses_only_practice_and_heldout_prompts(self):
        seen=[]
        holdout={item.question:item.reference for item in TASKS if item.split=="holdout"}
        def fake_model(prompt):
            seen.append(prompt)
            if prompt in holdout:
                return "wrong"
            target=prompt.partition("New question: ")[2]
            self.assertIn(target,holdout)
            return holdout[target]
        result=paired_probe(fake_model,model_identity="synthetic-model",max_seconds=5)
        self.assertEqual(result["model_calls_observed"],14)
        self.assertEqual(result["delta_correct"],7)
        self.assertFalse(result["model_weights_updated"])
        self.assertFalse(result["model_quality_qualified"])
        self.assertEqual(len(seen),14)
        with self.assertRaises(ValueError):
            paired_probe(fake_model,model_identity="bad identity !")

    def test_runtime_fails_closed_on_bad_model_output(self):
        with self.assertRaises(ValueError):
            paired_probe(None,model_identity="local")
        with self.assertRaises(Exception):
            paired_probe(lambda prompt:None,model_identity="local",max_seconds=5)
        with self.assertRaises(ValueError):
            request_local_model("http://localhost:8772/v1/chat/completions",
                                "local","x",timeout_seconds=0)

    def test_cli_fails_closed_without_explicit_model_identity_and_run(self):
        from contextlib import redirect_stderr
        from io import StringIO
        with redirect_stderr(StringIO()) as error:
            result=main(["--endpoint","http://localhost:8772/v1/chat/completions",
                         "--model-sha256","a"*64])
        self.assertEqual(result,2)
        self.assertIn('"status": "blocked"',error.getvalue())
        with redirect_stderr(StringIO()) as error:
            result=main(["--endpoint","http://example.com:8772/v1/chat/completions",
                         "--model-sha256","a"*64,"--run"])
        self.assertEqual(result,2)
        self.assertIn('"production_qualified": false',error.getvalue())

    def test_practice_feedback_is_training_data_not_a_model_update(self):
        result=practice_feedback("arith.practice.1","72")
        self.assertTrue(result["correct"])
        self.assertEqual(result["reference"],"72")
        self.assertTrue(result["teaching_only"])
        self.assertFalse(result["model_weights_updated"])


if __name__=="__main__":
    unittest.main(verbosity=2)
