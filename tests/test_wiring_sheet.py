import json
from pathlib import Path
import tempfile
import unittest

from merlin.wiring_sheet import read_sheet, render_wiring

FIXTURE = Path(__file__).resolve().parents[1] / "examples/merlin/lab-signal-sheet.json"


class WiringSheetTests(unittest.TestCase):
    def test_measured_sheet_and_editable_routes(self):
        try:
            import ezdxf
        except ImportError:
            self.skipTest("wiring CAD extra is unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "sheet"
            receipt = render_wiring(FIXTURE, output)
            self.assertEqual([r["length_mm"] for r in receipt["connections"]], [52.0, 62.0])
            cad = ezdxf.readfile(output / "wiring.dxf")
            self.assertEqual(cad.units, ezdxf.units.MM)
            self.assertFalse(cad.audit().errors)
            lines = cad.modelspace().query('LWPOLYLINE[layer=="NET_SAMPLE"]')
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0].get_points("xy"), [(30,30),(48,30),(48,16),(68,16)])
            self.assertEqual([t.value for t in lines[0].get_xdata("MERLIN")],
                             ["SAMPLE", "Sensor.OUT", "Recorder.IN"])
            second = render_wiring(FIXTURE, Path(tmp) / "repeat")
            self.assertEqual(receipt, second)
            with self.assertRaises(FileExistsError):
                render_wiring(FIXTURE, output)

    def test_invalid_endpoint_and_diagonal(self):
        for new_point, message in (([30,31], "endpoints"), ([49,31], "horizontal")):
            with self.subTest(new_point=new_point):
                spec = json.loads(FIXTURE.read_bytes())
                points = spec["nets"][0]["routes"][0]["points"]
                points[0 if message=="endpoints" else 1] = new_point
                with self.assertRaisesRegex(ValueError, message):
                    read_sheet(json.dumps(spec))

    def test_disconnected_net_is_rejected(self):
        spec = json.loads(FIXTURE.read_bytes())
        second = spec["nets"].pop()
        spec["nets"][0]["routes"].extend(second["routes"])
        with self.assertRaisesRegex(ValueError, "disconnected"):
            read_sheet(json.dumps(spec))

    def test_reference_is_only_attribution(self):
        spec = json.loads(FIXTURE.read_bytes())
        ref = {"title": "Sketch", "source": "drawing.jpg", "credit": "Synthetic fixture"}
        spec["reference_image"] = ref
        self.assertEqual(read_sheet(json.dumps(spec))[1], ref)
