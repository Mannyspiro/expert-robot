"""Parallax-inspired local linear estimator mathematical reference tests."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin.parallax_local_linear_reference import local_constant,local_linear,affine_boundary_experiment

class LocalLinearReferenceTests(unittest.TestCase):
    def test_affine_signal_reproduced_at_boundary(self):
        r=affine_boundary_experiment()
        self.assertEqual(r["local_linear"]["status"],"local_linear")
        self.assertLess(r["absolute_errors"]["linear"],1e-10)
        self.assertGreater(r["absolute_errors"]["constant"],0.1)
        self.assertFalse(r["parallax_kernel_executed"])

    def test_any_affine_data_predicts_query_with_distinct_samples(self):
        xs=[-3,-1,1,3]
        for q in (-2.0,0.0,2.0):
            ys=[4.5-1.75*x for x in xs]
            r=local_linear(xs,ys,q,3.0)
            self.assertEqual(r["status"],"local_linear")
            self.assertAlmostEqual(r["estimate"],4.5-1.75*q,places=10)

    def test_constant_signal_is_reproduced_by_both(self):
        x=[0,1,2,3];y=[7,7,7,7]
        self.assertAlmostEqual(local_constant(x,y,0.0,1.2)["estimate"],7,places=10)
        self.assertAlmostEqual(local_linear(x,y,0.0,1.2)["estimate"],7,places=10)

    def test_duplicate_coordinates_fallback_without_false_affine_claim(self):
        r=local_linear([1,1,1],[2,4,6],1,1)
        self.assertEqual(r["status"],"fallback_local_constant")
        self.assertAlmostEqual(r["estimate"],4.0)
        self.assertFalse(r["production_qualified"])

    def test_effectively_zero_local_variance_falls_back(self):
        r=local_linear([0,10000],[1,2],0,0.01)
        self.assertEqual(r["status"],"fallback_local_constant")
        self.assertAlmostEqual(r["estimate"],1.0)

    def test_invalid_lengths_and_numbers_are_rejected(self):
        for xs,ys,q,h in (([],[],0,1),([1],[1,2],0,1),([1],[1],0,0),([1],[1],float("nan"),1),([1],[float("inf")],0,1)):
            with self.subTest(case=(xs,ys,q,h)),self.assertRaises(ValueError):
                local_linear(xs,ys,q,h)
        with self.assertRaises(ValueError):local_linear([1],[2],0,1,singularity_tolerance=-1)

    def test_no_neural_or_novelty_claims_in_reference_results(self):
        r=affine_boundary_experiment()
        self.assertFalse(r["trained_model_evaluated"])
        self.assertFalse(r["novel_math_proven"])
        self.assertFalse(r["production_qualified"])

if __name__=="__main__":
    unittest.main()
