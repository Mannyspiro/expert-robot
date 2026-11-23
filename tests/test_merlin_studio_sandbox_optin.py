"""Opt-in Studio sandbox authority and portable source tests; no Docker required."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "portable" / "merlin_studio"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))
import tools as studio_tools
import sandbox_backend

IMAGE = "registry.example/merlin-python@sha256:" + "a"*64
OTHER_IMAGE = "registry.example/merlin-python@sha256:" + "b"*64


class StudioOptInTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "workspace"
        self.workspace.mkdir()
        self.script = self.workspace / "answer.py"
        self.script.write_bytes(b"print(6 * 7)\n")
        self.settings = {"python_enabled": True, "network_enabled": False,
                         "desktop_enabled": False}
        self.args = {"path": "answer.py"}
        self.owner_id = "a" * 32
        self.run_id = "b" * 32
        self.recovery = SimpleNamespace(
            ready=True, owner_id=self.owner_id,
            reserve=lambda run, digest: self.owner_id,
            complete=lambda run: {"cleanup_confirmed": True})
        self.store = SimpleNamespace(sandbox_recovery=self.recovery)

    def make_tool(self):
        return studio_tools.ToolSet(self.workspace, self.store, self.settings)

    @staticmethod
    def tool_names(tool):
        return [a["function"]["name"] for a in tool.schemas()]

    def test_host_worker_remains_default_and_is_not_falsely_sandboxed(self):
        with patch.dict(os.environ, {"MERLIN_PYTHON_BACKEND": "host"}, clear=False):
            tool = self.make_tool()
            self.assertIn("run_python", self.tool_names(tool))
            caps = tool.capabilities()
            self.assertTrue(caps["python"])
            self.assertFalse(caps["python_sandbox"])
            self.assertEqual(caps["python_backend"], "host")
            self.assertIn("not an OS sandbox", next(s for s in tool.schemas()
                if s["function"]["name"] == "run_python")["function"]["description"])
            binding = tool.approval_details("run_python", self.args)
            self.assertEqual(set(binding), {"script_sha256", "script_bytes"})
            self.assertEqual(binding["script_sha256"], hashlib.sha256(self.script.read_bytes()).hexdigest())

    def test_sandbox_requires_per_script_approval_and_copies_exact_bytes(self):
        env = {"MERLIN_PYTHON_BACKEND": "opensandbox", "MERLIN_SANDBOX_IMAGE": IMAGE,
               "MERLIN_SANDBOX_PORT": "8080"}
        with patch.dict(os.environ, env, clear=False):
            tool = self.make_tool()
            caps = tool.capabilities()
            self.assertTrue(caps["python"])
            self.assertTrue(caps["python_sandbox"])
            self.assertEqual(caps["python_backend"], "opensandbox")
            self.assertIn("OpenSandbox container", next(s for s in tool.schemas()
                if s["function"]["name"] == "run_python")["function"]["description"])
            approval = tool.approval_details("run_python", self.args)
            self.assertEqual(approval["backend"], "opensandbox")
            self.assertEqual(approval["sandbox_image"], IMAGE)
            self.assertEqual(approval["sandbox_port"], 8080)
            self.assertEqual(approval["script_bytes"], len(self.script.read_bytes()))
            answer = {"exit_code": 0, "stdout": "42\n", "stderr": "",
                      "truncated": False, "termination": "completed",
                      "os_sandbox": True, "sandbox_provider": "OpenSandbox",
                      "sandbox_id": "sandbox-accepted-1", "network_policy": "deny"}
            calls = []
            def generate(source, *, image, port, timeout, cancelled, owner_id, run_id):
                calls.append((source, image, port, timeout, owner_id, run_id))
                return {**answer, "script_sha256": hashlib.sha256(source).hexdigest()}
            with patch.object(sandbox_backend, "execute_approved", side_effect=generate), \
                 patch.object(studio_tools.subprocess, "Popen",
                              side_effect=AssertionError("host must never execute")):
                with self.assertRaises(PermissionError):
                    tool.execute("run_python", self.args, "run-1",
                                 approval_binding=approval, approved=False)
                response = tool.execute("run_python", self.args, self.run_id,
                                        approval_binding=approval, approved=True, timeout=9)
            self.assertEqual(calls, [(self.script.read_bytes(), IMAGE, 8080, 9,
                                      self.owner_id, self.run_id)])
            self.assertEqual(response["stdout"], "42\n")
            self.assertTrue(response["os_sandbox"])
            self.assertEqual(response["sandbox_id"], "sandbox-accepted-1")
            self.assertEqual(response["script_sha256"], approval["script_sha256"])

    def test_missing_image_or_invalid_port_never_falls_back_to_host(self):
        for bad in [
            {"MERLIN_PYTHON_BACKEND": "opensandbox", "MERLIN_SANDBOX_IMAGE": "",
             "MERLIN_SANDBOX_PORT": "8080"},
            {"MERLIN_PYTHON_BACKEND": "opensandbox", "MERLIN_SANDBOX_IMAGE": "python:latest",
             "MERLIN_SANDBOX_PORT": "8080"},
            {"MERLIN_PYTHON_BACKEND": "opensandbox", "MERLIN_SANDBOX_IMAGE": IMAGE,
             "MERLIN_SANDBOX_PORT": "bad"},
            {"MERLIN_PYTHON_BACKEND": "opensandbox", "MERLIN_SANDBOX_IMAGE": IMAGE,
             "MERLIN_SANDBOX_PORT": "80"},
            {"MERLIN_PYTHON_BACKEND": "not-an-approved-backend", "MERLIN_SANDBOX_IMAGE": IMAGE,
             "MERLIN_SANDBOX_PORT": "8080"},
        ]:
            with self.subTest(bad=bad), patch.dict(os.environ, bad, clear=False):
                tool = self.make_tool()
                self.assertNotIn("run_python", self.tool_names(tool))
                self.assertFalse(tool.capabilities()["python"])
                self.assertFalse(tool.capabilities()["python_sandbox"])
                self.assertTrue(tool.capabilities()["python_setup_required"])
                with patch.object(studio_tools.subprocess, "Popen",
                                  side_effect=AssertionError("host fallback forbidden")), \
                     patch.object(sandbox_backend, "execute_approved",
                                  side_effect=AssertionError("sandbox not configured")):
                    with self.assertRaises(ValueError):
                        tool.execute("run_python", self.args, "run-2", approved=True,
                                     approval_binding={"script_sha256": hashlib.sha256(self.script.read_bytes()).hexdigest()})

    def test_changed_script_or_backend_or_image_requires_fresh_approval(self):
        with patch.dict(os.environ, {"MERLIN_PYTHON_BACKEND": "opensandbox",
                                     "MERLIN_SANDBOX_IMAGE": IMAGE, "MERLIN_SANDBOX_PORT": "8080"}, clear=False):
            tool = self.make_tool()
            binding = tool.approval_details("run_python", self.args)
            with patch.object(sandbox_backend, "execute_approved",
                              side_effect=AssertionError("unapproved action reached sandbox")):
                tool.sandbox_image = OTHER_IMAGE
                with self.assertRaises(PermissionError):
                    tool.execute("run_python", self.args, "run-3",
                                 approved=True, approval_binding=binding)
                tool.sandbox_image = IMAGE
                tool.sandbox_port = 8081
                with self.assertRaises(PermissionError):
                    tool.execute("run_python", self.args, "run-3",
                                 approved=True, approval_binding=binding)
                tool.sandbox_port = 8080
                self.script.write_text("print(999)")
                with self.assertRaises(PermissionError):
                    tool.execute("run_python", self.args, "run-3",
                                 approved=True, approval_binding=binding)
                self.script.write_text("print(6 * 7)\n")
                tool.python_backend = "host"
                with self.assertRaises(PermissionError):
                    tool.execute("run_python", self.args, "run-3",
                                 approved=True, approval_binding=binding)

    def test_approval_cannot_be_replayed_after_switch_host_to_sandbox(self):
        with patch.dict(os.environ, {"MERLIN_PYTHON_BACKEND": "host"}, clear=False):
            tool = self.make_tool()
            host_binding = tool.approval_details("run_python", self.args)
        with patch.dict(os.environ, {"MERLIN_PYTHON_BACKEND": "opensandbox",
                                     "MERLIN_SANDBOX_IMAGE": IMAGE, "MERLIN_SANDBOX_PORT": "8080"}, clear=False):
            tool = self.make_tool()
            with patch.object(sandbox_backend, "execute_approved",
                              side_effect=AssertionError("approval mismatch must stop")):
                with self.assertRaises(PermissionError):
                    tool.execute("run_python", self.args, "run-4",
                                 approved=True, approval_binding=host_binding)

    def test_cancel_before_and_after_is_reported_without_host_fallback(self):
        with patch.dict(os.environ, {"MERLIN_PYTHON_BACKEND": "opensandbox",
                                     "MERLIN_SANDBOX_IMAGE": IMAGE, "MERLIN_SANDBOX_PORT": "8080"}, clear=False):
            tool = self.make_tool()
            binding = tool.approval_details("run_python", self.args)
            with patch.object(sandbox_backend, "execute_approved",
                              side_effect=AssertionError("cancelled command reached sandbox")):
                with self.assertRaises(InterruptedError):
                    tool.execute("run_python", self.args, "run-5", cancelled=lambda: True,
                                 approved=True, approval_binding=binding)
            cancel_state = {"cancelled": False}
            def generated(*args, **kwargs):
                cancel_state["cancelled"] = True
                return {"exit_code": 0, "os_sandbox": True}
            with patch.object(sandbox_backend, "execute_approved", side_effect=generated):
                with self.assertRaises(InterruptedError):
                    tool.execute("run_python", self.args, "run-5",
                                 cancelled=lambda: cancel_state["cancelled"],
                                 approved=True, approval_binding=binding)

    def test_unverified_recovery_disables_python_without_host_fallback(self):
        with patch.dict(os.environ, {"MERLIN_PYTHON_BACKEND": "opensandbox",
                                     "MERLIN_SANDBOX_IMAGE": IMAGE, "MERLIN_SANDBOX_PORT": "8080"}, clear=False):
            self.recovery.ready = False
            tool = self.make_tool()
            self.assertFalse(tool.capabilities()["python"])
            self.assertTrue(tool.capabilities()["python_setup_required"])
            self.assertNotIn("run_python", self.tool_names(tool))
            with patch.object(studio_tools.subprocess, "Popen",
                              side_effect=AssertionError("host fallback forbidden")):
                with self.assertRaises(ValueError):
                    tool.execute("run_python", self.args, self.run_id, approved=True,
                                 approval_binding={"script_sha256": hashlib.sha256(self.script.read_bytes()).hexdigest()})

    def test_portable_builder_allowlists_optional_module_without_vendoring_sdk(self):
        spec = importlib.util.spec_from_file_location("studio_portable_build", ROOT / "portable" / "build_portable.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        sources, origins = builder.collect_sources()
        self.assertEqual(sources["sandbox_backend.py"], (STUDIO / "sandbox_backend.py").read_bytes())
        self.assertEqual(origins["sandbox_backend.py"], "portable/merlin_studio/sandbox_backend.py")
        self.assertEqual(sources["sandbox_recovery.py"], (STUDIO / "sandbox_recovery.py").read_bytes())
        self.assertNotIn("opensandbox/", "".join(sorted(sources)))
        self.assertNotIn("third_party/", "".join(sorted(sources)))
        with patch.dict(os.environ, {"MERLIN_PYTHON_BACKEND": "host"}, clear=False):
            self.assertNotIn("opensandbox", sys.modules)
            self.assertFalse(self.make_tool().capabilities()["python_sandbox"])


if __name__ == "__main__":
    unittest.main()
