"""Negative and end-to-end checks for opt-in Merlin sensing and cross-modal cues."""
from __future__ import annotations

import base64
import hashlib
import http.client
import io
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
import wave
import zlib

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO))

from senses import (
    analyze_png, analyze_wav, decode_media, sensory_fusion, MAX_MEDIA_BYTES,
)
from storage import Store
from tools import ToolSet
from server import create_server


def chunk(tag, payload):
    return (struct.pack(">I", len(payload)) + tag + payload +
            struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff))


def png_rgb(width=2, height=2, color=(255, 0, 0), *, filters=None):
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    stream = b"".join(bytes([(filters or [0] * height)[i]]) +
                      bytes(color) * width for i in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(stream)) + chunk(b"IEND", b"")


def png_rgba(color=(255, 0, 0, 0)):
    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) +
            chunk(b"IDAT", zlib.compress(b"\x00" + bytes(color))) +
            chunk(b"IEND", b""))


def wav_pcm(*, rate=16000, seconds=0.25, channels=1, amplitude=0.35, freq=440.0):
    length = int(rate * seconds)
    samples = []
    for i in range(length):
        value = int(max(-1, min(1, amplitude * math.sin(2 * math.pi * freq * i / rate))) * 32760)
        samples.extend([value] * channels)
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return stream.getvalue()


class SensesTests(unittest.TestCase):
    def test_png_pixel_values_and_synesthesia_are_separate(self):
        data = png_rgb()
        measured = analyze_png(data)
        self.assertEqual(measured["width_px"], 2)
        self.assertEqual(measured["height_px"], 2)
        self.assertEqual(measured["mean_rgb"], [255, 0, 0])
        self.assertEqual(measured["dominant_color_family"], "red")
        self.assertGreater(measured["luminance_0_1"], 0.2)
        self.assertFalse(measured["semantic_object_detection"])
        result = sensory_fusion(image=data, source="user_upload", consent=True)
        self.assertEqual(result["modality"], "vision")
        self.assertEqual(result["synesthetic_cue"]["tone_label"], "C4")
        self.assertTrue(result["synesthetic_cue"]["generated_not_observed"])
        self.assertFalse(result["synesthetic_cue"]["playback_performed"])
        self.assertFalse(result["raw_media_retained"])
        self.assertEqual(result["features"]["source_sha256"], hashlib.sha256(data).hexdigest())

    def test_png_row_filter_family(self):
        # Single pixel has zero left/up predictors, so all PNG filter types
        # decode identically against a blank preceding row.
        for filter_type in range(5):
            with self.subTest(filter=filter_type):
                result = analyze_png(png_rgb(1, 1, filters=[filter_type]))
                self.assertEqual(result["mean_rgb"], [255, 0, 0])

    def test_gray_supported_and_transparency_rejected(self):
        base = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
        data = base + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00\x7f")) + chunk(b"IEND", b"")
        self.assertEqual(analyze_png(data)["mean_rgb"], [127, 127, 127])
        with self.assertRaises(ValueError):
            analyze_png(png_rgba())

    def test_png_corruption_bomb_and_unknown_critical_chunk_fail_closed(self):
        original = png_rgb()
        with self.assertRaises(ValueError):
            analyze_png(original[:-1] + b"\x01")
        with self.assertRaises(ValueError):
            analyze_png(original + b"trailing")
        with self.assertRaises(ValueError):
            analyze_png(original[:12] + b"\x01" + original[13:])
        ihdr = struct.pack(">IIBBBBB", 513, 1, 8, 2, 0, 0, 0)
        with self.assertRaises(ValueError):
            analyze_png(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
                        chunk(b"IDAT", zlib.compress(b"\x00" + b"\0" * (513 * 3))) + chunk(b"IEND", b""))
        base = b"\x89PNG\r\n\x1a\n"
        with self.assertRaises(ValueError):
            analyze_png(base + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) +
                        chunk(b"WXYZ", b"") + chunk(b"IDAT", zlib.compress(b"\x00\x01\x02\x03")) +
                        chunk(b"IEND", b""))
        with self.assertRaises(ValueError):
            analyze_png(base + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) +
                        chunk(b"acTL", b"") + chunk(b"IDAT", zlib.compress(b"\x00\x01\x02\x03")) +
                        chunk(b"IEND", b""))

    def test_corrupted_deflate_with_valid_png_crc_is_rejected_not_500(self):
        header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        bad = (b"\\x89PNG\\r\\n\\x1a\\n" + chunk(b"IHDR", header)
               + chunk(b"IDAT", b"not-compressed-pixels") + chunk(b"IEND", b""))
        with self.assertRaises(ValueError):
            analyze_png(bad)

    def test_audio_signal_features_without_semantic_claim(self):
        raw = wav_pcm()
        feature = analyze_wav(raw)
        self.assertEqual(feature["channels"], 1)
        self.assertEqual(feature["sample_rate_hz"], 16000)
        self.assertAlmostEqual(feature["duration_s"], 0.25)
        self.assertGreater(feature["rms_0_1"], 0.15)
        self.assertLess(feature["rms_0_1"], 0.5)
        self.assertFalse(feature["speech_recognition"])
        result = sensory_fusion(audio=raw, source="microphone_sample", consent=True)
        self.assertEqual(result["modality"], "hearing")
        self.assertTrue(result["synesthetic_cue"]["generated_not_observed"])

    def test_audio_boundaries_silence_and_corruption(self):
        silent = wav_pcm(amplitude=0)
        self.assertEqual(analyze_wav(silent)["rms_0_1"], 0.0)
        self.assertEqual(analyze_wav(wav_pcm(channels=2))["channels"], 2)
        with self.assertRaises(ValueError):
            analyze_wav(b"not-a-wav")
        with self.assertRaises(ValueError):
            analyze_wav(wav_pcm(seconds=3.1, rate=8000))
        with self.assertRaises(ValueError):
            analyze_wav(wav_pcm(rate=6000))

    def test_explicit_consent_and_modality_are_mandatory(self):
        with self.assertRaises(PermissionError):
            sensory_fusion(image=png_rgb(), source="user_upload", consent=False)
        with self.assertRaises(ValueError):
            sensory_fusion(image=png_rgb(), source="microphone_sample", consent=True)
        with self.assertRaises(ValueError):
            sensory_fusion(audio=wav_pcm(), source="screen_snapshot", consent=True)
        with self.assertRaises(ValueError):
            sensory_fusion(image=png_rgb(), audio=wav_pcm(), source="user_upload", consent=True)
        with self.assertRaises(ValueError):
            sensory_fusion(source="user_upload", consent=True)

    def test_canonical_base64_and_binary_limits(self):
        payload = png_rgb()
        encoded = base64.b64encode(payload).decode()
        self.assertEqual(decode_media(encoded, media_type="image/png"), payload)
        for invalid in ("data:image/png;base64," + encoded, encoded + "\n", "!!", ""):
            with self.subTest(invalid=invalid[:12]):
                with self.assertRaises(ValueError):
                    decode_media(invalid, media_type="image/png")
        with self.assertRaises(ValueError):
            decode_media(base64.b64encode(b"x" * (MAX_MEDIA_BYTES + 1)).decode(), media_type="image/png")
        with self.assertRaises(ValueError):
            decode_media(encoded, media_type="image/jpeg")

    def test_workspace_sense_tool_needs_exact_approval_and_detects_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            workspace = root / "workspace"
            workspace.mkdir()
            path = workspace / "sensor.png"
            path.write_bytes(png_rgb())
            tools = ToolSet(workspace, Store(root / "data"), {
                "model_url": "", "model_id": "local", "network_enabled": False,
                "python_enabled": True, "desktop_enabled": False, "max_steps": 8})
            args = {"path": "sensor.png"}
            binding = tools.approval_details("analyze_sensory_file", args)
            with self.assertRaises(PermissionError):
                tools.execute("analyze_sensory_file", args, "unit", approved=False)
            with self.assertRaises(PermissionError):
                tools.execute("analyze_sensory_file", args, "unit", approved=True)
            result = tools.execute("analyze_sensory_file", args, "unit", approved=True,
                                   approval_binding=binding)
            self.assertEqual(result["source"], "workspace_file")
            self.assertEqual(result["modality"], "vision")
            self.assertFalse(result["raw_media_retained"])
            path.write_bytes(png_rgb(color=(0, 0, 255)))
            with self.assertRaises(PermissionError):
                tools.execute("analyze_sensory_file", args, "unit", approved=True,
                              approval_binding=binding)


class LocalSensesApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.server = create_server(data_dir=Path(self.temp.name), start_bundled=False)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.shutdown)
        status, data = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.token = data["session_token"]

    def shutdown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, method, route, data=None, headers=None):
        headers = dict(headers or {})
        body = None
        if method == "POST":
            headers.setdefault("Content-Type", "application/json")
            headers.setdefault("X-Merlin-Token", self.token if hasattr(self, "token") else "")
            body = json.dumps(data, separators=(",", ":")).encode()
        con = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            con.request(method, route, body=body, headers=headers)
            response = con.getresponse()
            return response.status, json.loads(response.read())
        finally:
            con.close()

    def test_live_local_post_and_capabilities(self):
        code, capabilities = self.request("GET", "/api/senses/capabilities")
        self.assertEqual(code, 200)
        self.assertFalse(capabilities["retains_raw_media"])
        blob = base64.b64encode(png_rgb()).decode()
        request = {"media_type": "image/png", "data_base64": blob,
                   "source": "user_upload", "consent": True}
        code, result = self.request("POST", "/api/senses/analyze", request)
        self.assertEqual(code, 200, result)
        self.assertEqual(result["observation"]["features"]["mean_rgb"], [255, 0, 0])
        self.assertNotIn(blob, json.dumps(result))
        self.assertFalse(result["observation"]["action_authority"])

    def test_live_rejects_bad_source_consent_token_cross_origin(self):
        blob = base64.b64encode(png_rgb()).decode()
        request = {"media_type": "image/png", "data_base64": blob,
                   "source": "user_upload", "consent": True}
        for changed, expected in (
            ({"consent": False}, 403),
            ({"source": "microphone_sample"}, 400),
            ({"media_type": "audio/wav"}, 400),
            ({"source": "workspace_file"}, 400),
            ({"extra": "not-allowed"}, 400),
            ({"data_base64": "!!"}, 400),
        ):
            with self.subTest(change=changed):
                code, _ = self.request("POST", "/api/senses/analyze", {**request, **changed})
                self.assertEqual(code, expected)
        code, _ = self.request("POST", "/api/senses/analyze", request,
                               headers={"X-Merlin-Token": "wrong"})
        self.assertEqual(code, 403)
        code, _ = self.request("POST", "/api/senses/analyze", request,
                               headers={"Origin": "https://example.invalid"})
        self.assertEqual(code, 403)


if __name__ == "__main__":
    unittest.main()
