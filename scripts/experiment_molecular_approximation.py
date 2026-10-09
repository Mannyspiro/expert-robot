#!/usr/bin/env python3
"""Prespecified density-fitting diagnostic experiment, not an error certificate.

Six neutral closed-shell molecules; 6-31g; 36 converged SCF calculations.
Three calibration cases and three disjoint evaluation cases. No production use.
"""
import argparse
import hashlib
import json
import math
import os
import statistics
import time
from pathlib import Path

from generate_molecular_matter import generate

CASES = [('water', 'O'), ('methane', 'C'), ('ammonia', 'N'),
         ('methanol', 'CO'), ('formaldehyde', 'C=O'), ('peroxide', 'OO')]
TARGET = 1e-4  # Hartree error relative to full RHF at the SAME finite basis.
FLOOR = 1e-12


def fit_factor(rows):
    return max(1.0, 1.5 * max(r['fine_error_hartree'] /
                            max(r['diagnostic_hartree'], FLOOR) for r in rows))


def evaluate_rule(rows, factor):
    decisions = []
    for r in rows:
        prediction = factor * max(r['diagnostic_hartree'], FLOOR)
        accept = prediction <= TARGET
        decisions.append({'molecule': r['molecule'], 'predicted_error_hartree': prediction,
                          'accept_approximation': accept,
                          'actual_error_hartree': r['fine_error_hartree'],
                          'false_accept': accept and r['fine_error_hartree'] > TARGET,
                          'prediction_underestimated_error': prediction < r['fine_error_hartree']})
    return decisions


def experiment():
    from pyscf import gto, scf, df, __version__
    rows = []
    for index, (name, smiles) in enumerate(CASES):
        graph = generate(smiles, name + '-df-experiment', conformers=2, seed=1729)['matter_graph']
        atoms = [(a['element'], tuple(map(float, a['position']))) for a in graph['nodes']]
        samples = {m: [] for m in ('full', 'fine', 'coarse')}
        # Reverse order on the second pass; no reuse of SCF states or DF tensors.
        for order in [('full', 'fine', 'coarse'), ('coarse', 'fine', 'full')]:
            for method in order:
                start = time.perf_counter()
                mol = gto.M(atom=atoms, basis='6-31g', charge=0, spin=0,
                            unit='Angstrom', verbose=0, max_memory=384)
                solver = scf.RHF(mol)
                if method != 'full':
                    solver = solver.density_fit(auxbasis=df.aug_etb(
                        mol, beta=2.0 if method == 'fine' else 4.0))
                solver.conv_tol = 1e-10
                solver.max_cycle = 50
                energy = float(solver.kernel())
                elapsed = time.perf_counter() - start
                if not solver.converged or not math.isfinite(energy):
                    raise ValueError(name + '/' + method + ': SCF did not converge')
                samples[method].append({'energy_hartree': energy, 'seconds': elapsed,
                                        'basis_functions': int(mol.nao_nr()),
                                        'auxiliary_functions': (int(solver.with_df.auxmol.nao_nr())
                                                                if method != 'full' else None)})
        energies = {m: statistics.mean(s['energy_hartree'] for s in values)
                    for m, values in samples.items()}
        if any(abs(v[0]['energy_hartree'] - v[1]['energy_hartree']) > 1e-7
               for v in samples.values()):
            raise ValueError('repeat energy inconsistency')
        rows.append({'molecule': name, 'split': 'calibration' if index < 3 else 'evaluation',
                     'input': graph, 'input_sha256': hashlib.sha256(json.dumps(
                         graph, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                     'samples': samples, 'fine_error_hartree': abs(energies['fine'] - energies['full']),
                     'diagnostic_hartree': abs(energies['fine'] - energies['coarse'])})
    factor = fit_factor(rows[:3])
    decisions = evaluate_rule(rows[3:], factor)
    full_time = sum(statistics.mean(s['seconds'] for s in r['samples']['full']) for r in rows[3:])
    adaptive_time = 0.0
    for r, decision in zip(rows[3:], decisions):
        adaptive_time += sum(statistics.mean(s['seconds'] for s in r['samples'][m])
                             for m in ('fine', 'coarse'))
        if not decision['accept_approximation']:
            adaptive_time += statistics.mean(s['seconds'] for s in r['samples']['full'])
    return {'schema_version': 1, 'experiment': 'molecular-df-diagnostic-v1',
            'source_head_sha': os.environ.get('RESEARCH_HEAD_SHA'),
            'producer_run_id': os.environ.get('GITHUB_RUN_ID'), 'pyscf_version': __version__,
            'basis': '6-31g', 'scf_calculations': 36, 'rows': rows,
            'target_error_hartree': TARGET, 'calibration_factor': factor,
            'evaluation_decisions': decisions,
            'false_accepts': sum(d['false_accept'] for d in decisions),
            'underestimates': sum(d['prediction_underestimated_error'] for d in decisions),
            'evaluation_full_seconds': full_time, 'evaluation_policy_seconds': adaptive_time,
            'observed_policy_speed_ratio': full_time / adaptive_time,
            'cost_scope': 'Measured component times, two reversed passes; excludes calibration amortization.',
            'statistically_blind': False, 'rigorous_error_bound': False,
            'production_policy_enabled': False, 'promotion_authority': False,
            'scope': 'Approximation error against finite-basis RHF, not physical accuracy or thermochemistry.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    report = experiment()
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report[k] for k in ('experiment', 'scf_calculations', 'false_accepts',
                                           'underestimates', 'observed_policy_speed_ratio',
                                           'evaluation_decisions')}))


if __name__ == '__main__':
    main()
