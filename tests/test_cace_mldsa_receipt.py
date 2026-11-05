from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from merlin.cace_mldsa_receipt import CaceMldsaReceiptVerifier


CACE_SHA = "d1b7b9c47a222f25fd4bda5318a29d285e164c8d"
SOURCE_SHA = "8e40cb034864f80e58aef7602c4cc4dd1e41ed57"
PROVIDER_SHA = "5a1a854b0dc9f2141bdc771c555ee60c37950183"
VECTOR_SHA = "b121fee031dc65d32c96f4109a42a10dacbe2076"
ARTIFACT = b"exact Titan evidence bytes\n"
ARTIFACT_SHA = hashlib.sha256(ARTIFACT).hexdigest()
BUNDLE_SHA = "a" * 64
VERIFIER_ID = "cace-oci-a1"
KEY_ID = "ml-dsa-65:" + "b" * 64


class CaceMldsaReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cace = self.root / "Cace-app"
        (self.cace / "scripts").mkdir(parents=True)
        (self.cace / "cace_studio").mkdir()
        (self.cace / "scripts" / "verify_titan_bundle.py").write_text("# fixture\n")
        (self.cace / "cace_studio" / "attest_cli.py").write_text("# fixture\n")
        self.artifact_root = self.root / "artifact-root"
        self.artifact_root.mkdir()
        (self.artifact_root / "result.json").write_bytes(ARTIFACT)
        self.bundle_path = self.root / "bundle.json"
        self.attestation_path = self.root / "attestation.json"
        self.bundle_path.write_text(json.dumps({
            "cli_schema": 1,
            "command": "titan-bundle",
            "proof_effect": "none",
            "bundle_sha256": BUNDLE_SHA,
            "bundle": {
                "schema": "cace-evidence-bundle-v1",
                "bindings": {
                    "source_repository": "Mannyspiro/expert-robot",
                    "source_commit_sha": SOURCE_SHA,
                    "workflow_run_id": 42090360334,
                    "provider_commit": PROVIDER_SHA,
                    "vector_source_commit": VECTOR_SHA,
                    "verification_scope": "selected ACVP vectors",
                },
                "artifacts": [{
                    "artifact_id": "titan-result",
                    "sha256": ARTIFACT_SHA,
                    "size_bytes": len(ARTIFACT),
                    "role": "execution-result",
                    "media_type": "application/json",
                    "path": "result.json",
                    "metadata": {},
                }],
            },
        }), encoding="utf-8")
        self.attestation_path.write_text(json.dumps({
            "cli_schema": 1,
            "command": "pqc-sign",
            "proof_effect": "none",
            "attestation": {
                "schema": "cace-signed-attestation-v2",
                "signature_algorithm": "ML-DSA-65",
                "proof_effect": "none",
                "canonicalization": "sha256/cace-canonical-json-v1",
                "domain_separator": "CACE:TITAN:SIGNED-ATTESTATION:v2\\u0000",
                "statement_sha256": "c" * 64,
                "statement": {
                    "schema": "cace-attestation-statement-v2",
                    "signature_algorithm": "ML-DSA-65",
                    "proof_effect": "none",
                    "verifier_id": VERIFIER_ID,
                    "verifier_key_id": KEY_ID,
                    "claim_id": "titan:avrea:42090360334",
                    "bundle_sha256": BUNDLE_SHA,
                    "created_at_utc": "2026-11-05T19:30:00Z",
                    "purpose": "independent-reproduction",
                    "bindings": {
                        "source_repository": "Mannyspiro/expert-robot",
                        "source_commit_sha": SOURCE_SHA,
                        "workflow_run_id": 42090360334,
                        "provider_commit": PROVIDER_SHA,
                        "vector_source_commit": VECTOR_SHA,
                        "verification_scope": "selected ACVP vectors",
                    },
                },
                "public_key_b64": "cHVibGlj",
                "signature_b64": "c2lnbmF0dXJl",
            },
        }), encoding="utf-8")
        self.source_check = lambda repository, sha: repository == "Mannyspiro/expert-robot" and sha == SOURCE_SHA
        self.verifier = CaceMldsaReceiptVerifier(
            cace_root=self.cace,
            cace_commit_sha=CACE_SHA,
            trusted_verifier_id=VERIFIER_ID,
            trusted_key_id=KEY_ID,
            source_commit_verifier=self.source_check,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run(self, command, **kwargs):
        if command[:4] == ["git", "-C", str(self.cace), "rev-parse"]:
            return SimpleNamespace(returncode=0, stdout=CACE_SHA + "\n", stderr="")
        if "scripts/verify_titan_bundle.py" in command:
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "valid": True, "bundle_sha256": BUNDLE_SHA,
                "proof_effect": "none", "qualification_effect": "none",
            }), stderr="")
        if "-m" in command and "cace_studio.attest_cli" in command:
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "valid": True, "verifier_key_id": KEY_ID,
                "bundle_sha256": BUNDLE_SHA,
                "claim_id": "titan:avrea:42090360334",
            }), stderr="")
        raise AssertionError("unexpected subprocess command: " + repr(command))

    def _verify(self):
        with patch("merlin.cace_mldsa_receipt.subprocess.run", side_effect=self._run):
            return self.verifier.verify_artifact_receipt(
                bundle_path=self.bundle_path,
                artifact_root=self.artifact_root,
                attestation_path=self.attestation_path,
                repository="Mannyspiro/expert-robot",
                commit_sha=SOURCE_SHA,
                workflow_run_id=42090360334,
                provider_commit=PROVIDER_SHA,
                vector_source_commit=VECTOR_SHA,
                verification_scope="selected ACVP vectors",
                claim_id="titan:avrea:42090360334",
                artifact_sha256=ARTIFACT_SHA,
                artifact_kind="acvp-evidence",
                artifact_schema="titan-pqc-acvp-evidence/1",
                logical_path="result.json",
                requester_id="merlin-hermes",
            )

    def test_verifies_exact_cace_bundle_signature_and_source_binding(self):
        receipt = self._verify()
        self.assertEqual(receipt["signature_status"], "verified")
        self.assertEqual(receipt["verification_status"], "inconclusive")
        self.assertTrue(receipt["source_commit_verified"])
        self.assertTrue(receipt["artifact_digest_verified"])
        self.assertFalse(receipt["artifact_schema_validated"])
        self.assertFalse(receipt["artifact_content_verified"])
        self.assertFalse(receipt["promotion_authority"])
        self.assertEqual(receipt["bundle_sha256"], BUNDLE_SHA)
        body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
        self.assertEqual(receipt["receipt_sha256"], hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        ).hexdigest())

    def test_rejects_untrusted_verifier_key_before_cli_call(self):
        doc = json.loads(self.attestation_path.read_text())
        doc["attestation"]["statement"]["verifier_key_id"] = "ml-dsa-65:" + "0" * 64
        self.attestation_path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, "key is not trusted"):
            with patch("merlin.cace_mldsa_receipt.subprocess.run", side_effect=self._run):
                self._verify()

    def test_rejects_bundle_artifact_digest_mismatch(self):
        doc = json.loads(self.bundle_path.read_text())
        doc["bundle"]["artifacts"][0]["sha256"] = "0" * 64
        self.bundle_path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, "matching subject artifact"):
            with patch("merlin.cace_mldsa_receipt.subprocess.run", side_effect=self._run):
                self._verify()

    def test_rejects_unverified_source_commit(self):
        self.verifier = CaceMldsaReceiptVerifier(
            cace_root=self.cace,
            cace_commit_sha=CACE_SHA,
            trusted_verifier_id=VERIFIER_ID,
            trusted_key_id=KEY_ID,
            source_commit_verifier=lambda *_: False,
        )
        with self.assertRaisesRegex(ValueError, "source repository commit"):
            self._verify()


if __name__ == "__main__":
    unittest.main()
