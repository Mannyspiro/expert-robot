"""Public receipt, fresh-key replay and failure codes for the offline research command."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
COMMAND = runpy.run_path(str(ROOT / "scripts/merlin/measure_titan_board_pq.py"))


class TitanBoardMeasurementTest(unittest.TestCase):
    def call(self, args):
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = COMMAND["main"](args)
        return code, json.loads(stdout.getvalue())

    def test_fresh_keys_reproduce_stable_public_fields(self):
        measured = COMMAND["measure"]()
        again = COMMAND["measure"]()
        self.assertTrue(COMMAND["same_measurement"](measured, again))
        self.assertTrue(all(value is True for value in measured["checks"].values()))
        self.assertEqual(set(measured), {"schema", "scope", "versions", "checks", "wire_lengths_bytes", "timing"})
        self.assertEqual(set(measured["wire_lengths_bytes"]), {"padding_bucket", "modern_envelope", "legacy_envelope"})
        self.assertEqual(measured["wire_lengths_bytes"]["modern_envelope"], measured["wire_lengths_bytes"]["legacy_envelope"])

    def test_comparison_rejects_changes_to_flags_versions_lengths_and_schema(self):
        original = COMMAND["measure"]()
        for key, field, changed in (("checks", "backend_roundtrip", 1), ("versions", "suite", "other"),
                                    ("wire_lengths_bytes", "modern_envelope", 0)):
            with self.subTest(key=key):
                modified = deepcopy(original)
                modified[key][field] = changed
                self.assertFalse(COMMAND["same_measurement"](original, modified))
        self.assertFalse(COMMAND["same_measurement"](original, {"checks": original["checks"]}))
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "bad.json"
            path.write_text(json.dumps(modified))
            code, result = self.call(["--compare", str(path)])
        self.assertEqual(code, 1)
        self.assertEqual(result["checks"], {"comparison_match": False})

    def test_unsupported_backend_exit_code_without_sensitive_diagnostics(self):
        pq = COMMAND["pq"]
        with patch.object(pq, "backend_status", return_value={"available": False}):
            code, result = self.call([])
        self.assertEqual(code, 2)
        self.assertEqual(result["checks"], {"supported_backend": False})
        with patch.object(pq, "generate_recipient_keypair", side_effect=ValueError("private test diagnostic")):
            code, result = self.call([])
        self.assertEqual(code, 1)
        self.assertEqual(result["checks"], {"completed": False})
        self.assertNotIn("private test diagnostic", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
