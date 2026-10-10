#!/usr/bin/env python3
"""Independent, no-execution structural audit of a bounded research receipt.

This checks source/policy identity and internal claims, NOT numerical truth,
Lean correctness, CACE certification, signed provenance or a real experiment.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

REPO = 'Mannyspiro/expert-robot'
SHA40 = re.compile(r'[0-9a-f]{40}\Z')
SHA64 = re.compile(r'[0-9a-f]{64}\Z')
ROUTES = (
    ('reaction-conservation', 'experiment_general_reaction_conservation',
     'Derive exact cellwise reaction conservation with explicit boundary sources.'),
    ('crnt-assumption-search', 'experiment_crnt_deficiency',
     'Find counterexamples to deficiency-zero equilibrium without weak reversibility.'),
    ('enzyme-equilibrium-search', 'experiment_biochemistry_equilibrium',
     'Find positive-equilibrium counterexamples when a rate balance is omitted.'),
    ('parser-contract-search', 'experiment_parser_differential',
     'Mine reduced, bounded toy-parser contract counterexamples.'),
)
KEYS = {
    'schema_version', 'experiment', 'repository', 'source_commit', 'date_utc',
    'policy_sha256', 'episode_id', 'selected_route', 'prior_receipt_used',
    'research_evidence', 'result_sha256', 'candidate',
    'next_route_recommendation', 'conclusion', 'external_network_used',
    'avrea_credits_reserved', 'scientific_truth_or_formal_verification_claimed',
    'promotion_authorized', 'authority_expanded',
}
CANDIDATE_KEYS = {
    'question', 'module_sha256', 'result_sha256', 'status', 'lean_gate',
    'cace_gate', 'promotion_authorized',
}
POLICY_KEYS = {
    'schema_version', 'mode', 'repository', 'fixed_route_ids',
    'max_experiments_per_episode', 'max_artifact_bytes',
    'avrea_credit_reservation', 'network_access_authorized',
    'candidate_writes_authorized', 'automatic_promotion_authorized',
}


def encode(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(obj):
    return hashlib.sha256(encode(obj)).hexdigest()


def bounded_json(path: Path, limit: int):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('missing, symlinked or oversized input')
    return json.loads(path.read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(receipt, policy, expected_commit, root: Path):
    require(isinstance(policy, dict) and set(policy) == POLICY_KEYS, 'policy schema')
    require(policy == {
        'schema_version': 1, 'mode': 'offline_artifact_only', 'repository': REPO,
        'fixed_route_ids': [x[0] for x in ROUTES], 'max_experiments_per_episode': 1,
        'max_artifact_bytes': 65536, 'avrea_credit_reservation': 0,
        'network_access_authorized': False, 'candidate_writes_authorized': False,
        'automatic_promotion_authorized': False,
    }, 'policy must be exact and nonexpanding')
    require(isinstance(receipt, dict) and set(receipt) == KEYS, 'receipt schema')
    require(receipt['schema_version'] == 1 and
            receipt['experiment'] == 'offline-autonomous-research-episode-v1' and
            receipt['repository'] == REPO, 'receipt identity')
    require(isinstance(expected_commit, str) and SHA40.fullmatch(expected_commit) is not None,
            'expected commit must be an independently supplied full SHA')
    require(receipt['source_commit'] == expected_commit, 'source commit mismatch')
    require(receipt['policy_sha256'] == digest(policy), 'policy digest mismatch')
    require(receipt['conclusion'] == 'bounded_offline_experiment_only', 'conclusion')
    for key in ('external_network_used', 'scientific_truth_or_formal_verification_claimed',
                'promotion_authorized', 'authority_expanded'):
        require(receipt[key] is False, 'prohibited claim: ' + key)
    require(type(receipt['avrea_credits_reserved']) is int and
            receipt['avrea_credits_reserved'] == 0, 'unexpected compute reservation')
    require(type(receipt['prior_receipt_used']) is bool, 'prior flag')
    require(SHA64.fullmatch(str(receipt['result_sha256'])) is not None,
            'result hash syntax')
    day = receipt['date_utc']
    require(isinstance(day, str) and len(day) == 10, 'date format')
    try:
        date = dt.date.fromisoformat(day)
    except ValueError as error:
        raise ValueError('invalid ISO date') from error
    require(date.isoformat() == day, 'noncanonical date')
    names = [route[0] for route in ROUTES]
    name = receipt['selected_route']
    require(name in names, 'unregistered route')
    index = names.index(name)
    require(receipt['next_route_recommendation'] == names[(index + 1) % len(names)],
            'inconsistent successor')
    require(receipt['episode_id'] == digest([expected_commit, day, name, digest(policy)]),
            'episode hash mismatch')
    c = receipt['candidate']
    require(isinstance(c, dict) and set(c) == CANDIDATE_KEYS, 'candidate schema')
    require(c['question'] == ROUTES[index][2], 'wrong question')
    require(c['result_sha256'] == receipt['result_sha256'], 'result hash disagreement')
    require(c['promotion_authorized'] is False and
            c['status'] == 'conjecture_or_counterexample_not_proof' and
            c['lean_gate'] == 'requires_exact_kernel_axiom_audit' and
            c['cace_gate'] == 'requires_independent_residual_certificate',
            'unqualified evidence presented as qualified')
    module_path = root / 'scripts' / (ROUTES[index][1] + '.py')
    require(not module_path.is_symlink() and module_path.is_file() and
            module_path.stat().st_size <= 65536, 'missing or unsafe module')
    module_hash = hashlib.sha256(module_path.read_bytes()).hexdigest()
    require(c['module_sha256'] == module_hash, 'module content digest mismatch')
    evidence = receipt['research_evidence']
    require(isinstance(evidence, dict), 'invalid evidence')
    if name == 'reaction-conservation':
        require(evidence == {'toy_cases': 4, 'left_nullities': [2,1,2,1],
                            'exact_balance_residual': '0', 'mutants_detected': True},
                'reaction observation invalid')
    elif name == 'crnt-assumption-search':
        require(evidence == {'deficiency_zero': True, 'irreversible_variant_rejected': True},
                'CRNT observation invalid')
    elif name == 'enzyme-equilibrium-search':
        require(evidence == {'finite_grid_evaluations': 6400, 'counterexample_classes': 4},
                'enzyme observation invalid')
    else:
        require(set(evidence) == {'inputs','original_witnesses','contract_violations','mutant_detection'},
                'parser observation schema')
        require(type(evidence['inputs']) is int and evidence['inputs'] > 0 and
                type(evidence['original_witnesses']) is int and
                evidence['original_witnesses'] > 0 and
                type(evidence['contract_violations']) is int and
                evidence['contract_violations'] == 0 and
                isinstance(evidence['mutant_detection'], dict) and
                bool(evidence['mutant_detection']) and
                all(type(v) is int and v > 0 for v in evidence['mutant_detection'].values()),
                'parser observation invalid')
    require(len(encode(receipt)) <= 65536, 'oversized receipt')
    return {'status': 'structurally_consistent_only',
            'episode_id': receipt['episode_id'], 'source_commit': expected_commit,
            'route': name, 'module_sha256': module_hash,
            'numerical_truth_checked': False, 'lean_kernel_checked': False,
            'cace_certified': False, 'runner_attested': False,
            'promotion_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    policy = bounded_json(args.root / 'config/autonomous_research_policy.json', 8192)
    receipt = bounded_json(args.receipt, 65536)
    print(json.dumps(audit(receipt, policy, args.source_commit, args.root), sort_keys=True))


if __name__ == '__main__':
    main()
