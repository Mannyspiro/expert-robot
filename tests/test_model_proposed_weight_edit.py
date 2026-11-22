"""Regression tests for a detached, model-authored tiny tensor edit."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin import model_proposed_weight_edit as edits
from merlin.self_rewrite_lab import propose_self_repair, digest


class ModelProposalsTests(unittest.TestCase):
    def setUp(self):
        self.base=[[1.,0.],[0.,2.]]
        self.practice=[([0.,1.],[0.,1.]),([1.,0.],[1.,0.])]
        self.heldout=[([.5,.5],[.5,.5]),([1.,1.],[1.,1.])]
        self.proposal=propose_self_repair(self.base,self.practice)

    def test_model_authored_json_changes_only_detached_tiny_weights(self):
        receipt=edits.evaluate_proposal(
            json.dumps(self.proposal),self.base,self.practice,self.heldout)
        self.assertTrue(receipt["language_model_proposal_received"])
        self.assertTrue(receipt["actual_numeric_weights_changed"])
        self.assertTrue(receipt["candidate_accepted_for_research"])
        self.assertEqual(receipt["candidate_weights"],[[1.,0.],[0.,1.]])
        self.assertEqual(receipt["baseline_weight_sha256"],digest(self.base))
        self.assertEqual(self.base,[[1.,0.],[0.,2.]])
        self.assertFalse(receipt["merlin_gguf_weights_changed"])
        self.assertFalse(receipt["candidate_auto_promoted"])

    def test_prompt_exposes_only_training_not_heldout(self):
        message=edits.proposal_prompt(self.base,self.practice)
        payload=json.loads(message)
        self.assertEqual(payload["target"],"synthetic.output")
        self.assertEqual(payload["weight_sha256"],digest(self.base))
        self.assertIn("public_practice",payload)
        self.assertNotIn("heldout",payload)
        self.assertNotIn("candidate_weights",payload)
        self.assertNotIn(str(self.heldout[0]),message)

    def test_local_model_called_once_and_not_allowed_to_run_code(self):
        with patch.object(edits,"request_local_model",
                          return_value=json.dumps(self.proposal)) as mock:
            decision=edits.run_local_once(
                "http://127.0.0.1:8772/v1/chat/completions",
                "local",self.base,self.practice,self.heldout)
        self.assertEqual(mock.call_count,1)
        self.assertTrue(decision["candidate_accepted_for_research"])
        self.assertNotIn("tools",json.loads(mock.call_args.args[2]))
        bad={**self.proposal,"code":"os.system('echo hello')"}
        with self.assertRaises(ValueError):
            edits.evaluate_proposal(json.dumps(bad),self.base,self.practice,self.heldout)

    def test_untrusted_incorrect_direction_is_rejected_not_promoted(self):
        invalid={**self.proposal,"direction":[1.,0.]}
        receipt=edits.evaluate_proposal(json.dumps(invalid),
                                         self.base,self.practice,self.heldout)
        self.assertFalse(receipt["candidate_accepted_for_research"])
        self.assertFalse(receipt["production_qualified"])
        for value in ("garbage","{}",'{"schema":2}'," " * 4097):
            with self.subTest(value=value[:20]):
                with self.assertRaises(ValueError):
                    edits.evaluate_proposal(value,self.base,self.practice,self.heldout)


if __name__=="__main__":
    unittest.main(verbosity=2)
