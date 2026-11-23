"""Fail-closed sandbox cancellation tests using a blocking SDK fixture."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import threading
import unittest

STUDIO = Path(__file__).resolve().parents[1] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
from sandbox_backend import execute_approved, SandboxBoundaryError

IMAGE = "registry.example/merlin-python@sha256:" + "a" * 64


class BlockingSandbox:
    def __init__(self, *, kill_error=False):
        self.id = "sandbox-cancel-fixture"
        self.entered = threading.Event()
        self.release = threading.Event()
        self.kill_error = kill_error
        self.killed = False
        self.closed = False
        self.destroyed = False
        self.written = False
        self.commands = SimpleNamespace(run=self.run)
        self.files = SimpleNamespace(write_files=self.write)

    def get_egress_policy(self):
        return SimpleNamespace(default_action="deny", egress=[])

    def write(self, entries):
        self.written = True
        self.written_bytes = entries[0].data

    def run(self, command, *, opts):
        if command != "python -I -B /tmp/merlin_approved.py":
            raise AssertionError("wrong command")
        self.entered.set()
        if not self.release.wait(timeout=8):
            raise RuntimeError("fixture worker did not receive kill/finish")
        if self.killed:
            raise RuntimeError("synthetic remote stream interrupted")
        return SimpleNamespace(
            exit_code=0, logs=SimpleNamespace(
                stdout=[SimpleNamespace(text="fixture reply\n")], stderr=[]))

    def kill(self):
        if self.kill_error:
            raise RuntimeError("synthetic control-plane outage")
        self.killed = True
        self.release.set()

    def close(self):
        self.closed = True

    def destroy(self):
        self.destroyed = True
        self.release.set()


def sdk(instance):
    return SimpleNamespace(
        SandboxSync=SimpleNamespace(create=lambda *a, **k: instance),
        ConnectionConfigSync=lambda **k: SimpleNamespace(**k),
        WriteEntry=lambda **k: SimpleNamespace(**k),
        RunCommandOpts=lambda **k: SimpleNamespace(**k),
        NetworkPolicy=lambda **k: SimpleNamespace(**k))


class CancellationTests(unittest.TestCase):
    def run_in_thread(self, instance):
        flag = threading.Event()
        holder = {}
        def worker():
            try:
                holder["value"] = execute_approved(
                    b"print('hello')\n", image=IMAGE, timeout=8,
                    sdk=sdk(instance), cancelled=flag.is_set)
            except BaseException as exc:
                holder["error"] = exc
        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(instance.entered.wait(3), "Fixture command never started")
        return flag, holder, thread

    def test_cancel_running_command_requires_remote_kill_and_closes_sdk(self):
        instance = BlockingSandbox()
        flag, holder, thread = self.run_in_thread(instance)
        flag.set()
        thread.join(timeout=4)
        self.assertFalse(thread.is_alive(), "Cancellation monitor did not finish")
        self.assertIsInstance(holder.get("error"), InterruptedError)
        self.assertNotIn("value", holder)
        self.assertTrue(instance.killed)
        self.assertTrue(instance.closed)
        self.assertFalse(instance.destroyed, "Remote kill must not be repeated")
        self.assertEqual(instance.written_bytes, b"print('hello')\n")

    def test_control_plane_kill_failure_never_reports_clean_cancellation(self):
        instance = BlockingSandbox(kill_error=True)
        flag, holder, thread = self.run_in_thread(instance)
        flag.set()
        thread.join(timeout=4)
        self.assertFalse(thread.is_alive())
        self.assertIsInstance(holder.get("error"), RuntimeError)
        self.assertNotIsInstance(holder["error"], InterruptedError)
        self.assertTrue(instance.destroyed, "Normal cleanup should retry after failed kill")
        self.assertFalse(instance.closed)
        self.assertNotIn("value", holder)

    def test_cancel_before_create_never_creates_a_sandbox(self):
        calls = []
        instance = BlockingSandbox()
        fake = sdk(instance)
        fake.SandboxSync = SimpleNamespace(create=lambda *a, **k: calls.append(1))
        with self.assertRaises(InterruptedError):
            execute_approved(b"print(1)\n", image=IMAGE, timeout=8,
                             sdk=fake, cancelled=lambda: True)
        self.assertEqual(calls, [])

    def test_non_cancelled_result_preserves_identity_and_destroys(self):
        instance = BlockingSandbox()
        flag, holder, thread = self.run_in_thread(instance)
        instance.release.set()
        thread.join(timeout=4)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", holder)
        self.assertEqual(holder["value"]["stdout"], "fixture reply\n")
        self.assertEqual(holder["value"]["sandbox_id"], instance.id)
        self.assertTrue(instance.destroyed)
        self.assertFalse(instance.killed)


if __name__ == "__main__":
    unittest.main()
