"""Development mechanism checks; independent frozen evaluation lives elsewhere."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageChops, ImageDraw, ImageEnhance
from merlin.drafting_control import CHECKS, guide_files, review_wiring
from merlin.drafting_raster import check_registered_raster
from merlin.wiring_sheet import read_sheet, wire_svg


FIXTURE = Path(__file__).resolve().parents[1] / "examples/merlin/lab-signal-sheet.json"


def png(image):
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class RegisteredRasterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        raw = FIXTURE.read_bytes()
        title, _, parts, pins, nets = read_sheet(raw)
        svg = wire_svg(title, parts, pins, nets)
        (cls.root / "wiring.svg").write_bytes(svg)
        files = guide_files(raw, svg, nets)
        for name, data in files.items():
            (cls.root / name).write_bytes(data)
        cls.guide = files["conditioning-guide.png"]
        cls.controls = json.loads(files["draft-controls.json"])
        with Image.open(io.BytesIO(cls.guide)) as src:
            cls.image = src.convert("RGB")

    def check(self, image):
        return check_registered_raster(self.guide, png(image), self.controls)

    def test_exact_guide_is_clear_and_bound_to_all_bytes(self):
        result = check_registered_raster(self.guide, self.guide, self.controls)
        self.assertEqual(result["status"], "clear_within_scope")
        self.assertEqual(result["measurement"]["unexplained_ink_pixels"], 0)
        self.assertEqual(result["image_sha256"], hashlib.sha256(self.guide).hexdigest())
        self.assertFalse(result["qualification"])
        self.assertFalse(result["promotion_authority"])

    def test_light_global_paper_tone_keeps_declared_ink_scope(self):
        result = self.check(ImageEnhance.Brightness(self.image).enhance(0.95))
        self.assertEqual(result["status"], "clear_within_scope", result)

    def test_long_extra_stroke_is_measured_without_net_identity(self):
        image = self.image.copy()
        ImageDraw.Draw(image).line([(550, 900), (750, 900)], fill=(15, 35, 40), width=4)
        result = self.check(image)
        self.assertEqual(result["status"], "unexpected_stroke", result)
        self.assertGreater(result["stroke_like_component_count"], 0)
        self.assertTrue(any(row["longest_axis_run_px"] >= 32 for row in result["components"]))
        self.assertNotIn("nets", result)

    def test_route_attached_added_branch_requires_review(self):
        route = next(iter(self.controls["nets"].values()))[0]["vertices_px"]
        a, b = route[:2]
        point = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        image = self.image.copy()
        ImageDraw.Draw(image).line([point, (point[0], point[1] + 90)], fill=(15, 35, 40), width=4)
        result = self.check(image)
        self.assertEqual(result["status"], "unexpected_stroke", result)

    def test_short_added_dot_abstains_instead_of_certifying(self):
        image = self.image.copy()
        ImageDraw.Draw(image).ellipse((697, 897, 703, 903), fill=(15, 35, 40))
        result = self.check(image)
        self.assertEqual((result["status"], result["reason"]), ("unknown", "ambiguous_unmodeled_ink"))

    def test_shifted_registration_abstains(self):
        result = self.check(ImageChops.offset(self.image, 6, 0))
        self.assertEqual((result["status"], result["reason"]), ("unknown", "registration_not_established"))

    def test_transparent_or_rescaled_candidates_abstain(self):
        image = self.image.convert("RGBA")
        image.putpixel((700, 900), (20, 20, 20, 0))
        for candidate in (image, self.image.resize((768, 512))):
            with self.subTest(size=candidate.size):
                self.assertEqual(self.check(candidate)["status"], "unknown")

    def test_missing_sheet_content_abstains(self):
        image = self.image.copy()
        ImageDraw.Draw(image).rectangle((150, 120, 1400, 900), fill=(255, 255, 255))
        result = self.check(image)
        self.assertEqual((result["status"], result["reason"]), ("unknown", "guide_ink_not_preserved"))

    def test_residual_pixel_and_component_budgets_abstain(self):
        image = self.image.copy()
        ImageDraw.Draw(image).rectangle((400, 800, 800, 900), fill=(0, 0, 0))
        result = self.check(image)
        self.assertEqual(result["reason"], "residual_pixel_budget_exceeded")
        image = self.image.copy()
        draw = ImageDraw.Draw(image)
        for y in range(805, 940, 3):
            for x in range(400, 700, 3):
                draw.point((x, y), fill=(0, 0, 0))
        result = self.check(image)
        self.assertEqual((result["status"], result["reason"]), ("unknown", "component_budget_exceeded"))
        self.assertFalse(result["component_scan_complete"])
        self.assertLessEqual(len(result["components"]), 32)

    def test_guide_tamper_and_scope_mismatch_abstain(self):
        for key, value in (("guide_sha256", "0" * 64), ("canvas_px", [768, 512]),
                           ("fiducials_px", {})):
            controls = copy.deepcopy(self.controls)
            controls[key] = value
            result = check_registered_raster(self.guide, self.guide, controls)
            self.assertEqual(result["reason"], "guide_identity_or_scope_mismatch")

    def test_integration_is_opt_in_and_cannot_override_uncertain_human_verdict(self):
        image = self.image.copy()
        ImageDraw.Draw(image).line([(550, 900), (750, 900)], fill=(15, 35, 40), width=4)
        candidate = self.root / "added-stroke.png"
        candidate.write_bytes(png(image))
        verdict = {"schema": "merlin-drafting-verdict/1", "reviewer": "development fixture",
                   "notes": "Intentionally false all-pass label tests independence of the extra-ink measurement.",
                   "source_sha256": self.controls["source_sha256"],
                   "guide_sha256": self.controls["guide_sha256"],
                   "image_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                   "checks": dict.fromkeys(CHECKS, "pass"), "nets": [
                       {"id": name, "status": "pass", "connections": [
                           {"from": row["from"], "to": row["to"], "status": "pass"}
                           for row in rows]} for name, rows in self.controls["nets"].items()]}
        path = self.root / "verdict.json"
        path.write_text(json.dumps(verdict))
        default = review_wiring(FIXTURE, self.root, candidate, path, self.root / "default")
        measured = review_wiring(FIXTURE, self.root, candidate, path, self.root / "measured", independent_raster=True)
        self.assertEqual(default["decision"], "accepted")
        self.assertNotIn("raster_check", default)
        self.assertEqual(measured["decision"], "rejected")
        self.assertEqual(measured["raster_check"]["status"], "unexpected_stroke")
        # Even a clean raster measurement must not overrule an uncertain human.
        candidate.write_bytes(self.guide)
        verdict["image_sha256"] = hashlib.sha256(self.guide).hexdigest()
        verdict["checks"]["no_extra_connections"] = "unknown"
        path.write_text(json.dumps(verdict))
        unknown = review_wiring(FIXTURE, self.root, candidate, path, self.root / "uncertain", independent_raster=True)
        self.assertEqual(unknown["raster_check"]["status"], "clear_within_scope")
        self.assertEqual(unknown["decision"], "rejected")


if __name__ == "__main__":
    unittest.main()
