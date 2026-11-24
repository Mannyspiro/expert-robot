import tempfile
import unittest
from pathlib import Path
from wilborn_ops.gateway import BusinessGateway,Identity
from wilborn_ops.llm_boundary import BusinessToolDispatcher,ToolCall,SecurityUnavailable
from wilborn_ops.security_monitor import SecurityMonitor
from wilborn_ops.store import CaseStore

class AllowSyntheticOnly:
    def verify(self,identity,call):
        return True

class BrokenSecurity:
    def verify(self,identity,call):
        raise RuntimeError("simulated security failure")

class SecurityTelemetryTests(unittest.TestCase):
    def test_denials_and_security_failure_are_counted_without_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            store=CaseStore(Path(folder)/"demo.db")
            gateway=BusinessGateway(store)
            monitor=SecurityMonitor()
            identity=Identity("staff","wilborn-demo",frozenset({"cases:read"}))
            dispatcher=BusinessToolDispatcher(gateway,AllowSyntheticOnly(),monitor)
            with self.assertRaises(PermissionError):
                dispatcher.dispatch(identity,ToolCall("read_secrets",{"secret":"DO_NOT_LOG"}))
            with self.assertRaises(ValueError):
                dispatcher.dispatch(identity,ToolCall("list_cases",{"extra":"DO_NOT_LOG"}))
            with self.assertRaises(PermissionError):
                dispatcher.dispatch(Identity("staff","wrong-tenant",frozenset({"cases:read"})),
                                    ToolCall("list_cases",{}))
            with self.assertRaises(SecurityUnavailable):
                BusinessToolDispatcher(gateway,BrokenSecurity(),monitor).dispatch(
                    identity,ToolCall("list_cases",{}))
            summary=monitor.summary()
            self.assertEqual(summary["counts"]["unexpected_tool"],1)
            self.assertEqual(summary["counts"]["tool_denied"],2)
            self.assertEqual(summary["counts"]["integrity_failure"],1)
            self.assertNotIn("DO_NOT_LOG",repr(summary))
            store.close()

    def test_default_deny_emits_event(self):
        with tempfile.TemporaryDirectory() as folder:
            store=CaseStore(Path(folder)/"demo.db")
            monitor=SecurityMonitor()
            dispatcher=BusinessToolDispatcher(BusinessGateway(store),monitor=monitor)
            identity=Identity("staff","wilborn-demo",frozenset({"cases:read"}))
            with self.assertRaises(PermissionError):
                dispatcher.dispatch(identity,ToolCall("list_cases",{}))
            self.assertEqual(monitor.summary()["counts"]["tool_denied"],1)
            store.close()
