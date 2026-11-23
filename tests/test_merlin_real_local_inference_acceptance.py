"""Real inference acceptance negative controls, without pretending to run weights."""
from pathlib import Path
import importlib.util
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("real_inference",ROOT/"scripts"/"merlin_real_local_inference_acceptance.py")
assert SPEC and SPEC.loader
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class RealInferenceAcceptanceTests(unittest.TestCase):
    def test_nonloopback_endpoint_refused(self):
        for endpoint in ("https://example.com/v1/chat/completions",
                         "http://192.168.1.5:8772/v1/chat/completions",""):
            with self.subTest(endpoint=endpoint),self.assertRaises(ValueError):
                module.validate(endpoint,"local")

    def test_missing_model_refused_before_generation(self):
        with patch.object(module.LocalModel,"probe",return_value={
                "reachable":True,"models":[{"id":"other"}]}):
            with self.assertRaisesRegex(RuntimeError,"not advertised"):
                module.validate("http://127.0.0.1:8772/v1/chat/completions","local")

    def test_real_generation_protocol_requires_response(self):
        with patch.object(module.LocalModel,"probe",return_value={
                "reachable":True,"models":[{"id":"local"}]}),patch.object(
                module.LocalModel,"complete",return_value={"content":""}):
            with self.assertRaisesRegex(RuntimeError,"empty content"):
                module.validate("http://127.0.0.1:8772/v1/chat/completions","local")

    def test_mocked_generation_is_not_proof_of_real_weights(self):
        with patch.object(module.LocalModel,"probe",return_value={
                "reachable":True,"models":[{"id":"local"}]}),patch.object(
                module.LocalModel,"complete",return_value={"content":"READY fake"}):
            result=module.validate("http://127.0.0.1:8772/v1/chat/completions","local")
            self.assertFalse(result["actual_model_weights_verified_independently"])
            self.assertFalse(result["challenge_token_echoed"])
            self.assertFalse(result["production_qualified"])


if __name__=="__main__":
    unittest.main()
