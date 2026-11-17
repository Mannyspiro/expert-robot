import math
import unittest
from dot_ai_os.math_lenses import (simplex_weights, convex_blend, n_ality_signature,
    continuum_interpolate, fuzzy_membership, fuzzy_combine, representation_checks, mathematical_lenses_demo)


class MathematicalLensesTests(unittest.TestCase):
    def test_simplex_barycenter_and_vertex_reconstruction(self):
        vertices = ((0., 0.), (3., 0.), (0., 3.))
        self.assertEqual(convex_blend(vertices, (1/3, 1/3, 1/3)), (1., 1.))
        self.assertEqual(convex_blend(vertices, (0., 1., 0.)), vertices[1])

    def test_weights_are_not_silently_normalized(self):
        for weights in ((1., 1.), (-0.1, 1.1), (math.nan, 0.), (True, 0.), (10**1000, 0.)):
            with self.assertRaises(ValueError): simplex_weights(weights)

    def test_dimensions_and_numeric_domains_rejected(self):
        for vertices in (((0.,), (1., 2.)), ((math.inf,), (1.,)), ((), ())):
            with self.assertRaises(ValueError): convex_blend(vertices, (0.5, 0.5))

    def test_axes_remain_independent(self):
        self.assertEqual(n_ality_signature(2, 4, 3, 1), dict(geometric_dimension=2, state_dimension=4, logical_channels=3, temporal_parameters=1))
        for axes in ((True, 2, 2, 1), (2, 0, 2, 1), (2, 2, 2, 99)):
            with self.assertRaises(ValueError): n_ality_signature(*axes)

    def test_piecewise_field_knots_and_interior(self):
        field = ((0., (0., 2.)), (0.5, (2., 4.)), (1., (0., 8.)))
        self.assertEqual(continuum_interpolate(field, 0.5), (2., 4.))
        self.assertEqual(continuum_interpolate(field, 0.75), (1., 6.))
        self.assertEqual(continuum_interpolate(field, 1.), (0., 8.))

    def test_continuum_rejects_bad_gluing_domain_and_extrapolation(self):
        fields = (((0.1, (0.,)), (1., (1.,))), ((0., (0.,)), (0., (1.,)), (1., (2.,))), ((0., (0.,)), (1., (1., 2.))))
        for field in fields:
            with self.assertRaises(ValueError): continuum_interpolate(field, 0.5)
        with self.assertRaises(ValueError): continuum_interpolate(((0., (0.,)), (1., (1.,))), -0.1)

    def test_fuzzy_ramp_is_explicit_bounded_and_monotone(self):
        self.assertEqual([fuzzy_membership(x, 0., 10.) for x in (-1., 0., 5., 10., 20.)], [0., 0., 0.5, 1., 1.])
        with self.assertRaises(ValueError): fuzzy_membership(1., 2., 2.)

    def test_fuzzy_operators_idempotent_and_within_bounds(self):
        for x in (0., 0.25, 0.9, 1.):
            self.assertEqual(fuzzy_combine((x, x), "and_min"), x)
            self.assertAlmostEqual(1-fuzzy_combine((x, 0.6), "and_min"), fuzzy_combine((1-x, 0.4), "or_max"))
        for value in (-0.1, 1.1, math.nan, True):
            with self.assertRaises(ValueError): fuzzy_combine((value,), "and_min")

    def test_every_lens_needs_meaning_and_limits(self):
        row = dict(decision="deferred", reason="Needs a measured model", invariant_or_test="Original acceptance test", limits="No representation-based qualification")
        checks = {name: dict(row) for name in ("simplex", "n_ality", "continuum", "fuzzy_logic")}
        self.assertEqual(len(representation_checks(checks)), 4)
        del checks["continuum"]
        with self.assertRaises(ValueError): representation_checks(checks)

    def test_demo_does_not_promote_or_claim_probabilities(self):
        result = mathematical_lenses_demo({})
        self.assertFalse(result["qualification"])
        self.assertFalse(result["promotion_authority"])
        self.assertIn("not probabilities", result["fuzzy_logic"]["semantics"])
        with self.assertRaises(ValueError): mathematical_lenses_demo({"shell": "command"})


if __name__ == "__main__": unittest.main()
