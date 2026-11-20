import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from merlin.drafting_control import CHECKS, guide_files, review_wiring, verdict_status
from merlin.wiring_sheet import read_sheet, wire_svg


FIXTURE = Path(__file__).resolve().parents[1] / "examples/merlin/lab-signal-sheet.json"


class DraftControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        raw = FIXTURE.read_bytes()
        title, _, parts, pins, nets = read_sheet(raw)
        svg = wire_svg(title,parts,pins,nets)
        (cls.root/"wiring.svg").write_bytes(svg)
        for name,content in guide_files(raw,svg,nets).items():
            (cls.root/name).write_bytes(content)
        cls.controls = json.loads((cls.root/"draft-controls.json").read_bytes())
        cls.candidate = cls.root/"synthetic-positive.png"
        with Image.open(cls.root/"conditioning-guide.png") as image:
            image.putpixel((1,1),(233,233,222))
            image.save(cls.candidate)
        cls.image_sha = hashlib.sha256(cls.candidate.read_bytes()).hexdigest()
        cls.verdict = {"schema":"merlin-drafting-verdict/1","reviewer":"test fixture",
                       "notes":"Positive control, synthetic edit of a single background pixel.",
                       "source_sha256":cls.controls["source_sha256"],"guide_sha256":cls.controls["guide_sha256"],
                       "image_sha256":cls.image_sha,"checks":dict.fromkeys(CHECKS,"pass"),
                       "nets":[{"id":name,"status":"pass","connections":[
                           {"from":r["from"],"to":r["to"],"status":"pass"} for r in rows]}
                           for name,rows in cls.controls["nets"].items()]}

    def test_controlled_positive_and_unknown_negative(self):
        immutable = (self.root/"wiring.svg").read_bytes()
        for state, decision in (("pass","accepted"),("unknown","rejected"),("fail","rejected")):
            verdict = copy.deepcopy(self.verdict)
            verdict["nets"][0]["connections"][0]["status"] = state
            path = self.root/f"{state}.json"
            path.write_text(json.dumps(verdict))
            result = review_wiring(FIXTURE,self.root,self.candidate,path,self.root/state)
            self.assertEqual(result["decision"],decision)
        self.assertEqual((self.root/"wiring.svg").read_bytes(), immutable)

    def test_stale_hashes_permuted_pins_and_missing_observations_fail_closed(self):
        for key in ("source_sha256","guide_sha256","image_sha256"):
            invalid = dict(self.verdict, **{key:"0"*64})
            with self.assertRaisesRegex(ValueError,"digest"):
                verdict_status(invalid,self.controls,self.image_sha)
        for damage in ("missing_net","missing_global","wrong_pin","repeat_net","missing_pair"):
            invalid = copy.deepcopy(self.verdict)
            if damage=="missing_net":
                invalid["nets"].pop()
            elif damage=="missing_global":
                del invalid["checks"]["geometry"]
            elif damage=="wrong_pin":
                invalid["nets"][0]["connections"][0]["to"]="Display.IN"
            elif damage=="repeat_net":
                invalid["nets"].append(invalid["nets"][0])
            else:
                invalid["nets"][0]["connections"].clear()
            with self.assertRaises(ValueError):
                verdict_status(invalid,self.controls,self.image_sha)

    def test_tampered_guide_fails_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ("draft-controls.json","conditioning-guide.png","image-edit-brief.txt","wiring.svg"):
                (root/name).write_bytes((self.root/name).read_bytes())
            (root/"conditioning-guide.png").write_bytes(self.candidate.read_bytes())
            verdict_path=root/"verdict.json"
            verdict_path.write_text(json.dumps(self.verdict))
            with self.assertRaisesRegex(ValueError,"reconstructed"):
                review_wiring(FIXTURE,root,self.candidate,verdict_path,root/"result")
            self.assertFalse((root/"result").exists())
