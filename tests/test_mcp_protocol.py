"""Exercise the actual stdio MCP protocol, with no model/provider/network calls."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from merlin.project_registry import MerlinRegistry
from dot_ai_os.bridge import DotContextBridge


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_protocol_search_fetch_and_resume(self):
        with tempfile.TemporaryDirectory() as root:
            bridge = DotContextBridge(MerlinRegistry(root))
            bridge.initialize()
            result = bridge.ingest(namespace="merlin", source_id="protocol-test",
                title="Resume checkpoint", content=b"Merlin source-bound resume checkpoint.",
                source_url="https://example.org/checkpoint", source_version="v1",
                epistemic="local_observation", captured_at="2026-11-17T15:00:00Z")
            ref = result["source_ref"]
            bridge.save_handoff("test-session", summary="Continue integration",
                                next_action="Run acceptance tests", source_refs=[ref])
            params = StdioServerParameters(command=sys.executable, args=["-m",
                "dot_ai_os.mcp_server", "--root", root, "--namespaces", "merlin"],
                env={"PYTHONPATH": os.environ["PYTHONPATH"], "PATH": os.environ["PATH"]})
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    self.assertEqual({t.name for t in tools.tools},
                        {"context_status", "context_search", "context_fetch", "session_handoff", "rsi_status"})
                    self.assertTrue(all(t.annotations.readOnlyHint for t in tools.tools))
                    status = await session.call_tool("context_status", {})
                    self.assertFalse(status.isError)
                    self.assertEqual(status.structuredContent["record_count"], 1)
                    search = await session.call_tool("context_search", {"query": "resume"})
                    self.assertFalse(search.isError)
                    self.assertEqual(search.structuredContent["hits"][0]["source_ref"], ref)
                    fetched = await session.call_tool("context_fetch", {"source_ref": ref})
                    self.assertFalse(fetched.isError)
                    self.assertIn("resume", fetched.structuredContent["text"])
                    handoff = await session.call_tool("session_handoff", {"session_id": "test-session"})
                    self.assertFalse(handoff.isError)
                    self.assertEqual(handoff.structuredContent["handoff"]["summary"], "Continue integration")
                    workflow = await session.call_tool("rsi_status", {"session_id": "test-session"})
                    self.assertEqual(workflow.structuredContent["status"], "not_started")


if __name__ == "__main__":
    unittest.main()
