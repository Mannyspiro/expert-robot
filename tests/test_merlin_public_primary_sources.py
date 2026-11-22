"""Offline negative and positive controls for live-source receipt reconciliation.

These are synthetic bytes. They cannot authenticate a live website, native
Chromium, model answer, or evidence provenance outside the fixture.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from merlin_public_https_acceptance import SOURCES, acquire
from merlin_cited_research_cycle import CitedEvidenceError, assess


def fixture_fetch(url, *, max_bytes, timeout, max_redirects):
    index = 1 if url == SOURCES[0][1] else 2
    body = ("<html><head><title>Test source</title></head><body>"
            "Synthetic original " + str(index) + ": "
            "example.com, example.net, and example.org"
            "</body></html>").encode("utf-8")
    assert max_bytes >= len(body)
    return {"url": url, "final_url": url, "status": 200,
            "content_type": "text/html", "body": body,
            "sha256": hashlib.sha256(body).hexdigest(),
            "text": body.decode("utf-8"), "redirects": [],
            "network_bytes": len(body), "retrieval_kind": "https_http"}


class ResearchSourceEvidenceTests(unittest.TestCase):
    def ready(self, root):
        source = root / "sources"
        result = acquire(source, fetch=fixture_fetch)
        self.assertEqual(result["status"], "passed")
        return source

    def test_positive_fixture_requires_two_sources_and_cites_both(self):
        with tempfile.TemporaryDirectory() as temp:
            evidence = assess(self.ready(Path(temp)))
            self.assertEqual(evidence["status"], "passed")
            self.assertEqual(len(evidence["sources"]), 2)
            self.assertEqual(evidence["model_calls"], 0)
            self.assertFalse(evidence["production_qualified"])
            self.assertNotEqual(evidence["sources"][0]["body_sha256"],
                                evidence["sources"][1]["body_sha256"])

    def test_body_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self.ready(Path(temp))
            (source / "source-1.bin").write_bytes(b"tampered original")
            with self.assertRaises(CitedEvidenceError):
                assess(source)

    def test_source_swap_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self.ready(Path(temp))
            report_path = source / "report.json"
            report = json.loads(report_path.read_text())
            report["records"][0]["body_file"] = "source-2.bin"
            report_path.write_text(json.dumps(report))
            with self.assertRaises(CitedEvidenceError):
                assess(source)

    def test_publisher_origin_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self.ready(Path(temp))
            report_path = source / "report.json"
            report = json.loads(report_path.read_text())
            report["records"][0]["final_url"] = "https://example.com/iana"
            report_path.write_text(json.dumps(report))
            with self.assertRaises(CitedEvidenceError):
                assess(source)

    def test_missing_source_record_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self.ready(Path(temp))
            report_path = source / "report.json"
            report = json.loads(report_path.read_text())
            report["records"].pop()
            report_path.write_text(json.dumps(report))
            with self.assertRaises(CitedEvidenceError):
                assess(source)

    def test_symlink_replacement_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self.ready(Path(temp))
            original = source / "source-1.bin"
            original.unlink()
            original.symlink_to(source / "source-2.bin")
            with self.assertRaises(CitedEvidenceError):
                assess(source)

    def test_unverified_token_absence_fails_without_qualification(self):
        def bad_fetch(url, **kwargs):
            result = fixture_fetch(url, **kwargs)
            if url == SOURCES[1][1]:
                return {**result, "text": "No domain examples in this source"}
            return result
        with tempfile.TemporaryDirectory() as temp:
            data = acquire(Path(temp) / "sources", fetch=bad_fetch)
            self.assertEqual(data["status"], "reference_disagrees")
            with self.assertRaises(CitedEvidenceError):
                assess(Path(temp) / "sources")

    def test_network_failure_retains_blocked_evidence_not_fixture_success(self):
        def failed(url, **kwargs):
            if url == SOURCES[1][1]:
                raise OSError("fixture forced second-source failure")
            return fixture_fetch(url, **kwargs)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "sources"
            data = acquire(folder, fetch=failed)
            self.assertEqual(data["status"], "blocked")
            self.assertEqual(len(data["records"]), 1)
            self.assertTrue((folder / "source-1.bin").is_file())
            with self.assertRaises(CitedEvidenceError):
                assess(folder)


if __name__ == "__main__":
    unittest.main(verbosity=2)
