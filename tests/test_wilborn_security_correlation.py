import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from wilborn_ops.security_monitor import SecurityMonitor,SecurityEvent
from wilborn_ops.artex_detection import ArtexObservation,classify,observe_lead,SOURCE_REVISION

class Clock:
    def __init__(self):
        self.value=0
    def __call__(self):
        return self.value

def event(kind):
    return SecurityEvent(kind,"demo","synthetic")

class SecurityCorrelationTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock()
        self.monitor=SecurityMonitor(clock=self.clock)

    def test_burst_crossing_and_rearming(self):
        for kind in ("tool_denied","unexpected_tool"):
            self.assertEqual(self.monitor.observe(event(kind))["correlation_alerts"],[])
        self.assertEqual(self.monitor.observe(event("tool_denied"))["correlation_alerts"],
                         ["tool_policy_denial_burst"])
        self.assertEqual(self.monitor.observe(event("tool_denied"))["correlation_alerts"],[])
        self.assertEqual(self.monitor.summary()["active_correlations"],["tool_policy_denial_burst"])
        self.clock.value=60
        self.assertEqual(self.monitor.summary()["active_correlations"],[])
        for _ in range(2):
            self.assertEqual(self.monitor.observe(event("tool_denied"))["correlation_alerts"],[])
        self.assertEqual(self.monitor.observe(event("tool_denied"))["correlation_alerts"],
                         ["tool_policy_denial_burst"])

    def test_grouping_and_window_are_independent(self):
        for _ in range(2):
            self.monitor.observe(event("auth_failure"))
            self.monitor.observe(event("tool_denied"))
        self.assertEqual(self.monitor.summary()["active_correlations"],[])
        other=SecurityMonitor(clock=self.clock)
        other.observe(event("auth_failure"))
        self.assertEqual(other.summary()["active_correlations"],[])
        self.clock.value=59
        self.assertEqual(self.monitor.observe(event("auth_failure"))["correlation_alerts"],
                         ["authentication_denial_burst"])
        self.assertEqual(other.summary()["active_correlations"],[])
        self.clock.value=60
        self.assertEqual(self.monitor.summary()["active_correlations"],[])

    def test_clock_failure_never_creates_observation(self):
        self.clock.value=1
        self.monitor.observe(event("auth_failure"))
        for value in (float("nan"),float("inf"),True,0):
            self.clock.value=value
            with self.assertRaises(RuntimeError):
                self.monitor.observe(event("auth_failure"))
        self.clock.value=1
        self.assertEqual(self.monitor.summary()["counts"],{"auth_failure":1})

    def test_atomic_counts_and_bounded_windows(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.monitor.observe(event("tool_denied")),range(512)))
        self.assertEqual(sum(bool(r["correlation_alerts"]) for r in results),1)
        report=self.monitor.summary()
        self.assertEqual(report["counts"]["tool_denied"],512)
        self.assertFalse(report["execution_authorized"])
        self.assertFalse(report["compromise_confirmed"])
        self.assertLessEqual(sum(len(w) for w in self.monitor._windows.values()),11)

    def test_artifact_leads_and_benign_controls(self):
        cases=[
            ("runtime_audit","【ARTEX 平台管控·非目标防御】 synthetic event","artex_guard_marker"),
            ("file_created","/fixture/_ca/mitmproxy-ca-cert.pem","artex_recording_ca"),
            ("file_created",r"C:\fixture\_ca\mitmproxy-ca-cert.pem","artex_recording_ca"),
            ("outbound_user_agent","artex-selfupdate","artex_update_indicator"),
            ("inbound_user_agent","artex-enrich/1.0","artex_inbound_indicator"),
        ]
        for channel,value,kind in cases:
            with self.subTest(kind=kind):
                obs=ArtexObservation(channel,value)
                self.assertEqual(classify(obs).kind,kind)
                result=observe_lead(self.monitor,obs)
                self.assertEqual(result["source_revision"],SOURCE_REVISION)
                self.assertFalse(result["compromise_confirmed"])
                self.assertFalse(result["framework_execution_verified"])
                self.assertNotIn(value,json.dumps(result,ensure_ascii=False))
        for channel,value in [
            ("runtime_audit","Documentation quotes 【ARTEX 平台管控·非目标防御】"),
            ("file_created","/fixture/.mitmproxy/mitmproxy-ca-cert.pem"),
            ("outbound_user_agent","ordinary-client"),
            ("inbound_user_agent","ordinary-browser"),
        ]:
            with self.subTest(channel=channel):
                self.assertIsNone(observe_lead(self.monitor,ArtexObservation(channel,value)))

    def test_guard_burst_and_expiry(self):
        obs=ArtexObservation("runtime_audit","【ARTEX 平台管控·非目标防御】 synthetic")
        for _ in range(4):
            self.assertEqual(observe_lead(self.monitor,obs)["correlation_alerts"],[])
        self.assertEqual(observe_lead(self.monitor,obs)["correlation_alerts"],["artex_guard_marker_burst"])
        self.clock.value=600
        self.assertEqual(self.monitor.summary()["active_correlations"],[])

    def test_strict_scope_and_payload_type(self):
        with self.assertRaises(PermissionError):
            ArtexObservation("runtime_audit","placeholder",environment="production",data_class="real")
        for value in ({"secret":"fixture"}, "a"*1025,"\x00"):
            with self.assertRaises(ValueError):
                ArtexObservation("runtime_audit",value)
        with self.assertRaises(ValueError):
            ArtexObservation("arbitrary", "fixture")
        with self.assertRaises(TypeError):
            observe_lead(self.monitor,{"channel":"runtime_audit","value":"fixture"})
        self.assertEqual(self.monitor.summary()["counts"],{})
