"""Benign decoder-preselection regression; no advisory or malformed samples."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, JpegImagePlugin
from merlin.drafting_control import CHECKS, guide_files, review_wiring
from merlin.wiring_sheet import read_sheet, wire_svg


FIXTURE = Path(__file__).resolve().parents[1] / "examples/merlin/lab-signal-sheet.json"


class PngAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        raw = FIXTURE.read_bytes()
        title, _, parts, pins, nets = read_sheet(raw)
        svg = wire_svg(title, parts, pins, nets)
        (cls.root / "wiring.svg").write_bytes(svg)
        for name, content in guide_files(raw, svg, nets).items():
            (cls.root / name).write_bytes(content)
        cls.controls = json.loads((cls.root / "draft-controls.json").read_bytes())

    def verdict(self, image):
        value = {"schema": "merlin-drafting-verdict/1",
                 "reviewer": "synthetic decoder-admission fixture",
                 "notes": "Fixture supplies a verdict only to test parser admission; no independent visual review claimed.",
                 "source_sha256": self.controls["source_sha256"],
                 "guide_sha256": self.controls["guide_sha256"],
                 "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                 "checks": dict.fromkeys(CHECKS, "pass"),
                 "nets": [{"id": name, "status": "pass", "connections": [
                     {"from": row["from"], "to": row["to"], "status": "pass"}
                     for row in rows]} for name, rows in self.controls["nets"].items()]}
        path = self.root / (image.stem + "-verdict.json")
        path.write_text(json.dumps(value))
        return path

    def test_ordinary_jpeg_is_rejected_before_jpeg_decoder_entry(self):
        image = self.root / "ordinary-jpeg.bin"
        with Image.open(self.root / "conditioning-guide.png") as guide:
            guide.save(image, format="JPEG")
        destination = self.root / "jpeg-review"
        entered = []
        original = JpegImagePlugin.JpegImageFile._open

        def observed_open(asset):
            entered.append(True)
            return original(asset)

        with patch.object(JpegImagePlugin.JpegImageFile, "_open", observed_open):
            with self.assertRaises(ValueError):
                review_wiring(FIXTURE, self.root, image, self.verdict(image), destination)
        self.assertEqual(entered, [], "a rejected non-PNG must not select the JPEG decoder")
        self.assertFalse(destination.exists())

    def test_valid_png_and_existing_unknown_review_gate_are_preserved(self):
        image = self.root / "ordinary-positive.png"
        image.write_bytes((self.root / "conditioning-guide.png").read_bytes())
        verdict_path = self.verdict(image)
        result = review_wiring(FIXTURE, self.root, image, verdict_path, self.root / "png-review")
        self.assertEqual(result["decision"], "accepted")
        self.assertEqual(result["authority"], "illustration review only")
        self.assertEqual(result["source_sha256"], self.controls["source_sha256"])
        self.assertEqual(result["image_sha256"], hashlib.sha256(image.read_bytes()).hexdigest())
        verdict = copy.deepcopy(json.loads(verdict_path.read_bytes()))
        verdict["checks"]["no_extra_connections"] = "unknown"
        verdict_path.write_text(json.dumps(verdict))
        result = review_wiring(FIXTURE, self.root, image, verdict_path, self.root / "unknown-review")
        self.assertEqual(result["decision"], "rejected")


if __name__ == "__main__":
    unittest.main()
