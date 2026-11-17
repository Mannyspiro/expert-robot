"""Deterministic reference mathematics, not evidence of improved agent performance."""
from copy import deepcopy
from fractions import Fraction as F
import hashlib
import math
from pathlib import Path
import unittest

from merlin.mathematical_methods import (
    POLICY_TEXT, mathematical_strategy_contract, stationary_three_state,
    parrondo_reference, expected_information_gain,
)
from merlin.scientific_loop import scientific_loop_contract
from merlin.scientific_workflow import WORKFLOW_VERSION, WORKFLOW_TEXT, WORKFLOW_SHA256, scientific_workflow_section


class ParrondoReferenceTests(unittest.TestCase):
    def test_classic_exact_reference_has_losing_components_and_winning_mixture(self):
        r=parrondo_reference()
        self.assertLess(F(r['results']['A']['net_gain_per_step_exact']),0)
        self.assertLess(F(r['results']['B']['net_gain_per_step_exact']),0)
        self.assertGreater(F(r['results']['combined']['net_gain_per_step_exact']),0)
        self.assertTrue(r['strict_parrondo_in_model'])
        self.assertFalse(r['agent_benefit_measured'])
        self.assertFalse(r['promotion_authority'])

    def test_stationary_equations_hold_exactly_for_many_parameters(self):
        for p in [(F(1,10),F(3,4),F(3,4)),(F(0),F(1),F(1)),(F(1),F(1),F(1)),(F(0),F(0),F(0)),(F(1,7),F(2,5),F(3,8))]:
            pi=stationary_three_state(p)
            self.assertEqual(sum(pi),1)
            for i in range(3):
                self.assertEqual(pi[i],pi[(i-1)%3]*p[(i-1)%3]+pi[(i+1)%3]*(1-p[(i+1)%3]))

    def test_independent_forward_iteration_agrees_with_reference(self):
        probs=[F(59,200),F(31,50),F(31,50)]
        expected=stationary_three_state(probs);pi=[1.,0.,0.]
        for _ in range(2000):
            nxt=[0.,0.,0.]
            for i,p in enumerate(probs):
                nxt[(i+1)%3]+=pi[i]*float(p);nxt[(i-1)%3]+=pi[i]*(1-float(p))
            pi=nxt
        for a,b in zip(pi,expected):self.assertAlmostEqual(a,float(b),12)

    def test_zero_bias_is_not_strict_two_losing_games(self):
        r=parrondo_reference(epsilon=F(0))
        self.assertEqual(F(r['results']['A']['net_gain_per_step_exact']),0)
        self.assertEqual(F(r['results']['B']['net_gain_per_step_exact']),0)
        self.assertFalse(r['strict_parrondo_in_model'])

    def test_excess_overhead_eliminates_the_gain(self):
        r=parrondo_reference(combined_cost_per_step=F(1,10))
        self.assertFalse(r['strict_parrondo_in_model'])
        self.assertLess(r['results']['combined']['net_gain_per_step'],0)

    def test_pure_strategy_endpoints_do_not_claim_a_paradox(self):
        for alpha,name in [(F(0),'B'),(F(1),'A')]:
            r=parrondo_reference(probability_A=alpha)
            self.assertFalse(r['strict_parrondo_in_model'])
            self.assertEqual(r['results']['combined'],r['results'][name])

    def test_mixing_state_independent_losing_actions_stays_losing(self):
        for alpha in [F(0),F(1,4),F(1,2),F(1)]:
            p=alpha*F(2,5)+(1-alpha)*F(9,20)
            pi=stationary_three_state([p]*3)
            self.assertLess(sum(v*(2*p-1) for v in pi),0)

    def test_rejects_inexact_and_invalid_parameters(self):
        for changes in [dict(epsilon=.005),dict(epsilon=True),dict(epsilon=-1),dict(epsilon=F(1,10)),
                        dict(probability_A=2),dict(combined_cost_per_step=-1),dict(epsilon=F(1,1<<300))]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):parrondo_reference(**changes)

    def test_stationary_input_validation(self):
        for p in [[F(1,2)]*2,[True,F(1,2),F(1,2)],[F(-1),0,1],[2,0,1],[.5,.5,.5]]:
            with self.subTest(p=p),self.assertRaises(ValueError):stationary_three_state(p)


