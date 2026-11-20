"""Real ASGI/MCP authentication middleware; introspection is a trusted local double.

These tests do not establish an external identity provider or live deployment.
"""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import Mock

import httpx
from starlette.testclient import TestClient

from merlin.project_registry import MerlinRegistry
from dot_ai_os.bridge import DotContextBridge, canonical
from dot_ai_os.http_gateway import (
    GatewayConfig, GatewayConfigurationError, HTTPIntrospector,
    IntrospectionTokenVerifier, ReadOnlyMerlinRegistry, ReadOnlyRegistryError,
    build_http_gateway, create_http_server,
)


def configured(**values):
    defaults = dict(issuer_url="https://issuer.example.test",
                    introspection_url="https://issuer.example.test/introspect",
                    resource_url="https://merlin.example.test/mcp",
                    allowed_subjects=("user-allowed",), port=8766)
    defaults.update(values)
    return GatewayConfig(**defaults)


def claims(config, **values):
    defaults = {"active": True, "iss": config.issuer_url, "sub": "user-allowed",
                "aud": config.resource_url, "resource": config.resource_url,
                "exp": time.time() + 300, "client_id": "registered-client",
                "scope": "merlin:context:read"}
    defaults.update(values)
    return defaults


class StreamBody(httpx.AsyncByteStream):
    def __init__(self, data):
        self.data = data

    async def __aiter__(self):
        for start in range(0, len(self.data), 100):
            yield self.data[start:start + 100]


