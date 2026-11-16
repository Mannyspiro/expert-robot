from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

from merlin.media_workers import (
    BlenderWorker, ComfyUIWorker, MediaWorkerError, _loopback_base_url,
)


class _Response:
    def __init__(self, value: bytes):
        self.value = value
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size=-1):
        if size < 0:
            size = len(self.value)
        out, self.value = self.value[:size], self.value[size:]
        return out


class MediaWorkerTests(unittest.TestCase):
    def test_loopback_only_endpoint(self):
        self.assertEqual(_loopback_base_url("http://127.0.0.1:8188/"), "http://127.0.0.1:8188")
        for value in ("https://127.0.0.1:8188", "http://example.com:8188",
                      "http://user@127.0.0.1:8188", "http://127.0.0.1:8188/?x=1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _loopback_base_url(value)

    def test_comfyui_submit_poll_download_and_digest(self):
        workflow = {"1": {"class_type": "LoadImage", "inputs": {"image": "sample.png"}}}
        calls = []
        def fake_urlopen(request, timeout=0):
            path = urlsplit(request.full_url).path
            calls.append((request.get_method(), path))
            if path == "/prompt":
                return _Response(b'{"prompt_id":"job_123"}')
            if path == "/api/jobs/job_123":
                return _Response(b'{"status":"completed","version":"0.45.0","outputs":{"9":{"images":[{"filename":"result.png","subfolder":"","type":"output"}]}}}')
            if path == "/view":
                return _Response(b"png-bytes")
            raise AssertionError(request.full_url)
        with tempfile.TemporaryDirectory() as tmp, patch("merlin.media_workers.urlopen", fake_urlopen):
            worker = ComfyUIWorker("http://127.0.0.1:8188", tmp, timeout_seconds=10)
            receipt = worker.execute(workflow)
            self.assertEqual(receipt.worker, "comfyui")
            self.assertEqual(receipt.tool_version, "0.45.0")
            self.assertEqual(receipt.outputs[0]["media_sha256"],
                             __import__("hashlib").sha256(b"png-bytes").hexdigest())
            self.assertTrue(Path(receipt.outputs[0]["path"]).is_file())
            self.assertEqual(calls, [("POST", "/prompt"), ("GET", "/api/jobs/job_123"), ("GET", "/view")])

    def test_comfyui_rejects_unsafe_output_name(self):
        def fake_urlopen(request, timeout=0):
            path = urlsplit(request.full_url).path
            if path == "/prompt":
                return _Response(b'{"prompt_id":"job_123"}')
            if path == "/api/jobs/job_123":
                return _Response(b'{"status":"completed","outputs":[{"filename":"../escape.png"}]}')
            raise AssertionError(request.full_url)
        with tempfile.TemporaryDirectory() as tmp, patch("merlin.media_workers.urlopen", fake_urlopen):
            with self.assertRaises(MediaWorkerError):
                ComfyUIWorker("http://localhost:8188", tmp, timeout_seconds=10).execute({"1": {}})

    def test_comfyui_timeout_cancels_job(self):
        now = [0.0]
        calls = []
        def fake_urlopen(request, timeout=0):
            path = urlsplit(request.full_url).path
            calls.append((request.method, path))
            if path == "/prompt":
                return _Response(b'{"prompt_id":"job_123"}')
            if path == "/api/jobs/job_123":
                return _Response(b'{"status":"running"}')
            if path == "/api/jobs/job_123/cancel":
                return _Response(b'{}')
            raise AssertionError(request.full_url)
        def clock():
            return now[0]
        def sleeper(_):
            now[0] += 1
        with tempfile.TemporaryDirectory() as tmp, patch("merlin.media_workers.urlopen", fake_urlopen):
            worker = ComfyUIWorker("http://127.0.0.1:8188", tmp,
                                   timeout_seconds=1, clock=clock, sleeper=sleeper)
            with self.assertRaisesRegex(MediaWorkerError, "deadline"):
                worker.execute({"1": {}})
        self.assertIn(("POST", "/api/jobs/job_123/cancel"), calls)

    def test_blender_invokes_no_shell_and_records_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executable = root / "blender"
            executable.write_bytes(b"fake")
            executable.chmod(0o755)
            scene = root / "scene.blend"
            scene.write_bytes(b"blend-scene")
            out = root / "out"
            def fake_run(argv, **kwargs):
                self.assertIs(kwargs["shell"], False)
                class Result:
                    returncode = 0
                    stdout = b"Blender 5.3.0"
                if "--version" in argv:
                    return Result()
                self.assertIn("--background", argv)
                self.assertIn("--disable-autoexec", argv)
                out.mkdir(exist_ok=True)
                (out / "merlin-frame-0001.png").write_bytes(b"rendered-png")
                return Result()
            with patch("merlin.media_workers.subprocess.run", fake_run):
                worker = BlenderWorker(executable, root)
                receipt = worker.execute(scene, out)
            self.assertEqual(receipt.worker, "blender")
            self.assertEqual(receipt.status, "completed")
            self.assertEqual(receipt.outputs[0]["size_bytes"], len(b"rendered-png"))

    def test_blender_rejects_scene_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            executable = root / "blender"
            executable.write_bytes(b"fake")
            executable.chmod(0o755)
            outside = Path(other) / "scene.blend"
            outside.write_bytes(b"blend")
            with self.assertRaisesRegex(ValueError, "inside"):
                BlenderWorker(executable, root).execute(outside, root / "out")


if __name__ == "__main__":
    unittest.main()
