"""Tests for content-addressed Merlin evidence receipts."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from merlin.equation_atlas.receipts import sha256

class EvidenceReceiptTests(unittest.TestCase):
    def test_sha256_matches_standard_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.txt"
            path.write_text("Merlin evidence", encoding="utf-8")
            expected = hashlib.sha256(b"Merlin evidence").hexdigest()
            self.assertEqual(sha256(path), expected)

if __name__ == "__main__":
    unittest.main()
