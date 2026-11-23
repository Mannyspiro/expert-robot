"""Invariants of the small simulated two-channel recurrence baseline."""
import math
from pathlib import Path
import random
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"python"))
from merlin.simulated_parallax_models import (
    quadratic_reference,state_recurrence,truncated_local,
    phase_space_hybrid,run_reference_experiment
)

class SimulatedParallaxTests(unittest.TestCase):
    def test_exact_recurrence_identity_to_floating_precision(self):
        for n in (1,2,16,100):
            for a in (0.0,0.2,0.75,1.0):
                rng=random.Random(n)
                signal=[rng.uniform(-1,1) for _ in range(n)]
                x=quadratic_reference(signal,a)
                y=state_recurrence(signal,a)
                self.assertLessEqual(max(abs(p-q) for p,q in zip(x,y)),1e-12)

    def test_bounded_state_for_inputs_in_interval(self):
        samples=[-7,7,-7,1,2,0,7]
        for a in (0.0,0.13,0.5,0.99,1.0):
            self.assertTrue(all(abs(x)<=7 for x in state_recurrence(samples,a)))

    def test_lipschitz_bound_for_matched_gate(self):
        x=[1,0,1,-1,2,3]
        y=[v+0.125 for v in x]
        for a in (0,0.1,0.8,1):
            self.assertTrue(all(abs(p-q)<=0.125+1e-12 for p,q in
                                zip(state_recurrence(x,a),state_recurrence(y,a))))

    def test_window_one_and_full_window(self):
        sig=[1,-1,2,3]
        self.assertEqual(truncated_local(sig,0.5,1),[0.5,-0.5,1.0,1.5])
        self.assertLess(max(abs(x-y) for x,y in zip(
            truncated_local(sig,0.5,4),quadratic_reference(sig,0.5))),1e-12)

    def test_phase_simplex_endpoints(self):
        sig=[1,2,0,-1]
        self.assertEqual(phase_space_hybrid(sig,0.8,2,0),state_recurrence(sig,0.8))
        self.assertEqual(phase_space_hybrid(sig,0.8,2,1),truncated_local(sig,0.8,2))

    def test_hybrid_is_convex_mixture(self):
        sig=[1,-1,1,-1,0]
        y=phase_space_hybrid(sig,0.7,3,0.3)
        a=state_recurrence(sig,0.7);b=truncated_local(sig,0.7,3)
        self.assertTrue(all(min(x,z)-1e-12<=m<=max(x,z)+1e-12
                            for x,z,m in zip(a,b,y)))

    def test_invalid_parameters_fail_closed(self):
        with self.assertRaises(ValueError):state_recurrence([float("nan")])
        with self.assertRaises(ValueError):state_recurrence([1],-0.01)
        with self.assertRaises(ValueError):truncated_local([1],0.5,0)
        with self.assertRaises(ValueError):phase_space_hybrid([1],0.5,3,1.1)
        with self.assertRaises(ValueError):run_reference_experiment(n=4096)

    def test_actual_host_benchmark_does_not_claim_general_model_gain(self):
        r=run_reference_experiment(n=48,seed=8)
        self.assertTrue(r["actual_host_runtime_measured"])
        self.assertFalse(r["trained_model_evaluated"])
        self.assertFalse(r["physical_hardware_equivalence_proven"])
        self.assertFalse(r["formal_proof_assistant_executed"])
        self.assertLess(r["variants"]["scalar_recurrence"]["max_abs_error_vs_reference"],1e-12)
        self.assertTrue(all(math.isfinite(v["elapsed_seconds"]) and v["elapsed_seconds"]>=0
                            for v in r["variants"].values()))

if __name__=="__main__":
    unittest.main()
