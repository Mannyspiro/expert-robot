"""Real-model discovery uses the configured deadline, not an impossible 3s cap."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"portable"/"merlin_studio"))
from model import LocalModel


class ProbeTimeoutTests(unittest.TestCase):
    def test_probe_with_default_settings_uses_bounded_ten_seconds(self):
        m=LocalModel({"model_url":"http://127.0.0.1:8772/v1/chat/completions",
                      "model_timeout_seconds":45})
        with patch.object(m,"_request",return_value={"data":[{"id":"local"}]}) as req:
            self.assertTrue(m.probe()["reachable"])
            self.assertEqual(req.call_args.kwargs["timeout"],10)

    def test_probe_respects_smaller_configured_deadline(self):
        m=LocalModel({"model_url":"http://127.0.0.1:8772/v1/chat/completions",
                      "model_timeout_seconds":10})
        with patch.object(m,"_request",return_value={"data":[{"id":"local"}]}) as req:
            self.assertTrue(m.probe()["reachable"])
            self.assertEqual(req.call_args.kwargs["timeout"],10)

    def test_no_model_never_claims_ready(self):
        m=LocalModel({"model_url":"http://127.0.0.1:8772/v1/chat/completions",
                      "model_timeout_seconds":45})
        with patch.object(m,"_request",return_value={"data":[]}):
            self.assertFalse(m.probe()["reachable"])


if __name__=="__main__":
    unittest.main()
