import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from python.merlin.cace_adapter import CaceVerificationAdapter
from python.merlin.cace_runtime import cace_verification_adapter_from_environment
from python.merlin.event_outbox import MerlinEventOutbox
from python.merlin.project_registry import MerlinRegistry


class CaceRuntimeCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = MerlinRegistry(root / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.outbox = MerlinEventOutbox(root / "outbox.sqlite3")
        private = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        self.public_pem = private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        raw = private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.key_id = "ed25519:" + __import__("hashlib").sha256(raw).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def test_absent_configuration_returns_unavailable_not_a_fake_adapter(self):
        with patch.dict(os.environ, {}, clear=True):
            result = cace_verification_adapter_from_environment(
                registry=self.registry, outbox=self.outbox
            )
        self.assertIsNone(result)

    def test_partial_endpoint_token_or_trust_configuration_fails_closed(self):
        with patch.dict(os.environ, {"CACE_VERIFY_URL": "https://cace.example/verify"}, clear=True):
            with self.assertRaisesRegex(ValueError, "must be configured together"):
                cace_verification_adapter_from_environment(
                    registry=self.registry, outbox=self.outbox
                )
        with patch.dict(os.environ, {
            "CACE_VERIFY_TRUSTED_KEYS_JSON": json.dumps({self.key_id: self.public_pem})
        }, clear=True):
            with self.assertRaisesRegex(ValueError, "transport is absent"):
                cace_verification_adapter_from_environment(
                    registry=self.registry, outbox=self.outbox
                )
        with patch.dict(os.environ, {
            "CACE_VERIFY_URL": "https://cace.example/verify",
            "CACE_VERIFY_TOKEN": "t" * 40,
        }, clear=True):
            with self.assertRaisesRegex(ValueError, "no trusted verifier keys"):
                cace_verification_adapter_from_environment(
                    registry=self.registry, outbox=self.outbox
                )

    def test_complete_configuration_builds_https_adapter_with_pinned_signer(self):
        env = {
            "CACE_VERIFY_URL": "https://cace.example/verify",
            "CACE_VERIFY_TOKEN": "t" * 40,
            "CACE_VERIFY_TRUSTED_KEYS_JSON": json.dumps({self.key_id: self.public_pem}),
        }
        with patch.dict(os.environ, env, clear=True):
            adapter = cace_verification_adapter_from_environment(
                registry=self.registry, outbox=self.outbox, opener=object()
            )
        self.assertIsInstance(adapter, CaceVerificationAdapter)
        self.assertEqual(adapter.trusted_verifier_keys, {self.key_id: self.public_pem})
        self.assertEqual(adapter.verify_transport.endpoint, "https://cace.example/verify")

    def test_trusted_key_id_must_match_the_pinned_public_key(self):
        env = {
            "CACE_VERIFY_TRUSTED_KEYS_JSON": json.dumps({"ed25519:" + "0" * 64: self.public_pem}),
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "does not match"):
                cace_verification_adapter_from_environment(
                    registry=self.registry, outbox=self.outbox
                )


if __name__ == "__main__":
    unittest.main()
