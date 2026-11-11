import json
import os
import unittest
from threading import Barrier
from unittest.mock import patch

from python.merlin import council_runtime


class FakeResponse:
    def __init__(self, persona_name):
        self.payload = json.dumps({
            "model": "test-local-model",
            "choices": [{"message": {"content": f"{persona_name}: independent assessment."}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8},
        }).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.payload[:size]


class CouncilRuntimeTests(unittest.TestCase):
    def test_model_must_be_qualified(self):
        with patch.dict(os.environ, {"MERLIN_MODEL_QUALIFIED": "0"}, clear=False):
            with self.assertRaises(RuntimeError):
                council_runtime.run_local_council("Test")

    def test_openings_are_isolated_then_cross_examined(self):
        calls = []

        def fake_urlopen(request, timeout=0):
            payload = json.loads(request.data)
            user = payload["messages"][1]["content"]
            calls.append(user)
            persona_name = payload["messages"][0]["content"].split('"title": "')[1].split('"')[0]
            return FakeResponse(persona_name)

        with patch.dict(os.environ, {
            "MERLIN_MODEL_QUALIFIED": "1",
            "MERLIN_MODEL_URL": "http://127.0.0.1:8080/v1/chat/completions",
            "MERLIN_MODEL_NAME": "test-local-model",
        }, clear=False), patch.object(council_runtime, "urlopen", side_effect=fake_urlopen):
            result = council_runtime.run_local_council("Should we use adaptive routing?", rounds=2)

        self.assertEqual(len(result["opening_positions"]), 6)
        self.assertEqual(len(result["cross_examination"]), 6)
        self.assertEqual(len(calls), 12)
        self.assertTrue(all("OTHER COUNCIL OPENING POSITIONS" not in call for call in calls[:6]))
        self.assertTrue(all("OTHER COUNCIL OPENING POSITIONS" in call for call in calls[6:]))
        self.assertFalse(result["promotion_authorized"])
        self.assertFalse(result["authority_expansion"])

    def test_opening_seats_execute_concurrently(self):
        barrier = Barrier(6)

        def fake_urlopen(request, timeout=0):
            barrier.wait(timeout=2)
            payload = json.loads(request.data)
            persona_name = payload["messages"][0]["content"].split('"title": "')[1].split('"')[0]
            return FakeResponse(persona_name)

        with patch.dict(os.environ, {
            "MERLIN_MODEL_QUALIFIED": "1",
            "MERLIN_MODEL_URL": "http://127.0.0.1:8080/v1/chat/completions",
            "MERLIN_MODEL_NAME": "test-local-model",
        }, clear=False), patch.object(council_runtime, "urlopen", side_effect=fake_urlopen):
            result = council_runtime.run_local_council("Test", max_concurrency=6)

        self.assertEqual(len(result["opening_positions"]), 6)
        self.assertTrue(all(row["status"] == "completed" for row in result["opening_positions"]))

    def test_one_failed_seat_does_not_erase_other_openings(self):
        def fake_urlopen(request, timeout=0):
            payload = json.loads(request.data)
            title = payload["messages"][0]["content"].split('"title": "')[1].split('"')[0]
            if title == "Skeptic":
                raise OSError("simulated provider failure")
            return FakeResponse(title)

        events = []
        with patch.dict(os.environ, {
            "MERLIN_MODEL_QUALIFIED": "1",
            "MERLIN_MODEL_URL": "http://127.0.0.1:8080/v1/chat/completions",
            "MERLIN_MODEL_NAME": "test-local-model",
        }, clear=False), patch.object(council_runtime, "urlopen", side_effect=fake_urlopen):
            result = council_runtime.run_local_council("Test", event_sink=events.append)

        self.assertEqual(len(result["opening_positions"]), 6)
        self.assertEqual(result["failed_seats"], 1)
        self.assertEqual(sum(row["status"] == "completed" for row in result["opening_positions"]), 5)
        self.assertTrue(any(event["kind"] == "seat.failed" for event in events))

    def test_concurrency_is_bounded(self):
        with patch.dict(os.environ, {"MERLIN_MODEL_QUALIFIED": "1"}, clear=False):
            with self.assertRaises(ValueError):
                council_runtime.run_local_council("Test", max_concurrency=7)

    def test_remote_endpoint_is_rejected(self):
        with patch.dict(os.environ, {
            "MERLIN_MODEL_QUALIFIED": "1",
            "MERLIN_MODEL_URL": "https://provider.example/v1/chat/completions",
        }, clear=False):
            with self.assertRaises(ValueError):
                council_runtime.run_local_council("Test")


if __name__ == "__main__":
    unittest.main()
