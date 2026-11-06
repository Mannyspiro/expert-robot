"""Authenticated HTTP boundary tests for Hermes' durable outbox worker API."""
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from python.merlin.app import EventStore, make_handler
from python.merlin.event_outbox import MerlinEventOutbox


class MerlinWorkerApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.outbox = MerlinEventOutbox(self.root / "outbox.sqlite3")
        self.tokens = {"hermes": "h" * 48, "mcfc": "m" * 48}
        self.env = {"MERLIN_WORKER_TOKENS": json.dumps(self.tokens)}
        self.patch = patch.dict(os.environ, self.env, clear=False)
        self.patch.start()
        handler = make_handler(
            EventStore(self.root / "events.sqlite3"),
            learning_outbox=self.outbox,
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.patch.stop()
        self.temp.cleanup()

    def request(self, path, payload=None, worker="hermes", token=None, method="POST"):
        headers = {}
        if worker:
            headers["X-Merlin-Worker-ID"] = worker
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        elif worker in self.tokens:
            headers["Authorization"] = "Bearer " + self.tokens[worker]
        body = None if payload is None else json.dumps(payload).encode()
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_worker_authentication_is_required_and_identity_is_bound_to_token(self):
        self.outbox.enqueue("auth-event", "merlin.hermes.task", {"task": "research"})
        status, body = self.request("/api/internal/outbox/claim", {}, worker=None)
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "worker_authentication_required")
        status, body = self.request(
            "/api/internal/outbox/claim", {}, worker="hermes", token=self.tokens["mcfc"])
        self.assertEqual(status, 401)
        status, body = self.request(
            "/api/internal/outbox/claim", {}, worker="unknown", token="x" * 48)
        self.assertEqual(status, 401)

    def test_claim_heartbeat_acknowledge_round_trip(self):
        queued = self.outbox.enqueue(
            "round-trip", "merlin.hermes.task", {"task": "research", "budget": 3})
        status, response = self.request(
            "/api/internal/outbox/claim", {"topics": ["merlin.hermes.task"], "lease_seconds": 30})
        self.assertEqual(status, 200)
        lease = response["lease"]
        self.assertEqual(lease["event_id"], queued["event_id"])
        self.assertEqual(lease["lease_owner"], "hermes")
        status, heartbeat = self.request("/api/internal/outbox/heartbeat", {
            "event_id": lease["event_id"], "lease_token": lease["lease_token"],
            "lease_seconds": 60,
        })
        self.assertEqual(status, 200)
        self.assertEqual(heartbeat["event"]["state"], "leased")
        status, ack = self.request("/api/internal/outbox/acknowledge", {
            "event_id": lease["event_id"], "lease_token": lease["lease_token"],
            "result": {"accepted": True, "receipt_id": "receipt-1"},
        })
        self.assertEqual(status, 200)
        self.assertEqual(ack["event"]["state"], "acknowledged")
        self.assertEqual(ack["event"]["result"]["receipt_id"], "receipt-1")

    def test_worker_cannot_acknowledge_another_workers_lease(self):
        queued = self.outbox.enqueue("worker-isolation", "merlin.hermes.task", {})
        status, response = self.request("/api/internal/outbox/claim", {})
        lease = response["lease"]
        status, body = self.request("/api/internal/outbox/acknowledge", {
            "event_id": queued["event_id"], "lease_token": lease["lease_token"],
        }, worker="mcfc")
        self.assertEqual(status, 409)
        self.assertEqual(body["error"], "outbox_lease_conflict")
        self.assertEqual(self.outbox.get(queued["event_id"])["state"], "leased")

    def test_retry_returns_event_to_pending_then_quarantines(self):
        queued = self.outbox.enqueue("retry-api", "merlin.hermes.task", {})
        _, first = self.request("/api/internal/outbox/claim", {})
        lease = first["lease"]
        status, retry = self.request("/api/internal/outbox/retry", {
            "event_id": queued["event_id"], "lease_token": lease["lease_token"],
            "error": "provider unavailable", "max_attempts": 2,
        })
        self.assertEqual(status, 200)
        self.assertEqual(retry["event"]["state"], "pending")
        _, second = self.request("/api/internal/outbox/claim", {})
        status, final = self.request("/api/internal/outbox/retry", {
            "event_id": queued["event_id"], "lease_token": second["lease"]["lease_token"],
            "error": "provider still unavailable", "max_attempts": 2,
        })
        self.assertEqual(status, 200)
        self.assertEqual(final["event"]["state"], "quarantined")

    def test_status_is_authenticated_and_exposes_only_counts(self):
        self.outbox.enqueue("status-event", "merlin.hermes.task", {})
        status, body = self.request("/api/internal/outbox/status", method="GET")
        self.assertEqual(status, 200)
        self.assertEqual(body["worker_id"], "hermes")
        self.assertEqual(body["counts"]["pending"], 1)
        self.assertNotIn("lease_token", json.dumps(body))

    def test_worker_api_fails_closed_without_outbox(self):
        handler = make_handler(EventStore(self.root / "no-outbox.sqlite3"))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/api/internal/outbox/claim",
                data=b"{}", headers={
                    "Content-Type": "application/json",
                    "X-Merlin-Worker-ID": "hermes",
                    "Authorization": "Bearer " + self.tokens["hermes"],
                })
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
            self.assertEqual(caught.exception.code, 503)
            self.assertEqual(json.loads(caught.exception.read())["error"], "outbox_not_configured")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
