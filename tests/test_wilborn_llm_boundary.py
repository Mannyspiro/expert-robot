import tempfile
import unittest
from pathlib import Path
from wilborn_ops.gateway import BusinessGateway,Identity
from wilborn_ops.llm_boundary import ToolCall,dispatch
from wilborn_ops.store import CaseStore
from wilborn_ops.workflow import Case

class LLMBoundaryTests(unittest.TestCase):
    def test_explicit_verification_and_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            store=CaseStore(Path(folder)/"demo.db")
            case=Case.open("general")
            store.save(case)
            gateway=BusinessGateway(store)
            identity=Identity("staff","wilborn-demo",frozenset({"cases:read"}))
            with self.assertRaises(PermissionError):
                dispatch(gateway,identity,ToolCall("list_cases",{}))
            self.assertEqual(len(dispatch(gateway,identity,ToolCall("list_cases",{}),artex_verified=True)),1)
            with self.assertRaises(PermissionError):
                dispatch(gateway,identity,ToolCall("run_shell",{}),artex_verified=True)
            with self.assertRaises(ValueError):
                dispatch(gateway,identity,ToolCall("list_cases",{"extra":1}),artex_verified=True)
            with self.assertRaises(ValueError):
                dispatch(gateway,identity,ToolCall("get_case_status",{"case_id":""}),artex_verified=True)
            with self.assertRaises(PermissionError):
                dispatch(gateway,Identity("other","other",frozenset({"cases:read"})),
                         ToolCall("list_cases",{}),artex_verified=True)
            store.close()
