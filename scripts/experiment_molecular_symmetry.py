#!/usr/bin/env python3
"""Bounded exploratory molecular symmetry experiment; no cache promotion."""
import argparse
import copy
import json
import os
import time
from decimal import Decimal
from pathlib import Path

from generate_molecular_matter import generate
from evaluate_molecular_quantum import baseline
from molecular_symmetry_equivalence import equivalent

TOLERANCE = 1e-7  # Hartree; prespecified numerical comparison, not a proof.


def variants(graph):
    result = {}
    for name in ('translation', 'quarter_turn', 'atom_reordering', 'bond_stretch'):
        g = copy.deepcopy(graph)
        for a in g['nodes']:
            x, y, z = map(float, a['position'])
            if name == 'translation':
                p = tuple(str(Decimal(str(v)) + shift)
                          for v, shift in zip(a['position'], (2, -3, 1)))
            elif name == 'quarter_turn':
                p = (-y, x, z)
            elif name == 'bond_stretch':
                p = (1.1 * x, 1.1 * y, 1.1 * z)
            else:
                p = (x, y, z)
            a['position'] = list(p)
        if name == 'atom_reordering':
            g['nodes'].reverse()
        result[name] = g
    return result


def experiment():
    cases = []
    uncached_seconds = 0.0
    cached_seconds = 0.0
    cache_hits = 0
    cache_misses = 0
    for name, smiles in [('water', 'O'), ('methane', 'C'), ('ammonia', 'N')]:
        graph = generate(smiles, name + '-symmetry', conformers=2, seed=1729)['matter_graph']
        start = time.perf_counter()
        reference = baseline(graph)
        uncached_seconds += time.perf_counter() - start
        trials = []
        for transformation, changed in variants(graph).items():
            start = time.perf_counter()
            observed = baseline(changed)
            uncached_seconds += time.perf_counter() - start
            differences = [abs(a['total_electronic_energy_hartree'] -
                               b['total_electronic_energy_hartree'])
                           for a, b in zip(reference['scf_results'], observed['scf_results'])]
            invariant = transformation != 'bond_stretch'
            passed = (all(d <= TOLERANCE for d in differences) if invariant
                      else all(d > TOLERANCE for d in differences))
            trials.append({'transformation': transformation, 'expected_invariant': invariant,
                           'absolute_energy_differences_hartree': differences,
                           'passed': passed, 'input': changed, 'quantum_result': observed})
        # Separate measured run: equivalence lookup plus fresh calculations on misses.
        cache = []
        cached_checks = []
        start = time.perf_counter()
        for current, expected in [(graph, reference)] + [
                (t['input'], t['quantum_result']) for t in trials]:
            reused = next((energies for saved, energies in cache
                           if equivalent(saved, current)), None)
            hit = reused is not None
            if hit:
                cache_hits += 1
            else:
                cache_misses += 1
                reused = [r['total_electronic_energy_hartree']
                          for r in baseline(current)['scf_results']]
                cache.append((current, reused))
            differences = [abs(x - r['total_electronic_energy_hartree'])
                           for x, r in zip(reused, expected['scf_results'])]
            cached_checks.append({'hit': hit, 'passed': all(d <= TOLERANCE for d in differences),
                                  'differences_hartree': differences})
        cached_seconds += time.perf_counter() - start
        cases.append({'molecule': name, 'input': graph, 'reference': reference, 'trials': trials,
                      'cached_validation': cached_checks})
    passed = (all(t['passed'] for c in cases for t in c['trials']) and
              all(t['passed'] for c in cases for t in c['cached_validation']) and
              cache_hits == 9 and cache_misses == 6)
    return {'schema_version': 1, 'experiment': 'molecular-symmetry-reuse-v2',
            'source_head_sha': os.environ.get('RESEARCH_HEAD_SHA'),
            'producer_run_id': os.environ.get('GITHUB_RUN_ID'),
            'tolerance_hartree': TOLERANCE, 'passed': passed, 'cases': cases,
            'scf_calculations_performed': 30 + 2 * cache_misses,
            'benchmark': {'uncached_scf_calls': 30, 'cached_scf_calls': 2 * cache_misses,
                          'cache_hits': cache_hits, 'cache_misses': cache_misses,
                          'uncached_seconds': uncached_seconds, 'cached_seconds': cached_seconds,
                          'observed_time_ratio': uncached_seconds / cached_seconds,
                          'timing_scope': 'One paired run, uncached first; warmup/order bias not controlled.'},
            'candidate_math': 'Quotient rigid motions and element-preserving atom permutations.',
            'candidate_followup': 'Prove operator covariance and validate a collision-safe equivalence key.',
            'novel_mathematics_claimed': False, 'speedup_measured': True,
            'cache_enabled': False, 'promotion_authority': False,
            'evidence_scope': 'Three fixed geometries, RHF and two finite bases; empirical invariance only.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    report = experiment()
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report[k] for k in ('experiment', 'passed', 'scf_calculations_performed', 'benchmark')}))
    if not report['passed']:
        raise SystemExit('Molecular symmetry hypothesis or deformation control failed')


if __name__ == '__main__':
    main()
