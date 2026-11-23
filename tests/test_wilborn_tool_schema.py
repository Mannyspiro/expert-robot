import unittest
from wilborn_ops.tool_schema import TOOLS,describe_tools
from wilborn_ops.llm_boundary import ALLOWED_TOOLS

class ToolSchemaTests(unittest.TestCase):
    def test_schema_and_dispatcher_agree(self):
        self.assertEqual(set(TOOLS),set(ALLOWED_TOOLS))
        for item in describe_tools():
            self.assertEqual(item["parameters"]["type"],"object")
            self.assertFalse(item["parameters"]["additionalProperties"])
        self.assertEqual(TOOLS["get_case_status"]["required"],["case_id"])
        self.assertEqual(TOOLS["get_case_status"]["properties"]["case_id"]["maxLength"],64)
