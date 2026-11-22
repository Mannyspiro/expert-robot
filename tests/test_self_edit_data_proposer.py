"""Model-authored candidate arithmetic examples require independent oracle."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin.self_edit_data_proposer import (
    proposal_prompt, verify_proposal, write_verified_train_json
)


class ProposedDataTests(unittest.TestCase):
    def setUp(self):
        self.body = {
            "schema":"merlin-arithmetic-candidate/1",
            "examples":[
                {"operator":"mul","a":7,"b":13,"answer":91},
                {"operator":"sub","a":4,"b":9,"answer":-5},
                {"operator":"add","a":21,"b":22,"answer":43},
            ],
        }

    def payload(self):
        return json.dumps(self.body,separators=(",",":"))

    def test_self_proposal_is_recomputed_not_trusted(self):
        checked=verify_proposal(self.payload())
        self.assertEqual(checked["accepted_count"],3)
        self.assertTrue(checked["training_rows"][0]["question"].startswith("Compute 7 times 13"))
        self.assertFalse(checked["model_weights_updated"])
        self.assertIn("heldout_labels_exposed_to_proposer",checked)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"candidate-training.json"
            proof=write_verified_train_json(checked,path)
            self.assertEqual(proof["training_count"],3)
            self.assertEqual(len(json.loads(path.read_text())),3)
            with self.assertRaises(ValueError):
                write_verified_train_json(checked,path)

    def test_reject_wrong_oracle_label_and_untrusted_code(self):
        wrong=json.loads(self.payload())
        wrong["examples"][0]["answer"]=92
        with self.assertRaises(ValueError):
            verify_proposal(json.dumps(wrong))
        wrong=json.loads(self.payload())
        wrong["examples"][0]["python"]="import os"
        with self.assertRaises(ValueError):
            verify_proposal(json.dumps(wrong))
        wrong=json.loads(self.payload())
        wrong["examples"][1]["a"]=True
        with self.assertRaises(ValueError):
            verify_proposal(json.dumps(wrong))

    def test_heldout_and_duplicate_requests_rejected(self):
        with self.assertRaises(ValueError):
            verify_proposal(self.payload(),heldout_questions=[
                "Compute 7 times 13. Respond with only the integer."])
        wrong=json.loads(self.payload())
        wrong["examples"].append(dict(wrong["examples"][0]))
        with self.assertRaises(ValueError):
            verify_proposal(json.dumps(wrong))

    def test_modified_verification_report_cannot_poison_training_file(self):
        checked=verify_proposal(self.payload())
        checked["training_rows"][0]["answer"]="92"
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                write_verified_train_json(checked,Path(td)/"training.json")
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_reject_non_json_or_overlong_response(self):
        with self.assertRaises(ValueError):
            verify_proposal("not-json")
        with self.assertRaises(ValueError):
            verify_proposal(" " * 8193)


if __name__=="__main__":
    unittest.main(verbosity=2)
