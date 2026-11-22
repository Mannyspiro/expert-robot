"""Regression tests for read-only hybrid host readiness checks."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from merlin_hybrid_preflight import inspect


class HybridPreflightTests(unittest.TestCase):
    def test_missing_checkout_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = inspect(Path(directory))
            self.assertFalse(result["ready"])
            self.assertFalse(result["checks"]["checkout"])

    def test_revision_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = inspect(Path(directory), "0" * 40)
            self.assertFalse(result["checks"]["expected_sha_matches"])

    def test_dns_unavailable_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("merlin_hybrid_preflight.socket.getaddrinfo",
                       side_effect=OSError("offline")):
                result = inspect(Path(directory))
            self.assertFalse(result["checks"]["dns_github.com"])
            self.assertFalse(result["checks"]["dns_gitlab.com"])


if __name__ == "__main__":
    unittest.main()
