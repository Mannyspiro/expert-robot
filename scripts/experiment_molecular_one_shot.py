#!/usr/bin/env python3
"""Full-operator energy at a DF density: exploratory correction, no certificate.

Uses previously examined geometries. Evaluation is disjoint from calibration
within this experiment, but is not fresh or blind validation.
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
from experiment_molecular_approximation import CASES, TARGET, FLOOR


def predict(residual_squared, gap, factor):
    if not all(math.isfinite(x) for x in (residual_squared, gap, factor)):
        raise ValueError('finite diagnostic required')
    if residual_squared < 0 or factor < 1:
        raise ValueError('invalid diagnostic')
    if gap <= 1e-6:
        return None  # fail closed on a small or negative orbital gap
    return factor * max(residual_squared / gap, FLOOR)


def experiment():
    import numpy as np
    from pyscf import gto, scf, df, __version__
    rows = []
    for index, (name, smiles) in enumerate(CASES):
        graph = generate(smiles, name + '-one-shot', conformers=2, seed=1729)['matter_graph']
        atoms = [(a['element'], tuple(map(float, a['position']))) for a in graph['nodes']]
        samples = {'full': [], 'corrected': []}
        for order in [('full', 'corrected'), ('corrected', 'full')]:
            for method in order:
                start = time.perf_counter()
                mol = gto.M(atom=atoms, basis='6-31g', charge=0, spin=0,
                            unit='Angstrom', verbose=0, max_memory=384)
                solver = scf.RHF(mol)
                if method == 'corrected':
                    solver = solver.density_fit(auxbasis=df.aug_etb(mol, beta=2.0))
                solver.conv_tol = 1e-10
                solver.max_cycle = 50
                raw_energy = float(solver.kernel())
                if not solver.converged or not math.isfinite(raw_energy):
                    raise ValueError(name + '/' + method + ': unconverged')
                entry = {'raw_energy_hartree': raw_energy}
                energy = raw_energy
                if method == 'corrected':
                    density = solver.make_rdm1()
                    exact_operator = scf.RHF(mol)
                    hcore = exact_operator.get_hcore()
                    potential = exact_operator.get_veff(mol, density)
                    energy = float(exact_operator.energy_tot(dm=density, h1e=hcore, vhf=potential))
                    occupied = solver.mo_occ > 0
                    virtual = solver.mo_occ == 0
                    coefficients = solver.mo_coeff
                    block = coefficients[:, virtual].T @ (hcore + potential) @ coefficients[:, occupied]
                    residual_squared = float(np.sum(block * block))
                    gap = float(min(solver.mo_energy[virtual]) - max(solver.mo_energy[occupied]))
                    if not all(math.isfinite(x) for x in (energy, residual_squared, gap)):
                        raise ValueError('nonfinite one-shot diagnostic')
                    entry.update({'residual_squared_hartree2': residual_squared,
                                  'df_orbital_gap_hartree': gap})
                entry.update({'energy_hartree': energy, 'seconds': time.perf_counter() - start})
                samples[method].append(entry)
        if any(abs(s[0]['energy_hartree'] - s[1]['energy_hartree']) > 1e-7
               for s in samples.values()):
            raise ValueError('repeat energy inconsistency')
        full = statistics.mean(s['energy_hartree'] for s in samples['full'])
        corrected = statistics.mean(s['energy_hartree'] for s in samples['corrected'])
        raw = statistics.mean(s['raw_energy_hartree'] for s in samples['corrected'])
        residual = statistics.mean(s['residual_squared_hartree2'] for s in samples['corrected'])
        gap = statistics.mean(s['df_orbital_gap_hartree'] for s in samples['corrected'])
        rows.append({'molecule': name, 'split': 'calibration' if index < 3 else 'evaluation',
                     'input': graph, 'input_sha256': hashlib.sha256(json.dumps(
                         graph, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                     'samples': samples, 'raw_error_hartree': abs(raw - full),
                     'corrected_error_hartree': abs(corrected - full),
                     'signed_correction_defect_hartree': corrected - full,
                     'residual_squared_hartree2': residual, 'df_orbital_gap_hartree': gap})
    ratios = []
    for row in rows[:3]:
        proxy = predict(row['residual_squared_hartree2'], row['df_orbital_gap_hartree'], 1.0)
        if proxy is None:
            raise ValueError('calibration gap not qualified')
        ratios.append(row['corrected_error_hartree'] / proxy)
    factor = max(1.0, 1.5 * max(ratios))
    decisions = []
    full_seconds = 0.0
    policy_seconds = 0.0
    for row in rows[3:]:
        prediction = predict(row['residual_squared_hartree2'], row['df_orbital_gap_hartree'], factor)
        accepted = prediction is not None and prediction <= TARGET
        reference_time = statistics.mean(s['seconds'] for s in row['samples']['full'])
        full_seconds += reference_time
        policy_seconds += statistics.mean(s['seconds'] for s in row['samples']['corrected'])
        if not accepted:
            policy_seconds += reference_time
        decisions.append({'molecule': row['molecule'], 'predicted_error_hartree': prediction,
                          'actual_error_hartree': row['corrected_error_hartree'],
                          'raw_error_hartree': row['raw_error_hartree'],
                          'accepted': accepted,
                          'false_accept': accepted and row['corrected_error_hartree'] > TARGET,
                          'underestimate': prediction is not None and prediction < row['corrected_error_hartree']})
    return {'experiment': 'molecular-one-shot-v1', 'schema_version': 1,
            'source_head_sha': os.environ.get('RESEARCH_HEAD_SHA'),
            'producer_run_id': os.environ.get('GITHUB_RUN_ID'), 'pyscf_version': __version__,
            'scf_calculations': 24, 'full_operator_corrections': 12,
            'basis': '6-31g', 'target_error_hartree': TARGET,
            'rows': rows, 'calibration_factor': factor, 'decisions': decisions,
            'accepted': sum(d['accepted'] for d in decisions),
            'false_accepts': sum(d['false_accept'] for d in decisions),
            'underestimates': sum(d['underestimate'] for d in decisions),
            'full_seconds': full_seconds, 'policy_seconds': policy_seconds,
            'observed_policy_speed_ratio': full_seconds / policy_seconds,
            'timing_scope': 'Two reversed passes; sum of component times; excludes calibration amortization.',
            'theorem_candidate': 'Energy defect controlled by squared orbital residual under certified Hessian coercivity.',
            'hessian_coercivity_certified': False, 'rigorous_error_bound': False,
            'statistically_blind': False, 'fresh_evaluation_geometries': False,
            'production_policy_enabled': False, 'promotion_authority': False,
            'scope': 'Finite-basis RHF approximation only; no physical accuracy or synthesis claim.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    report = experiment()
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report[k] for k in ('experiment', 'scf_calculations', 'accepted',
                                           'false_accepts', 'underestimates',
                                           'observed_policy_speed_ratio', 'decisions')}))


if __name__ == '__main__':
    main()
