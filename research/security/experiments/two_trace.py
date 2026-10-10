#!/usr/bin/env python3
"""Finite, entirely synthetic two-trace noninterference experiment.

NOT a CPU simulator, hardware exploit, side-channel measurement or proof.
No external packages, network I/O, subprocesses or attacker-provided code.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

PUBLIC = (0, 1)
SECRET = (0, 1, 2, 3)
MODELS = ('public_only', 'speculative_cache', 'squashed_cache', 'secret_timing')


def execute(public, secret, model):
    if type(public) is not int or public not in PUBLIC:
        raise ValueError('invalid public input')
    if type(secret) is not int or secret not in SECRET:
        raise ValueError('invalid secret input')
    if model not in MODELS:
        raise ValueError('unknown model')
    # Synthetic architectural result never depends on secret.
    result = ('ALLOWED' if public else 'DENIED')
    cache = {f'public:{public}'}
    clock = 10 + public
    if model == 'speculative_cache':
        # Abstract hypothetical squashed branch leaves one secret-indexed line.
        cache.add(f'transient:{secret}')
    elif model == 'squashed_cache':
        # Abstract rollback erases ALL transient traces: toy mitigation only.
        scratch = {f'transient:{secret}'}
        scratch.clear()
    elif model == 'secret_timing':
        clock += secret
    return {'architectural': result,
            'microarchitectural': [sorted(cache), clock]}


def observed(state, layer):
    if layer == 'architectural':
        return state['architectural']
    if layer == 'joint':
        return [state['architectural'], state['microarchitectural']]
    raise ValueError('unknown observation layer')


def independent_oracle(public, a, b, model, layer):
    """Closed-form oracle independent of execute() and observed()."""
    if layer == 'architectural':
        return True
    if layer != 'joint':
        raise ValueError('observation layer')
    if model in ('public_only', 'squashed_cache'):
        return True
    if model in ('speculative_cache', 'secret_timing'):
        return a == b
    raise ValueError('unknown model')


def experiment():
    cases = []
    for model in MODELS:
        for layer in ('architectural', 'joint'):
            violations = []
            checked = 0
            for public in PUBLIC:
                for a, b in itertools.combinations(SECRET, 2):
                    left = observed(execute(public, a, model), layer)
                    right = observed(execute(public, b, model), layer)
                    equal = left == right
                    if equal != independent_oracle(public, a, b, model, layer):
                        raise AssertionError('oracle disagreement')
                    checked += 1
                    if not equal:
                        violations.append({'public': public, 'secret_pair': [a, b]})
            cases.append({'model': model, 'observation_layer': layer,
                          'pairs_checked': checked, 'noninterference': not violations,
                          'violation_count': len(violations),
                          'first_counterexample': violations[0] if violations else None})
    expected = {('speculative_cache', 'joint'), ('secret_timing', 'joint')}
    actual = {(x['model'], x['observation_layer']) for x in cases if not x['noninterference']}
    if actual != expected:
        raise AssertionError('deliberate leakage controls undetected')
    return {'schema_version': 1, 'experiment': 'bounded-two-trace-hyperproperty-v1',
            'models': list(MODELS), 'public_domain': list(PUBLIC),
            'secret_domain': list(SECRET), 'cases': cases,
            'pairs_checked_total': sum(x['pairs_checked'] for x in cases),
            'external_network_used': False, 'hardware_observed': False,
            'formal_lean_verified': False, 'cace_executed': False,
            'promotion_authorized': False, 'authority_expanded': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    data = experiment()
    payload = json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(payload.encode()) > 8192:
        raise ValueError('report exceeded bound')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + '\n', encoding='utf-8')
    print(json.dumps({'status': 'synthetic_experiment_only',
                      'report_sha256': hashlib.sha256(payload.encode()).hexdigest(),
                      'pairs_checked': data['pairs_checked_total']}))


if __name__ == '__main__':
    main()
