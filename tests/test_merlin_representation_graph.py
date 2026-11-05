import unittest
from fractions import Fraction as F

from merlin.representation_graph import (
    Frame, RepresentationGraph, cycle_is_identity, determinant, matrix,
    multiply, inverse, identity, characteristic_polynomial,
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
        self.assertEqual(multiply(backward, forward), identity(2))

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
        operator = matrix([[2, 0], [0, 3]])
        p = self.frames.transition("cartesian", "sheared")
        vector = (F(1), F(0))
        transformed = tuple(sum(p[i][j] * vector[j] for j in range(2)) for i in range(2))
        a_sheared = self.frames.represented_operator(operator, "sheared")
        lhs = tuple(sum(a_sheared[i][j] * transformed[j] for j in range(2)) for i in range(2))
        rhs = tuple(2 * x for x in transformed)
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
        self.assertEqual(multiply(a, inverse(a)), identity(2))

    def test_five_dimensional_frames_preserve_operator_invariants(self):
        shear = matrix([
            [1, 1, 0, 0, 0],
            [0, 1, 1, 0, 0],
            [0, 0, 1, 1, 0],
            [0, 0, 0, 1, 1],
            [0, 0, 0, 0, 1],
        ])
        reverse = matrix([
            [0, 0, 0, 0, 1],
            [0, 0, 0, 1, 0],
            [0, 0, 1, 0, 0],
            [0, 1, 0, 0, 0],
            [1, 0, 0, 0, 0],
        ])
        graph = RepresentationGraph([
            Frame("canonical5", identity(5)),
            Frame("shear5", shear),
            Frame("reverse5", reverse),
        ])
        operator = matrix([
            [1, 1, 0, 0, 0],
            [0, 2, 1, 0, 0],
            [0, 0, 3, 1, 0],
            [0, 0, 0, 4, 1],
            [0, 0, 0, 0, 5],
        ])
        expected = (F(15), F(120))
        for frame_id in graph.frames:
            self.assertEqual(graph.spectral_signature(operator, frame_id), expected)
        self.assertTrue(cycle_is_identity(
            graph, ["canonical5", "shear5", "reverse5", "canonical5"]
        ))


    def test_characteristic_polynomial_is_exact_and_basis_invariant(self):
        operator = matrix([[2, 1, 0], [0, 2, 1], [0, 0, 3]])
        expected = (F(1), F(-7), F(16), F(-12))
        self.assertEqual(characteristic_polynomial(operator), expected)
        frames = RepresentationGraph([
            Frame("canonical3", identity(3)),
            Frame("shear3", matrix([[1, 1, 0], [0, 1, 1], [0, 0, 1]])),
            Frame("reverse3", matrix([[0, 0, 1], [0, 1, 0], [1, 0, 0]])),
        ])
        for frame_id in frames.frames:
            represented = frames.represented_operator(operator, frame_id)
            self.assertEqual(characteristic_polynomial(represented), expected)

    def test_characteristic_polynomial_rejects_invalid_shapes(self):
        with self.assertRaises(ValueError):
            characteristic_polynomial(())
        with self.assertRaises(ValueError):
            characteristic_polynomial(((F(1), F(2)),))

    def test_mixed_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            RepresentationGraph([
                Frame("two", identity(2)),
                Frame("three", identity(3)),
            ])


if __name__ == "__main__":
    unittest.main()
