import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from cad_mcfc_model import (
    transform_point, multiply, inverse_affine, validate_wiring,
    validate_rigid,
)


class CadMcfcTests(unittest.TestCase):
    def test_affine_transform(self):
        matrix = [[1, 0, 0, 2], [0, 1, 0, 3], [0, 0, 1, 4], [0, 0, 0, 1]]
        self.assertEqual(transform_point(matrix, [1, 1, 1]), [3, 4, 5])

    def test_affine_inverse_round_trip(self):
        matrix = [[1, 0, 0, 2], [0, 1, 0, 3], [0, 0, 1, 4], [0, 0, 0, 1]]
        self.assertEqual(transform_point(inverse_affine(matrix), [3, 4, 5]), [1, 1, 1])
        identity = multiply(matrix, inverse_affine(matrix))
        for i in range(4):
            for j in range(4):
                self.assertAlmostEqual(identity[i][j], 1 if i == j else 0)

    def test_singular_transform_has_no_inverse(self):
        singular = [[1, 0, 0, 0], [0, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        with self.assertRaises(ValueError):
            inverse_affine(singular)

    def test_rigid_transform_rejects_reflection(self):
        reflection = [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        with self.assertRaises(ValueError):
            validate_rigid(reflection)

    def test_wiring_net(self):
        result = validate_wiring([{
            "connection_id": "c1", "from_node": "J1", "from_pin": "1",
            "to_node": "R1", "to_pin": "1", "net_name": "VCC",
        }])
        self.assertIn("VCC", result["nets"])

    def test_pin_cannot_belong_to_two_nets(self):
        connections = [
            {"connection_id": "c1", "from_node": "J1", "from_pin": "1",
             "to_node": "R1", "to_pin": "1", "net_name": "VCC"},
            {"connection_id": "c2", "from_node": "J1", "from_pin": "1",
             "to_node": "R2", "to_pin": "1", "net_name": "GND"},
        ]
        with self.assertRaises(ValueError):
            validate_wiring(connections)


if __name__ == "__main__":
    unittest.main()