class InformationGainTests(unittest.TestCase):
    def test_perfect_binary_discrimination_is_one_bit(self):
        r=expected_information_gain([.5,.5],[[1,0],[0,1]])
        self.assertEqual(r['expected_information_bits'],1)
        self.assertEqual(r['prior_entropy_bits'],1)
        self.assertTrue(r['conditional_on_supplied_model'])
        self.assertFalse(r['qualification'])

    def test_identical_likelihoods_have_zero_information(self):
        self.assertAlmostEqual(expected_information_gain([.3,.7],[[.2,.8],[.2,.8]])['expected_information_bits'],0)

    def test_degenerate_prior_has_zero_information(self):
        self.assertEqual(expected_information_gain([1,0],[[1,0],[0,1]])['expected_information_bits'],0)

    def test_noisy_binary_channel_matches_entropy_formula(self):
        r=expected_information_gain([.5,.5],[[.9,.1],[.1,.9]])
        self.assertAlmostEqual(r['expected_information_bits'],1+.9*math.log2(.9)+.1*math.log2(.1))

    def test_perfect_revelation_matches_nonuniform_prior_entropy(self):
        r=expected_information_gain([.1,.9],[[1,0],[0,1]])
        self.assertAlmostEqual(r['expected_information_bits'],-.1*math.log2(.1)-.9*math.log2(.9))

    def test_impossible_observation_columns_are_safe(self):
        r=expected_information_gain([.5,.5],[[1,0,0],[0,1,0]])
        self.assertEqual(r['observation_probabilities'],[.5,.5,0.])
        self.assertEqual(r['expected_information_bits'],1.)

    def test_information_per_cost_is_explicit_and_not_a_policy(self):
        r=expected_information_gain([.5,.5],[[1,0],[0,1]],cost=4,cost_unit='cpu-second')
        self.assertEqual(r['expected_bits_per_cost_unit'],.25)
        self.assertEqual(r['empirical_validation'],'not_assessed')

    def test_rejects_nonfinite_negative_boolean_and_unnormalized_prior(self):
        for p in [[True,0],[float('nan'),.5],[float('inf'),0],[-.2,1.2],[.4,.4],[10**10000,0],[]]:
            with self.subTest(kind=type(p)),self.assertRaises(ValueError):expected_information_gain(p,[[1,0],[0,1]])

    def test_rejects_missing_incompatible_or_unnormalized_rows(self):
        for rows in [[[1,0]],[[1,0],[1]],[[.3,.3],[.5,.5]],[[float('nan'),0],[1,0]]]:
            with self.subTest(rows=rows),self.assertRaises(ValueError):expected_information_gain([.5,.5],rows)

    def test_rejects_invalid_cost_and_overflow(self):
        for cost in [0,-1,True,float('nan'),float('inf'),10**10000,1e-320]:
            with self.subTest(kind=type(cost)),self.assertRaises(ValueError):expected_information_gain([.5,.5],[[1,0],[0,1]],cost=cost)

    def test_rejects_invalid_cost_units(self):
        for unit in ['',None,'x'*81]:
            with self.subTest(unit=unit),self.assertRaises(ValueError):expected_information_gain([.5,.5],[[1,0],[0,1]],cost_unit=unit)

    def test_bounds_and_no_mutation(self):
        p=[.2,.3,.5];rows=[[.1,.9],[.5,.5],[.8,.2]];old=deepcopy((p,rows))
        r=expected_information_gain(p,rows)
        self.assertGreaterEqual(r['expected_information_bits'],0)
        self.assertLessEqual(r['expected_information_bits'],r['prior_entropy_bits'])
        self.assertEqual((p,rows),old)


class SharedPolicyTests(unittest.TestCase):
    def test_both_roles_get_same_contract(self):
        p=mathematical_strategy_contract()
        self.assertEqual(p['audience'],['hermes','hermes-teacher'])
        self.assertEqual(scientific_loop_contract()['mathematical_strategy_policy'],p)

    def test_prompt_policy_is_inside_workflow_hash(self):
        self.assertEqual(WORKFLOW_VERSION,'merlin-scientific-workflow/2')
        self.assertIn(POLICY_TEXT,WORKFLOW_TEXT)
        self.assertEqual(hashlib.sha256(WORKFLOW_TEXT.encode()).hexdigest(),WORKFLOW_SHA256)
        self.assertIn(POLICY_TEXT,scientific_workflow_section())

    def test_contract_is_fresh_and_does_not_grant_authority(self):
        p=mathematical_strategy_contract();p['audience'].append('spoof')
        q=mathematical_strategy_contract();self.assertNotIn('spoof',q['audience'])
        for key in ['qualification','promotion_authority','automatic_adoption']:self.assertIs(q[key],False)

    def test_policy_keeps_null_results_holdout_and_noninferiority(self):
        for phrase in ['null and reverse','heldout','noninferiority','not_applicable','state/history','integrability']:
            self.assertIn(phrase,POLICY_TEXT)

    def test_gate_selects_teacher_and_math_suites(self):
        text=(Path(__file__).resolve().parents[1]/'scripts/merlin_research_stack_gate.py').read_text()
        self.assertIn('"test_hermes_teacher.py"',text)
        self.assertIn('"test_mathematical_methods.py"',text)


if __name__=='__main__':unittest.main()
