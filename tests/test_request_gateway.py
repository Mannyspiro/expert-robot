"""Real MCP HTTP request intake: identity comes from verified bearer context."""
import tempfile
import time
import unittest

from starlette.testclient import TestClient
from merlin.project_registry import MerlinRegistry
from dot_ai_os.bridge import DotContextBridge
from dot_ai_os.http_gateway import GatewayConfig, IntrospectionTokenVerifier
from dot_ai_os.job_inbox import ProductionJobInbox
from dot_ai_os.request_gateway import create_request_server, REQUEST_SCOPE


class RequestGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = MerlinRegistry(self.temp.name)
        bridge = DotContextBridge(self.registry)
        bridge.initialize()
        self.ref = bridge.ingest(namespace="merlin", source_id="http-request-test",
            title="Pinned context", content=b"Source context is unverified data.",
            source_url="https://example.org/source", source_version="test-v1",
            epistemic="local_observation", captured_at="2026-11-17T16:00:00Z")["source_ref"]
        self.config = GatewayConfig(issuer_url="https://issuer.example.org",
            introspection_url="https://issuer.example.org/introspect",
            resource_url="https://requests.example.org/mcp", allowed_subjects=("alice", "bob"), port=8767)
        self.tokens = {
            "alice-token": self.claims("alice"),
            "bob-token": self.claims("bob"),
            "read-token": self.claims("alice", scope="merlin:context:read"),
            "wrong-resource": self.claims("alice", aud="https://reader.example.org/mcp"),
        }
        self.introspection_calls = []
        async def introspect(token):
            self.introspection_calls.append(token)
            return self.tokens.get(token, {"active": False})
        inbox = ProductionJobInbox(self.registry, namespaces=("merlin",))
        server = create_request_server(inbox, config=self.config,
            token_verifier=IntrospectionTokenVerifier(self.config, introspect))
        self.client = self.enterContext(TestClient(server.streamable_http_app(), base_url="http://127.0.0.1:8767"))
        self.args = {"idempotency_key": "request-1", "namespace": "merlin",
            "objective": "Compare retrieval with exact citations", "source_commit": "a"*40,
            "source_refs": [self.ref], "acceptance_criteria": ["No citation loss"], "max_cost_usd": 0}

    def claims(self, subject, scope=REQUEST_SCOPE, aud="https://requests.example.org/mcp"):
        return {"active": True, "sub": subject, "client_id": "fixture-client",
                "iss": "https://issuer.example.org", "aud": aud,
                "exp": int(time.time())+600, "scope": scope}

    def call(self, tool, arguments, token="alice-token"):
        headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        return self.client.post("/mcp", headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": tool, "arguments": arguments}})

    def test_missing_identity_and_read_only_scope_cannot_write(self):
        before = len(self.registry.inventory("dot-ai-os")["artifacts"])
        self.assertEqual(self.call("submit_research_request", self.args, token=None).status_code, 401)
        self.assertEqual(self.introspection_calls, [])
        self.assertEqual(self.call("submit_research_request", self.args, token="read-token").status_code, 403)
        self.assertEqual(len(self.registry.inventory("dot-ai-os")["artifacts"]), before)

    def test_valid_intake_is_pending_and_replay_is_exact(self):
        first = self.call("submit_research_request", self.args)
        self.assertEqual(first.status_code, 200)
        payload = first.json()["result"]["structuredContent"]
        self.assertEqual(payload["state"], "pending_operator_review")
        self.assertEqual(payload["execution_state"], "not_dispatched")
        self.assertFalse(payload["promotion_authority"])
        count = len(self.registry.inventory("dot-ai-os")["artifacts"])
        second = self.call("submit_research_request", self.args).json()["result"]["structuredContent"]
        self.assertEqual(payload, second)
        self.assertEqual(len(self.registry.inventory("dot-ai-os")["artifacts"]), count)
        status = self.call("research_request_status", {"request_id": payload["request_id"]})
        self.assertEqual(status.json()["result"]["structuredContent"], payload)

    def test_status_is_bound_to_authenticated_principal(self):
        payload = self.call("submit_research_request", self.args).json()["result"]["structuredContent"]
        other = self.call("research_request_status", {"request_id": payload["request_id"]}, token="bob-token")
        self.assertTrue(other.json()["result"]["isError"])
        self.assertNotIn("Compare retrieval", other.text)

    def test_other_resource_and_namespace_do_not_create_requests(self):
        before = len(self.registry.inventory("dot-ai-os")["artifacts"])
        self.assertEqual(self.call("submit_research_request", self.args, token="wrong-resource").status_code, 401)
        invalid = {**self.args, "namespace": "morgana-cace"}
        self.assertTrue(self.call("submit_research_request", invalid).json()["result"]["isError"])
        self.assertEqual(len(self.registry.inventory("dot-ai-os")["artifacts"]), before)

    def test_tool_schemas_never_accept_principal_or_dispatch_authority(self):
        response = self.client.post("/mcp", headers={"Authorization":"Bearer alice-token",
            "Accept":"application/json, text/event-stream", "MCP-Protocol-Version":"2025-06-18"},
            json={"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
        tools = response.json()["result"]["tools"]
        self.assertEqual({tool["name"] for tool in tools}, {"submit_research_request","research_request_status"})
        for tool in tools:
            fields=tool["inputSchema"]["properties"]
            self.assertFalse({"principal","approval_state","execute","promotion_authority"}.intersection(fields))


if __name__ == "__main__":
    unittest.main()
