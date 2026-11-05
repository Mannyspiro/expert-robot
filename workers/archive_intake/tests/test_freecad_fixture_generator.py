import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "freecad-runtime"))
from generate_fixture import generate_fixture


class FakeShape:
    def __init__(self, kind):
        self.kind = kind
        self.translation = (0, 0, 0)

    def translate(self, vector):
        self.translation = vector


class FakeObject:
    def __init__(self, name):
        self.Name = name
        self.Label = name
        self.Group = []
        self.Shape = None

    def addObject(self, obj):
        self.Group.append(obj)


class FakeDocument:
    def __init__(self):
        self.Name = "Fixture"
        self.objects = []

    def addObject(self, kind, name):
        obj = FakeObject(name)
        self.objects.append(obj)
        return obj

    def recompute(self):
        pass

    def saveAs(self, path):
        Path(path).write_bytes(b"fake native document")


class FakeApp:
    def __init__(self):
        self.doc = None

    def newDocument(self, name):
        self.doc = FakeDocument()
        self.doc.Name = name
        return self.doc

    def Vector(self, x, y, z):
        return (x, y, z)

    def closeDocument(self, name):
        self.doc = None


class FakePart:
    def makeBox(self, *dimensions):
        return FakeShape(("box", dimensions))

    def makeCylinder(self, *dimensions):
        return FakeShape(("cylinder", dimensions))

    def export(self, objects, path):
        Path(path).write_bytes((",".join(obj.Name for obj in objects)).encode())


class FixtureGeneratorTests(unittest.TestCase):
    def test_generates_hash_manifest_and_expected_analytic_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            app = FakeApp()
            manifest = generate_fixture(temp, app=app, part=FakePart())
            root = Path(temp)
            self.assertTrue((root / "merlin-fixture-v1.FCStd").is_file())
            self.assertTrue((root / "merlin-fixture-v1.step").is_file())
            saved = json.loads((root / "fixture-manifest.json").read_text())
            self.assertEqual(saved, manifest)
            for filename, record in manifest["artifacts"].items():
                self.assertEqual(
                    hashlib.sha256((root / filename).read_bytes()).hexdigest(),
                    record["sha256"],
                )
            self.assertEqual(manifest["expected"]["component_count"], 3)
            self.assertAlmostEqual(
                manifest["expected"]["sum_of_shape_volumes_mm3"],
                600 + 24 * 3.141592653589793,
            )
            self.assertEqual(manifest["assembly_groups"]["UpperSubassembly"],
                             ["UpperBlock", "RoundPost"])
            self.assertIsNone(app.doc)

if __name__ == "__main__":
    unittest.main()
