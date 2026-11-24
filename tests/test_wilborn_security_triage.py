import unittest
from wilborn_ops.security_monitor import SecurityMonitor,SecurityEvent
from wilborn_ops.security_triage import triage

class SecurityTriageTests(unittest.TestCase):
    def test_bounded_ranked_findings(self):
        monitor=SecurityMonitor()
        for kind in ("tool_denied","tool_denied","integrity_failure","unexpected_tool"):
            monitor.observe(SecurityEvent(kind,"demo","synthetic"))
        findings=triage(monitor.summary(),max_findings=2)
        self.assertEqual([f.kind for f in findings],["integrity_failure","unexpected_tool"])
        self.assertTrue(all(f.data_class=="synthetic" for f in findings))
        self.assertEqual(findings[0].priority,"critical")

    def test_reject_real_unknown_or_malformed_summaries(self):
        for summary in (
            {"environment":"production","data_class":"real","counts":{}},
            {"environment":"demo","data_class":"synthetic","counts":{"unknown":1}},
            {"environment":"demo","data_class":"synthetic","counts":{"tool_denied":-1}},
            {"environment":"demo","data_class":"synthetic","counts":{"tool_denied":True}},
        ):
            with self.assertRaises((PermissionError,ValueError)):
                triage(summary)
        with self.assertRaises(ValueError):
            triage({"environment":"demo","data_class":"synthetic","counts":{}},max_findings=0)

    def test_empty_summary_yields_no_findings(self):
        self.assertEqual(triage(SecurityMonitor().summary()),[])
