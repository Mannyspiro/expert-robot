"""Mamba-inspired complex-state reference invariants; no neural model executed."""
import math
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin.mamba_complex_state_reference import (
    rotating_state, rotating_history, complex_state_report
)

class ComplexStateTests(unittest.TestCase):
    def test_direct_and_recurrent_complex_state_agree(self):
        rng=random.Random(23)
        x=[complex(rng.uniform(-1,1),rng.uniform(-1,1)) for _ in range(32)]
        for rho in (0,0.25,0.8,1.0):
            for theta in (0,0.25,-1.0,math.pi):
                fast=rotating_state(x,retention=rho,angle=theta)
                direct=rotating_history(x,retention=rho,angle=theta)
                self.assertLess(max(abs(a-b) for a,b in zip(fast,direct)),1e-11)

    def test_state_norm_bound_induction(self):
        x=[complex(2,-3),-3,3j,2.5,-2j]
        for rho in (0,0.5,0.999,1):
            report=complex_state_report(x,retention=rho,angle=math.pi/3)
            self.assertLessEqual(report["max_state_magnitude"],report["max_input_magnitude"]+1e-12)

    def test_zero_retention_is_memoryless(self):
        x=[1,2-1j,-3,0j]
        self.assertEqual(rotating_state(x,retention=0,angle=0.7),list(map(complex,x)))

    def test_full_retention_with_zero_initial_state_stays_zero(self):
        x=[1,2,3]
        self.assertEqual(rotating_state(x,retention=1,angle=0.5),[0j]*3)

    def test_zero_phase_reduces_real_scalar_recurrence(self):
        x=[1.,-1.,0.,2.]
        z=rotating_state(x,retention=0.6,angle=0)
        from merlin.simulated_parallax_models import state_recurrence
        y=state_recurrence(x,0.6)
        self.assertLess(max(abs(a.real-b) for a,b in zip(z,y)),1e-12)
        self.assertTrue(all(abs(a.imag)<1e-12 for a in z))

    def test_reject_nonfinite_or_unbounded_arguments(self):
        for values,rho,angle in (([],0.5,0),([1],-0.1,0),([1],1.1,0),
                                 ([1],0.5,float("nan")),([float("inf")],0.5,0),
                                 ([1],0.5,100)):
            with self.subTest(values=values,rho=rho,angle=angle),self.assertRaises(ValueError):
                rotating_state(values,retention=rho,angle=angle)
        with self.assertRaises(ValueError):rotating_state([1]*2049)

    def test_report_no_model_or_novel_math_claim(self):
        result=complex_state_report([1,0,1],retention=0.7,angle=0.2)
        self.assertFalse(result["actual_mamba3_model_executed"])
        self.assertFalse(result["novel_xenomaths_proved"])
        self.assertFalse(result["physically_realized_device_claim"])
        self.assertFalse(result["production_qualified"])
        self.assertLess(result["max_abs_error_against_direct_history"],1e-12)

if __name__=="__main__":
    unittest.main()
