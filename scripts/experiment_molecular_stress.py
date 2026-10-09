#!/usr/bin/env python3
"""Falsify a frozen empirical RHF residual rule on new distorted geometries."""
import argparse
import copy
import hashlib
import json
import math
import os
import time
from pathlib import Path
from generate_molecular_matter import generate
from experiment_molecular_one_shot import predict
from experiment_molecular_approximation import TARGET

MOLECULES = [('ethane', 'CC'), ('acetylene', 'C#C'), ('ethanol', 'CCO')]
SCALES = (0.85, 1.25, 1.75)


def classify(error, prediction):
    if not math.isfinite(error) or error < 0:
        raise ValueError('finite nonnegative error required')
    if prediction is not None and (not math.isfinite(prediction) or prediction < 0):
        raise ValueError('finite nonnegative prediction required')
    accepted = prediction is not None and prediction <= TARGET
    return {'accepted': accepted, 'false_accept': accepted and error > TARGET,
            'underestimate': prediction is not None and prediction < error,
            'gap_rejected': prediction is None}


def distort(graph, scale):
    result = copy.deepcopy(graph)
    for atom in result['nodes']:
        atom['position'] = [scale * float(x) for x in atom['position']]
    result['verification']['geometry_validity'] = False
    result['description'] = 'Unrelaxed synthetic stress geometry; not qualified molecular structure'
    return result


def pair(graph, reverse):
    import numpy as np
    from pyscf import gto, scf, df
    atoms = [(a['element'], tuple(map(float, a['position']))) for a in graph['nodes']]
    observations = {}
    for method in (('corrected', 'full') if reverse else ('full', 'corrected')):
        start = time.perf_counter()
        mol = gto.M(atom=atoms, basis='6-31g', charge=0, spin=0,
                    unit='Angstrom', verbose=0, max_memory=384)
        solver = scf.RHF(mol)
        if method == 'corrected':
            solver = solver.density_fit(auxbasis=df.aug_etb(mol, beta=2.0))
        solver.conv_tol = 1e-10
        solver.max_cycle = 50
        raw = float(solver.kernel())
        if not solver.converged or not math.isfinite(raw):
            return {'status': 'unconverged', 'method': method}
        row = {'raw_energy_hartree': raw, 'energy_hartree': raw}
        if method == 'corrected':
            density = solver.make_rdm1()
            operator = scf.RHF(mol)
            h = operator.get_hcore()
            v = operator.get_veff(mol, density)
            energy = float(operator.energy_tot(dm=density, h1e=h, vhf=v))
            occupied, virtual = solver.mo_occ > 0, solver.mo_occ == 0
            block = solver.mo_coeff[:, virtual].T @ (h + v) @ solver.mo_coeff[:, occupied]
            residual = float(np.sum(block * block))
            gap = float(min(solver.mo_energy[virtual]) - max(solver.mo_energy[occupied]))
            if not all(math.isfinite(x) for x in (energy, residual, gap)):
                return {'status': 'nonfinite'}
            row.update({'energy_hartree': energy, 'residual_squared_hartree2': residual,
                        'gap_hartree': gap})
        row['seconds'] = time.perf_counter() - start
        observations[method] = row
    return {'status': 'converged', 'observations': observations}


def experiment(calibration, calibration_sha):
    if calibration.get('experiment') != 'molecular-one-shot-v1':
        raise ValueError('wrong calibration experiment')
    if calibration.get('source_head_sha') != os.environ.get('RESEARCH_HEAD_SHA'):
        raise ValueError('calibration source mismatch')
    factor = float(calibration['calibration_factor'])
    predict(0, 1, factor)  # validate once, freeze before all new evaluations
    cases = []
    for name, smiles in MOLECULES:
        base = generate(smiles, name + '-stress', conformers=2, seed=1729)['matter_graph']
        for scale in SCALES:
            graph = distort(base, scale)
            result = pair(graph, reverse=len(cases) % 2 == 1)
            result.update({'molecule': name, 'scale': scale, 'input': graph})
            if result['status'] == 'converged':
                full, corrected = result['observations']['full'], result['observations']['corrected']
                error = abs(corrected['energy_hartree'] - full['energy_hartree'])
                prediction = predict(corrected['residual_squared_hartree2'], corrected['gap_hartree'], factor)
                result.update(classify(error, prediction))
                result.update({'error_hartree': error, 'predicted_error_hartree': prediction,
                               'raw_error_hartree': abs(corrected['raw_energy_hartree'] - full['energy_hartree']),
                               'signed_defect_hartree': corrected['energy_hartree'] - full['energy_hartree']})
            cases.append(result)
    converged = [c for c in cases if c['status'] == 'converged']
    return {'schema_version': 1, 'experiment': 'molecular-residual-stress-v1',
            'source_head_sha': os.environ.get('RESEARCH_HEAD_SHA'),
            'producer_run_id': os.environ.get('GITHUB_RUN_ID'),
            'calibration_report_sha256': calibration_sha, 'frozen_factor': factor,
            'target_error_hartree': TARGET, 'cases': cases,
            'cases_converged': len(converged), 'cases_unqualified': len(cases) - len(converged),
            'accepted': sum(c['accepted'] for c in converged),
            'false_accepts': sum(c['false_accept'] for c in converged),
            'underestimates': sum(c['underestimate'] for c in converged),
            'negative_defects_beyond_roundoff': sum(c['signed_defect_hartree'] < -1e-8 for c in converged),
            'maximum_scf_calculations': 18, 'rigorous_error_bound': False,
            'statistically_blind': False, 'production_policy_enabled': False,
            'promotion_authority': False,
            'scope': 'Synthetic geometry stress; finite-basis closed-shell RHF only. Same SCF branch not certified.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    with args.calibration.open('rb') as source:
        snapshot = source.read(4 * 1024 * 1024 + 1)
    if len(snapshot) > 4 * 1024 * 1024:
        raise ValueError('calibration snapshot too large')
    report = experiment(json.loads(snapshot), hashlib.sha256(snapshot).hexdigest())
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    keys = ('experiment', 'cases_converged', 'cases_unqualified', 'accepted', 'false_accepts',
            'underestimates', 'negative_defects_beyond_roundoff')
    print(json.dumps({k: report[k] for k in keys}))
    for case in report['cases']:
        print(json.dumps({k: v for k, v in case.items() if k not in ('input', 'observations')}))


if __name__ == '__main__':
    main()
