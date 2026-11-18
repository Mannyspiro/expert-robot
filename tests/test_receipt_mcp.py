"""Exercise the actual MCP tool dispatcher with two host-provisioned scopes."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"python"), str(ROOT/"scripts/merlin")]
from ask_receipt import ReceiptConversation
from dot_ai_os.bridge import DotContextBridge
from dot_ai_os.mcp_server import create_server
from merlin.project_registry import MerlinRegistry


class MCPDialogueTests(unittest.IsolatedAsyncioTestCase):
    async def test_catalogue_scope_and_fresh_state(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = DotContextBridge(MerlinRegistry(Path(directory)))
            bridge.initialize()
            refs = {}
            for run in ("101","102","201","202"):
                refs[run] = bridge.ingest(namespace="merlin",source_id=run,title="Example",
                    content=json.dumps({"run_id":run,"tests":{"tests":int(run)}}).encode(),
                    source_url="https://example.org",source_version="1",epistemic="historical_report",
                    captured_at="2026-11-18T00:00:00Z")["source_ref"]
            def host(runs):
                return create_server(bridge,new_receipt_dialogue=lambda: ReceiptConversation(
                    bridge,{run:{1:refs[run]} for run in runs}))
            a,b = host(("101","102")),host(("201","202"))
            async def invoke(server,*turns):
                _, result = await server.call_tool("receipt_dialogue",{"turns":list(turns)})
                return result
            q = "How many main shard tests ran?"
            answers = await asyncio.gather(invoke(a,q,"101"),invoke(b,q,"201"))
            self.assertEqual([v["value"] for v in answers],[101,201])
            self.assertEqual(answers[0]["citation"]["source_ref"],refs["101"])
            self.assertEqual((await invoke(a,q,"201"))["disposition"],"abstain")
            self.assertEqual((await invoke(a,"101"))["disposition"],"clarify_field")
            self.assertEqual((await invoke(a,q,"For run 102, how many main shard tests ran?"))["value"],102)
            self.assertNotIn("receipt_dialogue",[t.name for t in await create_server(bridge).list_tools()])
