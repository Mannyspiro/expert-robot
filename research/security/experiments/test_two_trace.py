#!/usr/bin/env python3
"""Independent negative controls for the finite synthetic CPU experiment."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name('two_trace.py')
spec = importlib.util.spec_from_file_location('two_trace', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class TwoTraceTests(unittest.TestCase):
    def test_closed_form_oracle_and_cartesian_coverage(self):
        data = m.experiment()
        self.assertEqual(data['pairs_checked_total'], 96)
        self.assertEqual(len(data['cases']), 8)
        self.assertTrue(all(c['pairs_checked'] == 12 for c in data['cases']))
        self.assertFalse(data['formal_lean_verified'])
        self.assertFalse(data['promotion_authorized'])

    def test_architecture_does_not_leak_in_any_fixture(self):
        self.assertTrue(all(c['noninterference'] for c in m.experiment()['cases']
                            if c['observation_layer'] == 'architectural'))

    def test_joint_micro_observation_detects_deliberate_mutants(self):
        cases = {(c['model'], c['observation_layer']): c for c in m.experiment()['cases']}
        for name in ('speculative_cache', 'secret_timing'):
            self.assertEqual(cases[(name, 'joint')]['violation_count'], 12)
            self.assertEqual(cases[(name, 'joint')]['first_counterexample'],
                             {'public': 0, 'secret_pair': [0, 1]})
        for name in ('public_only', 'squashed_cache'):
            self.assertTrue(cases[(name, 'joint')]['noninterference'])

    def test_tampered_observer_detected_by_independent_oracle(self):
        actual = m.execute(0, 0, 'speculative_cache')
        changed = m.execute(0, 1, 'speculative_cache')
        self.assertNotEqual(m.observed(actual, 'joint'), m.observed(changed, 'joint'))
        self.assertTrue(m.independent_oracle(0, 0, 1, 'speculative_cache', 'architectural'))
        self.assertFalse(m.independent_oracle(0, 0, 1, 'speculative_cache', 'joint'))

    def test_rejects_out_of_domain_inputs(self):
        for args in [(True, 0, 'public_only'), (1, 4, 'public_only'),
                     (0, 0, 'unknown'), (0, -1, 'public_only')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                m.execute(*args)
        with self.assertRaises(ValueError):
            m.observed(m.execute(0, 0, 'public_only'), 'secret')

    def test_deterministic_and_no_file_or_network_activity(self):
        self.assertEqual(m.experiment(), m.experiment())
        self.assertEqual(len(m.experiment()['models']), 4)
        self.assertFalse(m.experiment()['hardware_observed'])
        self.assertFalse(m.experiment()['external_network_used'])


if __name__ == '__main__':
    unittest.main()
