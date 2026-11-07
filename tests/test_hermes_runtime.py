import json
import os
import tempfile
import time
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from python.merlin.hermes_runtime import build_merlin_hermes_runtime


class HermesRuntimeCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        private = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        public_pem = private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        raw = private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.key_id = "ed25519:" + __import__("hashlib").sha256(raw).hexdigest()
        self.trusted = {
            self.key_id: {
                "verifier_id": "cace:production-verifier",
                "public_key_pem": public_pem,
            }
        }

    def tearDown(self):
        self.temp.cleanup()

    def build(self):
        return build_merlin_hermes_runtime(
            root=Path(self.temp.name) / "runtime",
            project_id="merlin",
            project_name="Merlin",
            repository="Mannyspiro/expert-robot",
            commit_sha="a" * 40,
            requester_id="merlin:worker",
            research_executor=lambda task, context: {
                "artifact_bytes": b"research evidence",
                "summary": "Research artifact recorded",
                "metadata": {"tool_identity": "test-research-engine@1.0"},
            },
            proof_search_executor=lambda task, context: {
                "artifact_bytes": b"proof search evidence",
                "summary": "Proof-search artifact recorded",
                "metadata": {"tool_identity": "test-proof-search@1.0"},
            },
            approval_validator=lambda approval_ref, task: False,
            lease_validator=lambda lease_ref, budget: False,
            include_ngspice=False,
        )

    def test_composition_builds_real_worker_and_fails_closed_without_cace(self):
        with patch.dict(os.environ, {}, clear=True):
            runtime = self.build()
        self.assertIsNone(runtime.cace_adapter)
        self.assertEqual(runtime.health()["cace_verification"], "unavailable")
        self.assertFalse(runtime.health()["promotion_authority"])
        self.assertIn("research", runtime.worker.handlers)
        self.assertIn("proof_search", runtime.worker.handlers)
        self.assertTrue(runtime.start())
        deadline = time.monotonic() + 1
        while not runtime.health()["worker"]["ready"] and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(runtime.health()["worker"]["ready"])
        self.assertTrue(runtime.stop(timeout_seconds=1))

    def test_missing_approval_or_lease_validators_is_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "validators are required"):
                build_merlin_hermes_runtime(
                    root=Path(self.temp.name) / "invalid",
                    project_id="merlin", project_name="Merlin",
                    repository="owner/repo", commit_sha="a" * 40,
                    requester_id="merlin:worker",
                    research_executor=lambda task, context: {},
                    proof_search_executor=lambda task, context: {},
                    approval_validator=None, lease_validator=None,
                )

    def test_partial_cace_configuration_prevents_runtime_downgrade(self):
        with patch.dict(os.environ, {
            "CACE_VERIFY_URL": "https://cace.example/verify",
            "CACE_VERIFY_TOKEN": "t" * 40,
        }, clear=True):
            with self.assertRaisesRegex(ValueError, "no trusted verifier keys"):
                self.build()

    def test_runtime_health_endpoint_reports_cace_configuration_state(self):
        with patch.dict(os.environ, {}, clear=True):
            runtime = self.build()
        self.assertTrue(runtime.start())
        deadline = time.monotonic() + 1
        while not runtime.health()["worker"]["ready"] and time.monotonic() < deadline:
            time.sleep(0.01)
        store = EventStore(runtime.root / "events.sqlite3")
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(
                store,
                learning_outbox=runtime.outbox,
                canonical_registry=runtime.registry,
                canonical_graph=runtime.graph,
                hermes_worker_service=runtime.service,
                hermes_runtime=runtime,
            ),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(
                f"http://127.0.0.1:{server.server_port}/api/runtime/hermes",
                timeout=5,
            ) as response:
                health = json.loads(response.read())
            self.assertEqual(health["cace_verification"], "unavailable")
            self.assertTrue(health["worker"]["ready"])
            self.assertFalse(health["promotion_authority"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            self.assertTrue(runtime.stop(timeout_seconds=1))

    def test_api_server_owns_and_stops_injected_runtime(self):
        runtime = self.build()
        class FakeServer:
            def __init__(self, address, handler):
                self.address = address
                self.handler = handler
                self.closed = False

            def serve_forever(self):
                raise KeyboardInterrupt()

            def server_close(self):
                self.closed = True

        with patch("python.merlin.app.ThreadingHTTPServer", FakeServer):
            with patch("python.merlin.app._build_optional_hud_runtime", return_value=None):
                serve(
                    port=0,
                    db_path=str(runtime.root / "events.sqlite3"),
                    hermes_runtime=runtime,
                )
        self.assertEqual(runtime.health()["worker"]["status"], "stopped")

    def test_complete_cace_configuration_pins_verifier_identity(self):
        env = {
            "CACE_VERIFY_URL": "https://cace.example/verify",
            "CACE_VERIFY_TOKEN": "t" * 40,
            "CACE_VERIFY_TRUSTED_KEYS_JSON": json.dumps(self.trusted),
        }
        with patch.dict(os.environ, env, clear=True):
            runtime = build_merlin_hermes_runtime(
                root=Path(self.temp.name) / "configured",
                project_id="merlin", project_name="Merlin",
                repository="Mannyspiro/expert-robot", commit_sha="a" * 40,
                requester_id="merlin:worker",
                research_executor=lambda task, context: {},
                proof_search_executor=lambda task, context: {},
                approval_validator=lambda approval_ref, task: False,
                lease_validator=lambda lease_ref, budget: False,
                include_ngspice=False,
                cace_opener=object(),
            )
        self.assertIsNotNone(runtime.cace_adapter)
        self.assertEqual(runtime.health()["cace_verification"], "configured")
        self.assertEqual(runtime.cace_adapter.trusted_verifier_keys, self.trusted)


if __name__ == "__main__":
    unittest.main()
