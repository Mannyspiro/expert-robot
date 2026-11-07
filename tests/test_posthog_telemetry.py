import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from pathlib import Path

from python.merlin.app import EventStore, make_handler
from python.merlin.posthog_telemetry import PostHogExportService, PostHogTelemetrySink


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return b'{"status":"ok"}'


class PostHogTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = EventStore(Path(self.temp.name) / "events.sqlite3")
        self.requests = []

        def opener(request, timeout):
            self.requests.append({
                "url": request.full_url,
                "timeout": timeout,
                "body": json.loads(request.data),
            })
            return FakeResponse()

        self.sink = PostHogTelemetrySink(
            project_token="phc-test-project-token",
            region="us",
            instance_id="merlin-test-instance",
            opener=opener,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_environment_without_token_keeps_analytics_disabled(self):
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(PostHogTelemetrySink.from_environment())

    def test_environment_requires_instance_identity_when_export_is_enabled(self):
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {
            "MERLIN_POSTHOG_PROJECT_TOKEN": "phc-test",
        }, clear=True):
            with self.assertRaisesRegex(ValueError, "INSTANCE_ID"):
                PostHogTelemetrySink.from_environment()

        with patch.dict(os.environ, {
            "MERLIN_POSTHOG_PROJECT_TOKEN": "phc-test",
            "MERLIN_INSTANCE_ID": "merlin-production-instance",
        }, clear=True):
            sink = PostHogTelemetrySink.from_environment()
            self.assertTrue(sink.distinct_id.startswith("merlin:"))
            self.assertNotIn("merlin-production-instance", sink.distinct_id)

    def test_export_contains_only_allowlisted_metadata(self):
        self.store.append(
            "/api/chat",
            {"messages": [{"role": "user", "content": "private prompt text"}]},
            {
                "model": "gemini-test",
                "provider_host": "generativelanguage.googleapis.com",
                "response_bytes": 123,
                "duration_ms": 45.6,
                "private_text": "must not leave Merlin",
                "email": "person@example.test",
            },
        )
        service = PostHogExportService(event_store=self.store, sink=self.sink)
        self.assertEqual(service.run_once(), 1)
        self.assertEqual(self.store.get_posthog_export_cursor(), 1)
        sent = json.dumps(self.requests[0]["body"])
        self.assertNotIn("private prompt text", sent)
        self.assertNotIn("must not leave Merlin", sent)
        self.assertNotIn("person@example.test", sent)
        event = self.requests[0]["body"]["batch"][0]
        props = event["properties"]
        self.assertEqual(event["event"], "merlin_runtime_event")
        self.assertEqual(props["model"], "gemini-test")
        self.assertEqual(props["response_bytes"], 123)
        self.assertEqual(props["distinct_id"], self.sink.distinct_id)
        self.assertNotIn("email", props)
        self.assertNotIn("merlin_request_sha256", props)
        self.assertNotIn("private_text", props)
        self.assertNotIn("content", props)
        self.assertFalse(props["$process_person_profile"])
        self.assertEqual(self.requests[0]["url"], "https://us.i.posthog.com/batch/")

    def test_cursor_is_not_advanced_when_remote_export_fails(self):
        self.store.append("/api/job", {"secret": "not persisted"}, {"status": "failed"})

        def fail(request, timeout):
            raise OSError("network unavailable")

        sink = PostHogTelemetrySink(
            project_token="phc-test",
            opener=fail,
        )
        service = PostHogExportService(event_store=self.store, sink=sink)
        with self.assertRaises(OSError):
            service.run_once()
        self.assertEqual(self.store.get_posthog_export_cursor(), 0)

    def test_retry_uses_same_stable_insert_id(self):
        self.store.append("/api/job", {}, {"status": "completed"})
        event_ids = []

        def opener(request, timeout):
            payload = json.loads(request.data)
            event_ids.append(payload["batch"][0]["properties"]["$insert_id"])
            return FakeResponse()

        sink = PostHogTelemetrySink(
            project_token="phc-test",
            opener=opener,
        )
        # Simulate acceptance followed by a crash before cursor advancement.
        class CrashBeforeCursor:
            def __init__(self, inner):
                self.inner = inner
                self.calls = 0

            def get_posthog_export_cursor(self):
                return 0

            def export_batch(self, **kwargs):
                return self.inner.export_batch(**kwargs)

            def advance_posthog_export_cursor(self, cursor):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("simulated crash")

        crash_store = CrashBeforeCursor(self.store)
        service = PostHogExportService(event_store=crash_store, sink=sink)
        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            service.run_once()
        self.assertEqual(service.run_once(), 1)
        self.assertEqual(len(event_ids), 2)
        self.assertEqual(event_ids[0], event_ids[1])

    def test_runtime_analytics_endpoint_exposes_exporter_health(self):
        service = PostHogExportService(event_store=self.store, sink=self.sink)
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(self.store, posthog_service=service),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(
                f"http://127.0.0.1:{server.server_port}/api/runtime/analytics",
                timeout=5,
            ) as response:
                health = json.loads(response.read())
            self.assertEqual(health["schema"], "merlin-posthog-export-health/1")
            self.assertEqual(health["status"], "stopped")
            self.assertFalse(health["raw_conversation_export"])
            self.assertFalse(health["promotion_authority"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_eu_region_is_selected_from_fixed_endpoint_map(self):
        sink = PostHogTelemetrySink(project_token="phc-test", region="eu")
        self.assertEqual(sink.endpoint, "https://eu.i.posthog.com/batch/")
        with self.assertRaisesRegex(ValueError, "region"):
            PostHogTelemetrySink(project_token="phc-test", region="custom")


if __name__ == "__main__":
    unittest.main()
