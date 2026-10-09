#!/usr/bin/env python3
"""Bounded exploratory molecular symmetry experiment; no cache promotion."""
import argparse
import copy
import json
import os
from pathlib import Path

from generate_molecular_matter import generate
from evaluate_molecular_quantum import baseline

TOLERANCE = 1e-7  # Hartree; prespecified numerical comparison, not a proof.


def variants(graph):
    result = {}
    for name in ('translation', 'quarter_turn', 'atom_reordering', 'bond_stretch'):
        g = copy.deepcopy(graph)
        for a in g['nodes']:
            x, y, z = map(float, a['position'])
            if name == 'translation':
                p = (x + 2, y - 3, z + 1)
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
    for name, smiles in [('water', 'O'), ('methane', 'C'), ('ammonia', 'N')]:
        graph = generate(smiles, name + '-symmetry', conformers=2, seed=1729)['matter_graph']
        reference = baseline(graph)
        trials = []
        for transformation, changed in variants(graph).items():
            observed = baseline(changed)
            differences = [abs(a['total_electronic_energy_hartree'] -
                               b['total_electronic_energy_hartree'])
                           for a, b in zip(reference['scf_results'], observed['scf_results'])]
            invariant = transformation != 'bond_stretch'
            passed = (all(d <= TOLERANCE for d in differences) if invariant
                      else all(d > TOLERANCE for d in differences))
            trials.append({'transformation': transformation, 'expected_invariant': invariant,
                           'absolute_energy_differences_hartree': differences,
                           'passed': passed, 'input': changed, 'quantum_result': observed})
        cases.append({'molecule': name, 'input': graph, 'reference': reference, 'trials': trials})
    passed = all(t['passed'] for c in cases for t in c['trials'])
    return {'schema_version': 1, 'experiment': 'molecular-symmetry-v1',
            'source_head_sha': os.environ.get('RESEARCH_HEAD_SHA'),
            'producer_run_id': os.environ.get('GITHUB_RUN_ID'),
            'tolerance_hartree': TOLERANCE, 'passed': passed, 'cases': cases,
            'scf_calculations_performed': 30,
            'candidate_math': 'Quotient rigid motions and element-preserving atom permutations.',
            'candidate_followup': 'Prove operator covariance and validate a collision-safe equivalence key.',
            'novel_mathematics_claimed': False, 'speedup_measured': False,
            'cache_enabled': False, 'promotion_authority': False,
            'evidence_scope': 'Three fixed geometries, RHF and two finite bases; empirical invariance only.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    report = experiment()
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report[k] for k in ('experiment', 'passed', 'scf_calculations_performed')}))
    if not report['passed']:
        raise SystemExit('Molecular symmetry hypothesis or deformation control failed')


if __name__ == '__main__':
    main()
