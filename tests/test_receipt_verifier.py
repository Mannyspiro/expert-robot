#!/usr/bin/env python3
"""Standalone regression checks; no network, runner or experiment execution."""
import copy
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / 'scripts/verify_autonomous_research_receipt.py'
spec = importlib.util.spec_from_file_location('receipt_verifier', PATH)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
COMMIT = 'b' * 40
POLICY = {
    'schema_version': 1, 'mode': 'offline_artifact_only',
    'repository': 'Mannyspiro/expert-robot',
    'fixed_route_ids': [x[0] for x in verifier.ROUTES],
    'max_experiments_per_episode': 1, 'max_artifact_bytes': 65536,
    'avrea_credit_reservation': 0, 'network_access_authorized': False,
    'candidate_writes_authorized': False, 'automatic_promotion_authorized': False,
}

class ReceiptVerification(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'scripts').mkdir()
        (self.root / 'config').mkdir()
        (self.root / 'config/autonomous_research_policy.json').write_text(json.dumps(POLICY))
        module = self.root / 'scripts/experiment_general_reaction_conservation.py'
        module.write_text('# synthetic source for checksum fixture\n')
        module_sha = hashlib.sha256(module.read_bytes()).hexdigest()
        day = '2026-10-11'
        policy_sha = verifier.digest(POLICY)
        self.receipt = {
            'schema_version': 1,
            'experiment': 'offline-autonomous-research-episode-v1',
            'repository': verifier.REPO, 'source_commit': COMMIT,
            'date_utc': day, 'policy_sha256': policy_sha,
            'episode_id': verifier.digest([COMMIT, day, 'reaction-conservation', policy_sha]),
            'selected_route': 'reaction-conservation', 'prior_receipt_used': False,
            'research_evidence': {'toy_cases': 4, 'left_nullities': [2,1,2,1],
                                  'exact_balance_residual': '0', 'mutants_detected': True},
            'result_sha256': 'c' * 64,
            'candidate': {
                'question': verifier.ROUTES[0][2], 'module_sha256': module_sha,
                'result_sha256': 'c' * 64,
                'status': 'conjecture_or_counterexample_not_proof',
                'lean_gate': 'requires_exact_kernel_axiom_audit',
                'cace_gate': 'requires_independent_residual_certificate',
                'promotion_authorized': False,
            },
            'next_route_recommendation': 'crnt-assumption-search',
            'conclusion': 'bounded_offline_experiment_only',
            'external_network_used': False, 'avrea_credits_reserved': 0,
            'scientific_truth_or_formal_verification_claimed': False,
            'promotion_authorized': False, 'authority_expanded': False,
        }

    def test_accepts_consistent_structural_evidence(self):
        result = verifier.audit(self.receipt, POLICY, COMMIT, self.root)
        self.assertEqual(result['status'], 'structurally_consistent_only')
        self.assertFalse(result['runner_attested'])
        self.assertFalse(result['numerical_truth_checked'])

    def test_denies_provenance_mutation(self):
        variants = [('episode_id', '0' * 64), ('source_commit', 'd'*40),
                    ('policy_sha256', 'e'*64), ('date_utc', '2026-10-12'),
                    ('next_route_recommendation', 'parser-contract-search')]
        for field, value in variants:
            with self.subTest(field=field):
                bad = copy.deepcopy(self.receipt); bad[field] = value
                with self.assertRaises(ValueError):
                    verifier.audit(bad, POLICY, COMMIT, self.root)

    def test_denies_unqualified_authority_and_schema(self):
        for field, value in [('promotion_authorized', True),
                             ('authority_expanded', True),
                             ('external_network_used', True),
                             ('avrea_credits_reserved', False),
                             ('scientific_truth_or_formal_verification_claimed', True)]:
            with self.subTest(field=field):
                bad = copy.deepcopy(self.receipt); bad[field] = value
                with self.assertRaises(ValueError):
                    verifier.audit(bad, POLICY, COMMIT, self.root)
        bad = copy.deepcopy(self.receipt)
        bad['candidate']['lean_gate'] = 'passed'
        with self.assertRaises(ValueError):
            verifier.audit(bad, POLICY, COMMIT, self.root)
        bad = copy.deepcopy(self.receipt); bad['unexpected'] = True
        with self.assertRaises(ValueError):
            verifier.audit(bad, POLICY, COMMIT, self.root)

    def test_requires_source_module_hash(self):
        mod = self.root / 'scripts/experiment_general_reaction_conservation.py'
        mod.write_text('# changed module\n')
        with self.assertRaisesRegex(ValueError, 'module content digest mismatch'):
            verifier.audit(self.receipt, POLICY, COMMIT, self.root)

    def test_rejects_laundered_results(self):
        bad = copy.deepcopy(self.receipt)
        bad['research_evidence']['exact_balance_residual'] = '1/2'
        with self.assertRaisesRegex(ValueError, 'reaction observation invalid'):
            verifier.audit(bad, POLICY, COMMIT, self.root)
        bad = copy.deepcopy(self.receipt)
        bad['candidate']['result_sha256'] = 'e'*64
        with self.assertRaisesRegex(ValueError, 'result hash disagreement'):
            verifier.audit(bad, POLICY, COMMIT, self.root)

    def test_input_file_bounds(self):
        p = self.root/'receipt.json'
        p.write_text('x'*66000)
        with self.assertRaises(ValueError):
            verifier.bounded_json(p,65536)
        symlink=self.root/'receipt_link.json'
        symlink.symlink_to(p)
        with self.assertRaises(ValueError):
            verifier.bounded_json(symlink,65536)

if __name__ == '__main__':
    unittest.main()