def streamed_response(status=200, body=b"{}", headers=None):
    return httpx.Response(status, headers={"content-type": "application/json", **(headers or {})},
                          stream=StreamBody(body))


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        writer = DotContextBridge(MerlinRegistry(self.root))
        writer.initialize()
        self.ref = writer.ingest(namespace="merlin", source_id="HTTP-source",
             title="Merlin private context", content=b"Merlin private source-bound checkpoint.",
             source_url="https://example.test/checkpoint", source_version="v1",
             epistemic="local_observation", captured_at="2026-11-17T15:00:00Z")["source_ref"]
        writer.save_handoff("resume", summary="Resume local implementation",
                            next_action="Run focused tests", source_refs=[self.ref])
        self.config = configured()
        self.responses = {"valid-token": claims(self.config)}
        self.introspection_calls = []

        async def introspect(token):
            self.introspection_calls.append(token)
            return deepcopy(self.responses.get(token, {"active": False}))

        self.verifier = IntrospectionTokenVerifier(self.config, introspect)
        self.reader = DotContextBridge(ReadOnlyMerlinRegistry(self.root), namespaces=("merlin",))
        self.reader.search = Mock(wraps=self.reader.search)
        self.server = create_http_server(self.reader, config=self.config, token_verifier=self.verifier)
        self.client = self.enterContext(TestClient(self.server.streamable_http_app(),
                          base_url="http://127.0.0.1:8766"))

    def rpc(self, method, params=None, token="valid-token", headers=None):
        values = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"}
        if token is not None:
            values["Authorization"] = "Bearer " + token
        values.update(headers or {})
        return self.client.post("/mcp", headers=values,
             json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})

    def call(self, name="context_search", arguments=None, **kwargs):
        return self.rpc("tools/call", {"name": name, "arguments": arguments or {"query": "checkpoint"}}, **kwargs)

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

    def test_authentication_and_scope_rejections_do_not_reach_tool(self):
        before = self.snapshot()
        no_token = self.call(token=None)
        self.assertEqual(no_token.status_code, 401)
        self.assertIn("resource_metadata", no_token.headers["www-authenticate"])
        self.assertEqual(self.introspection_calls, [])
        unknown = self.call(token="unknown-token")
        self.assertEqual(unknown.status_code, 401)
        self.responses["scope-token"] = claims(self.config, scope="other:read")
        no_scope = self.call(token="scope-token")
        self.assertEqual(no_scope.status_code, 403)
        self.assertIn("insufficient_scope", no_scope.headers["www-authenticate"])
        self.reader.search.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_valid_http_mcp_query_fetch_resume_and_tool_annotations(self):
        before = self.snapshot()
        initialized = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                               "clientInfo": {"name": "tests", "version": "1"}})
        self.assertEqual(initialized.status_code, 200, initialized.text)
        tools = self.rpc("tools/list")
        self.assertEqual(tools.status_code, 200, tools.text)
        values = tools.json()["result"]["tools"]
        self.assertEqual({item["name"] for item in values},
            {"context_status", "context_search", "context_fetch", "session_handoff", "rsi_status"})
        self.assertTrue(all(item["annotations"]["readOnlyHint"] for item in values))
        response = self.call()
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["hits"][0]["source_ref"], self.ref)
        fetch = self.call("context_fetch", {"source_ref": self.ref})
        self.assertFalse(fetch.json()["result"]["isError"])
        resume = self.call("session_handoff", {"session_id": "resume"})
        self.assertEqual(resume.json()["result"]["structuredContent"]["handoff"]["summary"], "Resume local implementation")
        self.assertEqual(self.server.settings.host, "127.0.0.1")
        self.assertEqual(before, self.snapshot())

    def test_invalid_claims_fail_closed_without_registry_or_coder_activity(self):
        invalid = {
            "audience": {"aud": "https://other.example.test/mcp"},
            "missing-audience": {"aud": None},
            "resource": {"resource": "https://other.example.test/mcp"},
            "issuer": {"iss": "https://other-issuer.example.test"},
            "subject": {"sub": "user-not-allowed"},
            "expiry": {"exp": time.time() - 1},
            "boolean-expiry": {"exp": True},
            "nan-expiry": {"exp": float("nan")},
            "infinite-expiry": {"exp": float("inf")},
            "missing-expiry": {"exp": None},
            "not-active-bool": {"active": 1},
            "not-yet-valid": {"nbf": time.time() + 300},
            "scope-type": {"scope": ["merlin:context:read"]},
            "client-id": {"client_id": ""},
        }
        before = self.snapshot()
        for token, changes in invalid.items():
            with self.subTest(token=token):
                self.responses[token] = claims(self.config, **changes)
                self.assertEqual(self.call(token=token).status_code, 401)
        self.reader.search.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_fixed_host_and_origin_protection(self):
        self.assertEqual(self.call(headers={"Host": "attacker.example.test"}).status_code, 421)
        self.assertEqual(self.call(headers={"Origin": "https://attacker.example.test"}).status_code, 403)
        self.reader.search.assert_not_called()
        self.assertEqual(self.call(headers={"Host": "merlin.example.test",
                       "Origin": "https://merlin.example.test"}).status_code, 200)

    def test_read_only_registry_denies_sql_and_blob_mutations_without_migrations(self):
        before = self.snapshot()
        reader = ReadOnlyMerlinRegistry(self.root)
        with reader._connect() as db:
            self.assertEqual(db.execute("PRAGMA query_only").fetchone()[0], 1)
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("CREATE TABLE must_not_exist(value TEXT)")
        for operation in (lambda: reader._initialize(),
                          lambda: reader.register_project("new", "not allowed"),
                          lambda: reader.put_artifact("dot-ai-os", "new.txt", b"new")):
            with self.assertRaises(ReadOnlyRegistryError):
                operation()
        self.assertEqual(before, self.snapshot())

    def test_missing_or_invalid_configuration_refuses_before_registry_creation(self):
        missing = self.root / "not-created"
        with self.assertRaises(GatewayConfigurationError):
            build_http_gateway(root=missing, namespaces=("merlin",), config=None)
        self.assertFalse(missing.exists())
        for changes in ({"issuer_url": "http://insecure.example.test"},
                        {"resource_url": "https://example.test/other"},
                        {"introspection_url": "https://example.test/introspect?endpoint=other"},
                        {"allowed_subjects": ()}, {"port": True}):
            with self.subTest(changes=changes), self.assertRaises(GatewayConfigurationError):
                configured(**changes)
        with self.assertRaises(GatewayConfigurationError):
            create_http_server(DotContextBridge(MerlinRegistry(self.root)),
                               config=self.config, token_verifier=self.verifier)

    def test_wal_mode_refuses_before_sqlite_can_create_side_files(self):
        with sqlite3.connect(self.root / "merlin.sqlite3") as db:
            self.assertEqual(db.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        before = self.snapshot()
        with self.assertRaisesRegex(GatewayConfigurationError, "read snapshot"):
            ReadOnlyMerlinRegistry(self.root)
        self.assertEqual(before, self.snapshot())

    def test_workflow_status_cannot_cross_namespace_scope(self):
        writer = DotContextBridge(MerlinRegistry(self.root))
        outside = writer.ingest(namespace="morgana-cace", source_id="other-source", title="Other namespace",
            content=b"Other project context", source_url="https://example.test/other", source_version="v1",
            epistemic="local_observation", captured_at="2026-11-17T15:00:00Z")["source_ref"]
        payload = {"schema": "dot-dual-coder-spec/1", "specification": {"context_refs": [outside]}, "providers": {}}
        writer.registry.put_artifact("dot-ai-os", "dual-coder/other-scope/spec.json", canonical(payload), "application/json")
        response = self.call("rsi_status", {"session_id": "other-scope"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["result"]["isError"])
        self.assertNotIn("Other project context", response.text)


class IntrospectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixed_http_endpoint_body_and_valid_response(self):
        config = configured()
        requests = []

        def handler(request):
            requests.append(request)
            return streamed_response(body=json.dumps(claims(config)).encode())

        callback = HTTPIntrospector(config, transport=httpx.MockTransport(handler))
        access = await IntrospectionTokenVerifier(config, callback).verify_token("local-test-token")
        self.assertIsNotNone(access)
        self.assertEqual(access.subject, "user-allowed")
        self.assertEqual(access.resource, config.resource_url)
        self.assertEqual(str(requests[0].url), config.introspection_url)
        self.assertEqual(requests[0].method, "POST")
        self.assertIn(b"token=local-test-token", requests[0].content)

    async def test_malformed_oversized_redirect_and_transport_failure_responses(self):
        config = configured(introspection_max_bytes=1000)
        cases = [
            streamed_response(body=b"not-json"),
            streamed_response(body=b'{"active":true,"active":false}'),
            streamed_response(body=b"[]"),
            streamed_response(headers={"content-type": "text/plain"}),
            streamed_response(headers={"content-length": "1001"}),
            streamed_response(headers={"content-length": "bad"}),
            streamed_response(body=b"x" * 1001),
            streamed_response(headers={"content-encoding": "gzip"}),
            streamed_response(302, headers={"location": "https://attacker.example.test/token"}),
            streamed_response(500),
        ]
        for index, response in enumerate(cases):
            with self.subTest(index=index):
                requests = []
                def handler(request):
                    requests.append(request)
                    return response
                callback = HTTPIntrospector(config, transport=httpx.MockTransport(handler))
                self.assertIsNone(await IntrospectionTokenVerifier(config, callback).verify_token("test-token"))
                self.assertEqual(len(requests), 1)

    async def test_callback_error_timeout_size_and_token_bounds_fail_closed(self):
        config = configured(introspection_timeout_seconds=0.01, introspection_max_bytes=1000)
        calls = []
        async def too_large(token):
            calls.append(token)
            return {**claims(config), "extra": "x" * 1001}
        verifier = IntrospectionTokenVerifier(config, too_large)
        self.assertIsNone(await verifier.verify_token("bad token"))
        self.assertIsNone(await verifier.verify_token("a" * 8193))
        self.assertEqual(calls, [])
        self.assertIsNone(await verifier.verify_token("test-token"))
        async def failing(token):
            raise RuntimeError("provider error must remain private")
        self.assertIsNone(await IntrospectionTokenVerifier(config, failing).verify_token("test-token"))
        async def blocking(token):
            import asyncio
            await asyncio.sleep(0.1)
            return claims(config)
        self.assertIsNone(await IntrospectionTokenVerifier(config, blocking).verify_token("test-token"))

    async def test_missing_issuer_allowed_but_declared_issuer_must_match(self):
        config = configured()
        async def absent_issuer(token):
            value = claims(config)
            value.pop("iss")
            return value
        self.assertIsNotNone(await IntrospectionTokenVerifier(config, absent_issuer).verify_token("test-token"))
        async def list_audience(token):
            return claims(config, aud=["https://another-resource.example.test", config.resource_url])
        self.assertIsNotNone(await IntrospectionTokenVerifier(config, list_audience).verify_token("test-token"))


if __name__ == "__main__":
    unittest.main()
