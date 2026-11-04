import unittest
from fractions import Fraction as F

from merlin.representation_graph import (
    Frame, RepresentationGraph, cycle_is_identity, determinant, matrix,
    multiply, inverse, IDENTITY,
)


class RepresentationGraphTests(unittest.TestCase):
    def setUp(self):
        self.frames = RepresentationGraph([
            Frame("cartesian", matrix([[1, 0], [0, 1]])),
            Frame("sheared", matrix([[1, 1], [0, 1]])),
            Frame("rotated", matrix([[0, -1], [1, 0]])),
        ])

    def test_transition_round_trip_is_identity(self):
        forward = self.frames.transition("cartesian", "sheared")
        backward = self.frames.transition("sheared", "cartesian")
        self.assertEqual(multiply(backward, forward), IDENTITY)

    def test_direct_transition_equals_two_step_path(self):
        audit = self.frames.audit_path(["cartesian", "sheared", "rotated"])
        self.assertTrue(audit.consistent)
        self.assertEqual(audit.composed, audit.direct)

    def test_closed_frame_cycle_has_identity_holonomy(self):
        self.assertTrue(cycle_is_identity(
            self.frames, ["cartesian", "sheared", "rotated", "cartesian"]
        ))

    def test_operator_trace_and_determinant_are_basis_invariant(self):
        operator = matrix([[2, 1], [0, 3]])
        expected = (F(5), F(6))
        for frame_id in self.frames.frames:
            self.assertEqual(self.frames.spectral_signature(operator, frame_id), expected)

    def test_eigenvector_coordinates_transform_with_frame(self):
        # A has eigenvector (1,0) for eigenvalue 2.
        operator = matrix([[2, 0], [0, 3]])
        p = self.frames.transition("cartesian", "sheared")
        vector = ((F(1),), (F(0),))
        transformed = (
            (p[0][0] * vector[0][0] + p[0][1] * vector[1][0],),
            (p[1][0] * vector[0][0] + p[1][1] * vector[1][0],),
        )
        a_sheared = self.frames.represented_operator(operator, "sheared")
        lhs = (
            (a_sheared[0][0] * transformed[0][0] + a_sheared[0][1] * transformed[1][0],),
            (a_sheared[1][0] * transformed[0][0] + a_sheared[1][1] * transformed[1][0],),
        )
        rhs = ((2 * transformed[0][0],), (2 * transformed[1][0],))
        self.assertEqual(lhs, rhs)

    def test_singular_frame_is_rejected(self):
        with self.assertRaises(ValueError):
            Frame("collapsed", matrix([[1, 2], [2, 4]]))

    def test_unknown_frame_is_rejected(self):
        with self.assertRaises(KeyError):
            self.frames.transition("missing", "cartesian")

    def test_cycle_must_close(self):
        with self.assertRaises(ValueError):
            cycle_is_identity(self.frames, ["cartesian", "sheared"])

    def test_fraction_arithmetic_is_exact(self):
        a = matrix([[1, 1], [0, 1]])
        self.assertEqual(determinant(a), F(1))
        self.assertEqual(multiply(a, inverse(a)), IDENTITY)


if __name__ == "__main__":
    unittest.main()
