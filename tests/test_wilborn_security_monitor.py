import unittest
from wilborn_ops.security_monitor import SecurityEvent, SecurityMonitor

class SecurityMonitorTests(unittest.TestCase):
    def test_typed_synthetic_events_only(self):
        monitor=SecurityMonitor()
        event=SecurityEvent("provenance_rejected","demo","synthetic")
        alert=monitor.observe(event)
        self.assertEqual(alert["severity"],"high")
        self.assertTrue(alert["requires_review"])
        self.assertEqual(monitor.summary()["counts"]["provenance_rejected"],1)

    def test_reject_untrusted_real_or_unknown_events(self):
        with self.assertRaises(PermissionError):
            SecurityEvent("tool_denied","production","real")
        with self.assertRaises(ValueError):
            SecurityEvent("made_up","demo","synthetic")
        with self.assertRaises(TypeError):
            SecurityMonitor().observe({"kind":"tool_denied","secret":"never-log"})
