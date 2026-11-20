import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from merlin import council, council_runtime, science_visualizer


class ScientificVisualsTests(unittest.TestCase):
    def test_specialist_is_opt_in(self):
        default = council.build_deliberation_packets("Explain the series")
        specialist = council.build_deliberation_packets("Explain the series", visual_specialist_only=True)
        self.assertEqual(len(default), 6)
        self.assertEqual([p["persona"]["persona_id"] for p in specialist], ["visual_scientist"])

    def test_qualified_model_receives_exactly_one_specialist_packet(self):
        with patch.dict(os.environ, {"MERLIN_MODEL_QUALIFIED": "1",
                                     "MERLIN_MODEL_URL": "http://127.0.0.1/consult"}), \
             patch.object(council_runtime, "_model_call", return_value={"content": "design"}) as call:
            result = council_runtime.run_local_council("Imagine two encodings", visual_specialist_only=True)
        packet = call.call_args.args[2]
        self.assertEqual(packet["persona"]["persona_id"], "visual_scientist")
        self.assertEqual(call.call_count, 1)
        self.assertEqual(len(result["opening_positions"]), 1)
        self.assertFalse(result["authority_expansion"])

    def test_rejects_unplottable_data(self):
        fixture = Path(__file__).resolve().parents[1] / "examples/merlin/synthetic-cooling.json"
        series = json.loads(fixture.read_bytes())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "series.json"
            for invalid in (None, False, float("nan"), float("inf"), 2**54 + 1):
                with self.subTest(invalid=invalid):
                    series["samples"] = [[0, 1], [1, invalid]]
                    path.write_text(json.dumps(series))
                    with self.assertRaises(ValueError):
                        science_visualizer.load_series(path)
            series["samples"] = [[1, 2], [1, 3]]
            path.write_text(json.dumps(series))
            with self.assertRaisesRegex(ValueError, "strictly increase"):
                science_visualizer.load_series(path)

    def test_encoder_failure_leaves_output_available_for_retry(self):
        fixture = Path(__file__).resolve().parents[1] / "examples/merlin/synthetic-cooling.json"
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(science_visualizer, "render_video", side_effect=RuntimeError("encoder failed")):
            destination = Path(tmp) / "bundle"
            with self.assertRaises(RuntimeError):
                science_visualizer.render(fixture, destination)
            self.assertEqual(list(Path(tmp).iterdir()), [])
