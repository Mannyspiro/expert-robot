"""Two synthetic subjects routed through the same authenticated ASGI endpoint."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"python"), str(ROOT/"scripts/merlin")]
from ask_receipt import ReceiptConversation
from dot_ai_os.bridge import DotContextBridge
from dot_ai_os.http_gateway import (GatewayConfigurationError, ReadOnlyMerlinRegistry, SubjectReadScope,
                                    build_http_gateway)
from merlin.project_registry import MerlinRegistry
from test_http_gateway import configured, claims


class ReceiptHTTPScopeTests(unittest.TestCase):
    def test_shared_transport_uses_authenticated_subject_for_receipts_and_context(self):
        with tempfile.TemporaryDirectory() as directory:
            scopes, refs = {}, {}
            config = configured(allowed_subjects=("subject-a","subject-b"))
            for subject, count in zip(config.allowed_subjects,(12,31)):
                root = Path(directory)/subject
                bridge = DotContextBridge(MerlinRegistry(root))
                bridge.initialize()
                ref = bridge.ingest(namespace="merlin",source_id="receipt",title="receipt",
                    content=json.dumps({"run_id":"101","tests":{"tests":count}}).encode(),
                    source_url="https://example.org",source_version="1",epistemic="historical_report",
                    captured_at="2026-11-18T00:00:00Z")["source_ref"]
                bridge.save_handoff("resume",summary=subject,next_action="check",source_refs=[ref])
                refs[subject] = ref
                scopes[subject] = SubjectReadScope(DotContextBridge(ReadOnlyMerlinRegistry(root)),
                    lambda reader, pin=ref: ReceiptConversation(reader,{"101":{1:pin}}))

            async def introspect(token):
                return claims(config,sub=token) if token in scopes else {"active":False}

            def build(mapping):
                return build_http_gateway(root=root,namespaces=("merlin",),config=config,
                                          introspect=introspect,subject_scopes=mapping)
            with self.assertRaises(GatewayConfigurationError):
                build({"subject-a":scopes["subject-a"]})
            with TestClient(build(scopes).streamable_http_app(), base_url="http://127.0.0.1:8766") as client:
                def call(subject,name,args):
                    return client.post("/mcp",headers={"Authorization":"Bearer "+subject,
                        "Accept":"application/json, text/event-stream","MCP-Protocol-Version":"2025-06-18"},
                        json={"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":name,"arguments":args}})
                turns = {"turns":["For run 101, how many main shard tests ran?"]}
                for subject, count in (("subject-a",12),("subject-b",31),("subject-a",12)):
                    answer = call(subject,"receipt_dialogue",turns).json()["result"]["structuredContent"]
                    self.assertEqual(answer["value"],count)
                    self.assertEqual(answer["citation"]["source_ref"],refs[subject])
                    handoff = call(subject,"session_handoff",{"session_id":"resume"}).json()["result"]
                    self.assertEqual(handoff["structuredContent"]["handoff"]["summary"],subject)
                    hits = call(subject,"context_search",{"query":"tests"}).json()["result"]["structuredContent"]["hits"]
                    self.assertEqual({hit["source_ref"]["sha256"] for hit in hits},{refs[subject]["sha256"]})
                self.assertTrue(call("subject-b","context_fetch",{"source_ref":refs["subject-a"]}).json()["result"]["isError"])
                self.assertEqual(call("unknown","receipt_dialogue",turns).status_code,401)
