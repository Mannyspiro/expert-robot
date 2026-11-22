"""VerifierBench-inspired calibration tests catch reject-all/accept-all judges."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin.verifier_calibration import VerificationCase, calibrate


CASES=[
    VerificationCase("arith.canonical","arith1","canonical_valid","42"),
    VerificationCase("arith.alternate","arith1","alternative_valid","042"),
    VerificationCase("arith.invalid","arith1","invalid","41"),
    VerificationCase("arith2.canonical","arith2","canonical_valid","6"),
    VerificationCase("arith2.alternate","arith2","alternative_valid","+6"),
    VerificationCase("arith2.invalid","arith2","invalid","9"),
]


class VerifierCalibrationTests(unittest.TestCase):
    def test_independently_valid_alternatives_must_be_accepted(self):
        def judge(task,answer):
            expected={"arith1":42,"arith2":6}[task]
            return answer.lstrip("+").isdigit() and int(answer)==expected
        result=calibrate(judge,CASES)
        self.assertEqual(result["true_positive"],4)
        self.assertEqual(result["true_negative"],2)
        self.assertEqual(result["false_negative"],0)
        self.assertEqual(result["false_positive"],0)
        self.assertEqual(result["valid_alternatives_rejected"],0)
        self.assertTrue(result["accepted_for_tested_cases"])
        self.assertFalse(result["validity_established_beyond_test_cases"])

    def test_reject_all_judge_is_not_mistaken_for_safe(self):
        result=calibrate(lambda task,candidate:False,CASES)
        self.assertEqual(result["true_negative"],2)
        self.assertEqual(result["false_negative"],4)
        self.assertEqual(result["valid_alternatives_rejected"],2)
        self.assertFalse(result["accepted_for_tested_cases"])
        self.assertEqual(result["balanced_accuracy"],.5)

    def test_overly_strict_verifier_rejects_valid_alternatives(self):
        result=calibrate(
            lambda task,candidate:candidate=={"arith1":"42","arith2":"6"}[task],CASES)
        self.assertEqual(result["valid_alternatives_rejected"],2)
        self.assertEqual(result["false_positive"],0)
        self.assertFalse(result["accepted_for_tested_cases"])

    def test_accept_all_and_wrong_verifiers_are_rejected(self):
        result=calibrate(lambda task,candidate:True,CASES)
        self.assertEqual(result["false_positive"],2)
        self.assertFalse(result["accepted_for_tested_cases"])
        with self.assertRaises(ValueError):
            calibrate(lambda task,candidate:"True",CASES)
        with self.assertRaises(RuntimeError):
            calibrate(lambda task,candidate:1/0,CASES)

    def test_missing_negatives_and_duplicated_cases_are_rejected(self):
        with self.assertRaises(ValueError):
            calibrate(lambda task,candidate:True,CASES[:2]+CASES[3:5])
        with self.assertRaises(ValueError):
            calibrate(lambda task,candidate:True,CASES+[CASES[0]])
        with self.assertRaises(ValueError):
            calibrate(lambda task,candidate:True,CASES[:2])
        with self.assertRaises(ValueError):
            calibrate(lambda task,candidate:True,[*CASES, "invalid case"])


if __name__=="__main__":
    unittest.main(verbosity=2)
