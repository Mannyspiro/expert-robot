"""Offline negative controls for optional live public HTTPS source acceptance."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import merlin_public_https_acceptance as module
from public_web import PublicWebError


def response():
    body = b"from fractions import Fraction\nclass Fraction:\n    pass\n"
    return {"body": body, "status": 200, "final_url": module.URL,
            "retrieval_kind": "https_http", "content_type": "text/x-python",
            "sha256": hashlib.sha256(body).hexdigest(),
            "network_bytes": len(body), "redirects": []}


class LiveReceiptTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.output = Path(temp.name) / "receipt"

    def test_exact_raw_bytes_and_receipt_scope(self):
        data = response()
        # Valid measured body must include source marker and >=200 bytes.
        data["body"] += b"# documented fixture\n" * 12
        data["sha256"] = hashlib.sha256(data["body"]).hexdigest()
        data["network_bytes"] = len(data["body"])
        observed = module.record(self.output, data, commit="a" * 40)
        self.assertEqual(observed["raw_sha256"], data["sha256"])
        self.assertEqual((self.output / observed["raw_path"]).read_bytes(), data["body"])
        self.assertEqual(json.loads((self.output / "receipt.json").read_text()), observed)
        self.assertFalse(observed["browser_rendering_performed"])
        self.assertFalse(observed["domain_ownership_or_scientific_truth_verified"])
        self.assertFalse(observed["promotion_authority"])
        self.assertEqual(observed["external_spend_usd"], 0)

    def test_wrong_source_or_hash_fails_before_success_receipt(self):
        data = response()
        body = data["body"] + b"padding\n" * 40
        for mutation in ({"status": 403}, {"final_url": "https://evil.example/"},
                         {"sha256": "f" * 64}, {"retrieval_kind": "rendered_browser"},
                         {"redirects": [{"location": "x"}]},
                         {"body": b"!" + body[1:]}):
            with self.subTest(mutation=mutation):
                invalid = {**data, "body": body, "sha256": hashlib.sha256(body).hexdigest(),
                           "network_bytes": len(body), **mutation}
                with self.assertRaises(ValueError):
                    module.record(self.output, invalid, commit="a" * 40)
                self.assertFalse((self.output / "receipt.json").exists())

    def test_too_short_or_oversize_refused(self):
        sample = response()
        for body in (b"class Fraction", b"class Fraction\n" + b"x" * module.LIMIT):
            with self.subTest(size=len(body)):
                candidate = {**sample, "body": body,
                             "sha256": hashlib.sha256(body).hexdigest(),
                             "network_bytes": len(body)}
                with self.assertRaises(ValueError):
                    module.record(self.output, candidate, commit="a" * 40)

    def test_live_network_arguments_are_strict_and_one_attempt(self):
        data = response()
        data["body"] += b"# note\n" * 50
        data["sha256"] = hashlib.sha256(data["body"]).hexdigest()
        data["network_bytes"] = len(data["body"])
        with patch.object(module, "source_commit", return_value="a" * 40), \
             patch.object(module, "PublicWebFetcher") as fetcher:
            fetcher.return_value.fetch.return_value = data
            result = module.live(self.output)
        fetcher.return_value.fetch.assert_called_once_with(
            module.URL, max_bytes=module.LIMIT, timeout=20, max_redirects=0)
        self.assertTrue(result["source_observed"])
        self.assertFalse((self.output / "failure.json").exists())

    def test_network_failure_is_retained_not_success(self):
        with patch.object(module, "source_commit", return_value="a" * 40), \
             patch.object(module, "PublicWebFetcher") as fetcher:
            fetcher.return_value.fetch.side_effect = PublicWebError(
                "tls_failed", "TLS failure", status=None)
            with self.assertRaises(PublicWebError):
                module.live(self.output)
        failure = json.loads((self.output / "failure.json").read_text())
        self.assertEqual(failure["error_code"], "tls_failed")
        self.assertFalse(failure["source_observed"])
        self.assertFalse((self.output / "receipt.json").exists())
        self.assertFalse((self.output / "public-source-raw.py.txt").exists())

    def test_changed_ci_source_is_rejected(self):
        with patch.object(module, "subprocess") as process, \
             patch.object(module.os, "environ", {"MERLIN_EXPECTED_SHA": "b" * 40}):
            process.run.return_value = type("Completed", (), {
                "returncode": 0, "stdout": "a" * 40 + "\n"})()
            with self.assertRaises(RuntimeError):
                module.source_commit()

    def test_invalid_result_preserves_failure_without_raw_evidence(self):
        bad = response()
        with patch.object(module, "source_commit", return_value="a" * 40), \
             patch.object(module, "PublicWebFetcher") as fetcher:
            fetcher.return_value.fetch.return_value = bad
            with self.assertRaises(ValueError):
                module.live(self.output)
        self.assertTrue((self.output / "failure.json").exists())
        self.assertFalse((self.output / "receipt.json").exists())

    def test_output_rewrite_is_atomic_and_latest_bytes_match(self):
        body = b"class Fraction\n" + b"x" * 200
        data = {**response(), "body": body,
                "sha256": hashlib.sha256(body).hexdigest(),
                "network_bytes": len(body)}
        first = module.record(self.output, data, commit="a" * 40)
        second = module.record(self.output, data, commit="a" * 40)
        self.assertEqual(first["raw_sha256"], second["raw_sha256"])
        self.assertEqual((self.output / "public-source-raw.py.txt").read_bytes(), body)


if __name__ == "__main__":
    unittest.main()
