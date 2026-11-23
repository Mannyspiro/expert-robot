import tempfile
import unittest
from pathlib import Path
from wilborn_ops.gateway import BusinessGateway,Identity
from wilborn_ops.llm_boundary import ToolCall,BusinessToolDispatcher,SecurityUnavailable
from wilborn_ops.store import CaseStore
from wilborn_ops.workflow import Case

class SyntheticTestAdapter:
    """Test-only adapter; MUST NOT be deployed."""
    def verify(self,identity,call):
        return True

class BrokenAdapter:
    def verify(self,identity,call):
        raise RuntimeError("security service down")

class LLMBoundaryTests(unittest.TestCase):
    def test_fail_closed_and_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            store=CaseStore(Path(folder)/"demo.db")
            case=Case.open("general")
            store.save(case)
            gateway=BusinessGateway(store)
            identity=Identity("staff","wilborn-demo",frozenset({"cases:read"}))
            with self.assertRaises(PermissionError):
                BusinessToolDispatcher(gateway).dispatch(identity,ToolCall("list_cases",{}))
            dispatcher=BusinessToolDispatcher(gateway,SyntheticTestAdapter())
            result=dispatcher.dispatch(identity,ToolCall("list_cases",{}))
            self.assertEqual(len(result["data"]),1)
            self.assertEqual(result["data_class"],"synthetic")
            with self.assertRaises(PermissionError):
                dispatcher.dispatch(identity,ToolCall("run_shell",{}))
            with self.assertRaises(ValueError):
                dispatcher.dispatch(identity,ToolCall("list_cases",{"extra":1}))
            with self.assertRaises(ValueError):
                dispatcher.dispatch(identity,ToolCall("get_case_status",{"case_id":""}))
            with self.assertRaises(PermissionError):
                dispatcher.dispatch(Identity("other","other",frozenset({"cases:read"})),
                                    ToolCall("list_cases",{}))
            with self.assertRaises(SecurityUnavailable):
                BusinessToolDispatcher(gateway,BrokenAdapter()).dispatch(identity,ToolCall("list_cases",{}))
            store.close()
