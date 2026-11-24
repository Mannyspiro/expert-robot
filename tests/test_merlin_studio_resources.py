"""Resource observations and loopback boundary tests, not hardware qualification."""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable/merlin_studio"))
import resources
from engine import Application
from server import StudioServer


class ResourceObservations(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proc, self.group, self.dev = (self.root / name for name in ("proc", "group", "dev"))
        for path in (self.proc / "self", self.proc / "123", self.group, self.dev):
            path.mkdir(parents=True)

    def snapshot(self, **kwargs):
        return resources.resource_snapshot(self.root, self.root, proc_root=self.proc,
            group_root=self.group, dev_root=self.dev, **kwargs)

    def test_actual_kernel_values_are_distinct_and_unknown_is_not_zero(self):
        (self.proc / "meminfo").write_text("MemTotal: 9000 kB\nMemAvailable: 2000 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n")
        (self.proc / "self/status").write_text("VmRSS: 17 kB\nVmHWM: 21 kB\n")
        (self.proc / "123/status").write_text("VmRSS: 300 kB\nVmHWM: 400 kB\n")
        result = self.snapshot(model_pid=123)
        self.assertEqual(result["memory"]["available_bytes"], 2000 * 1024)
        self.assertEqual(result["processes"]["studio_rss_bytes"], 17 * 1024)
        self.assertEqual(result["processes"]["owned_model_rss_bytes"], 300 * 1024)
        self.assertEqual(result["memory"]["swap_total_bytes"], 0)
        self.assertIsNone(result["gpu"]["vram_bytes"])
        self.assertEqual(result["gpu"]["compute_readiness"], "not_probed")
        self.assertIsNone(self.snapshot()["processes"]["owned_model_rss_bytes"])

    def test_malformed_units_negative_and_oversized_input_stay_unknown(self):
        (self.proc / "meminfo").write_text("MemTotal: 9000 MB\nMemAvailable: -42 kB\nSwapTotal: 99999999999999999 kB\n")
        result = self.snapshot()
        self.assertTrue(all(result["memory"][key] is None for key in ("total_bytes", "available_bytes", "swap_total_bytes")))
        (self.proc / "meminfo").write_bytes(b"x" * (resources.MAX_READ + 1))
        self.assertIsNone(self.snapshot()["memory"]["total_bytes"])

    def test_cgroup_limit_does_not_replace_host_total(self):
        (self.proc / "self/cgroup").write_text("0::/test-scope\n")
        folder = self.group / "test-scope"
        folder.mkdir()
        (folder / "memory.current").write_text("1048576\n")
        (folder / "memory.max").write_text("2097152\n")
        result = self.snapshot()
        self.assertEqual(result["cgroup"]["current_bytes"], 1048576)
        self.assertEqual(result["cgroup"]["limit_bytes"], 2097152)
        self.assertIsNone(result["memory"]["total_bytes"])
        (folder / "memory.max").write_text("max\n")
        result = self.snapshot()
        self.assertIsNone(result["cgroup"]["limit_bytes"])
        self.assertTrue(result["cgroup"]["unlimited_at_visible_scope"])

    def test_cgroup_traversal_and_arbitrary_pid_are_not_read(self):
        (self.proc / "self/cgroup").write_text("0::/../outside\n")
        (self.root / "outside").mkdir()
        (self.root / "outside/memory.current").write_text("12345")
        (self.root / "outside/memory.max").write_text("12346")
        result = self.snapshot(model_pid="../outside")
        self.assertIsNone(result["cgroup"]["current_bytes"])
        self.assertIsNone(result["processes"]["owned_model_rss_bytes"])

    def test_device_node_observation_never_qualifies_compute(self):
        (self.dev / "nvidia0").touch()
        result = self.snapshot()
        self.assertEqual(result["gpu"]["observed_device_nodes"], ["nvidia0"])
        self.assertEqual(result["gpu"]["compute_readiness"], "not_probed")
        self.assertIsNone(result["gpu"]["vram_bytes"])


class ResourceBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Application(Path(self.temp.name), Path(self.temp.name) / "state", start_bundled=False)
        self.server = StudioServer(("127.0.0.1", 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, headers):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request("GET", "/api/resources", headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_snapshot_requires_session_token_and_same_origin(self):
        self.assertEqual(self.request({})[0], 403)
        token = {"X-Merlin-Token": self.server.session_token}
        self.assertEqual(self.request({**token, "Origin": "https://untrusted.invalid"})[0], 403)
        self.assertEqual(self.request({**token, "Host": "untrusted.invalid"})[0], 403)
        status, value = self.request(token)
        self.assertEqual(status, 200)
        self.assertEqual(value["schema"], "merlin-studio-resources/1")
        self.assertEqual(self.app.store.conversations(), [])

    def test_offline_command_saves_observation_with_canonical_artifact_reference(self):
        conversation = self.app.store.create_conversation()
        run_id = self.app.store.start_run(conversation["id"], "/resources")
        value = json.loads(self.app._command(run_id, "/resources"))
        self.assertEqual(value["schema"], "merlin-studio-resources/1")
        events = self.app.store.run(run_id)["events"]
        observation = [event for event in events if event["type"] == "resource_observation"]
        self.assertEqual(len(observation), 1)
        self.assertIn("artifact_ref", observation[0])
        with self.assertRaisesRegex(ValueError, "without arguments"):
            self.app._command(run_id, "/resources change-system")


if __name__ == "__main__":
    unittest.main()
