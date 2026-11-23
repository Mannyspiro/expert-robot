"""Synthetic redacted source scanner controls; no real credentials are used."""
from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from merlin_source_secrets_audit import MAX_FILE, audit_paths


class SecretAuditTests(unittest.TestCase):
    def audit(self, values):
        return audit_paths(sorted(values), lambda path: values[path], source_sha="fixture")

    def test_clean_source_and_zip_are_accepted_without_claiming_secrets_absent(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("notes.txt", b"Untrusted public log, no credentials")
        report = self.audit({"docs/readme.md": b"Public information",
                             "docs/evidence/fixture.zip": archive.getvalue()})
        self.assertEqual(report["status"], "no_patterns_detected")
        self.assertEqual(report["zip_members_examined"], 1)
        self.assertFalse(report["secret_absence_proven"])

    def test_github_personal_access_token_match_is_redacted(self):
        candidate = b"gh" + b"p_" + b"A" * 36
        report = self.audit({"private.env": b"API_KEY=" + candidate})
        self.assertEqual(report["status"], "findings")
        self.assertEqual(report["findings"][0]["rule"], "github_classic")
        self.assertFalse(report["matched_bytes_emitted"])
        serialized = repr(report)
        self.assertNotIn(candidate.decode(), serialized)
        self.assertNotIn("API_KEY=", serialized)

    def test_gitlab_and_private_key_signatures_match_inside_zip_members(self):
        candidate = b"gl" + b"pat-" + b"B" * 24
        private = b"-----BEGIN " + b"PRIVATE KEY-----"  # fixture signature, not a key
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("dump.txt", candidate + b"\n" + private)
        report = self.audit({"docs/evidence/results.zip": archive.getvalue()})
        self.assertEqual(report["status"], "findings")
        self.assertEqual({f["rule"] for f in report["findings"]},
                         {"private_key", "gitlab_personal"})
        self.assertTrue(any("results.zip::dump.txt" in f["locator"] for f in report["findings"]))
        self.assertTrue(all(f["locator"] in ("docs/evidence/results.zip",
                         "docs/evidence/results.zip::dump.txt") for f in report["findings"]))
        # Uncompressed ZIP entries can carry a match both in raw ZIP bytes and
        # in the decoded member; this must not leak the actual matched text.
        self.assertNotIn(candidate.decode(), repr(report))

    def test_overlarge_path_and_invalid_source_are_audited_as_partial(self):
        report = self.audit({"huge.log": b"A" * (MAX_FILE + 1), "../private": b"X"})
        self.assertEqual(report["status"], "partial")
        self.assertTrue(report["omissions"])
        self.assertTrue(report["errors"])
        self.assertFalse(report["production_qualified"])

    def test_corrupt_zip_container_is_not_clean(self):
        report = self.audit({"bad.zip": b"PK\x03\x04bad"})
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["omissions"][0]["reason"], "invalid_zip_container")

    def test_oversize_member_is_reported_not_ignored(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("large.log", b"x" * (13 * 1024 * 1024))
        report = self.audit({"large.zip": archive.getvalue()})
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["zip_members_examined"], 0)
        self.assertIn("budget", report["omissions"][0]["reason"])

    def test_rule_names_not_actual_tokens_appear_in_audit(self):
        report = self.audit({"source.py": b"GH token patterns named github_classic and gitlab_personal"})
        self.assertEqual(report["status"], "no_patterns_detected")
        self.assertEqual(report["findings"], [])


    def test_gitlink_sources_record_external_commit_without_reading_code(self):
        from merlin_source_secrets_audit import gitlink_sources
        commit = "a" * 40
        stage = (b"100644 " + b"b" * 40 + b" 0\tREADME.md\0"
                 + b"160000 " + commit.encode() + b" 0\tthird_party/openbot\0")
        with patch("merlin_source_secrets_audit.subprocess.run",
                   return_value=SimpleNamespace(stdout=stage)) as run:
            links = gitlink_sources(Path("/synthetic-repo"))
        self.assertEqual(links, {"third_party/openbot": commit})
        self.assertEqual(run.call_args.args[0][-3:], ["ls-files", "--stage", "-z"])

    def test_gitlink_invalid_stage_or_digest_fails_closed(self):
        from merlin_source_secrets_audit import gitlink_sources
        for bad in (b"160000 " + b"z" * 40 + b" 0\tx\0",
                    b"160000 " + b"a" * 40 + b" 1\tx\0",
                    b"160000 " + b"a" * 39 + b" 0\tx\0"):
            with self.subTest(raw=bad), patch(
                "merlin_source_secrets_audit.subprocess.run",
                return_value=SimpleNamespace(stdout=bad),
            ):
                with self.assertRaises(ValueError):
                    gitlink_sources(Path("/synthetic-repo"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
