#!/usr/bin/env python3
"""Numerical branch-instability counterexamples to residual-only acceptance."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from experiment_molecular_stress import pair, classify
from experiment_molecular_one_shot import predict

CASES = [('H2', 'H', r) for r in (0.74, 1.5, 3.0, 5.0)] + [
    ('N2', 'N', r) for r in (1.1, 2.0, 3.0, 4.0)]


def branch_gate(accepted, internal, spin_stable):
    return accepted is True and internal is True and spin_stable is True


def experiment(calibration, digest):
    import numpy as np
    from pyscf import gto, scf, __version__
    if calibration.get('experiment') != 'molecular-one-shot-v1':
        raise ValueError('wrong calibration')
    if calibration.get('source_head_sha') != os.environ.get('RESEARCH_HEAD_SHA'):
        raise ValueError('calibration source mismatch')
    factor = float(calibration['calibration_factor'])
    predict(0, 1, factor)
    cases = []
    for label, element, distance in CASES:
        graph = {'nodes': [{'id': 'a0', 'element': element, 'position': [0, 0, 0]},
                           {'id': 'a1', 'element': element, 'position': [0, 0, distance]}],
                 'description': 'Prespecified diatomic electronic stress geometry; angstrom units',
                 'verification': {'chemistry_validity': False, 'geometry_validity': False}}
        result = pair(graph, reverse=len(cases) % 2 == 1)
        result.update({'molecule': label, 'distance_angstrom': distance, 'input': graph})
        if result['status'] != 'converged':
            cases.append(result)
            continue
        full, corrected = result['observations']['full'], result['observations']['corrected']
        error = abs(corrected['energy_hartree'] - full['energy_hartree'])
        prediction = predict(corrected['residual_squared_hartree2'], corrected['gap_hartree'], factor)
        result.update(classify(error, prediction))
        result.update({'error_hartree': error, 'predicted_error_hartree': prediction,
                       'df_gap_hartree': corrected['gap_hartree'],
                       'residual_squared_hartree2': corrected['residual_squared_hartree2']})
        mol = gto.M(atom=[(a['element'], a['position']) for a in graph['nodes']],
                    basis='6-31g', charge=0, spin=0, unit='Angstrom', verbose=0, max_memory=384)
        solver = scf.RHF(mol)
        solver.conv_tol, solver.max_cycle = 1e-10, 50
        energy = float(solver.kernel())
        if not solver.converged or abs(energy - full['energy_hartree']) > 1e-7:
            result['status'] = 'reference_replay_unqualified'
            cases.append(result)
            continue
        _, external_orbitals, internal, spin_stable = solver.stability(
            internal=True, external=True, return_status=True, nroots=1, tol=1e-7)
        if not all(isinstance(x, (bool, np.bool_)) for x in (internal, spin_stable)):
            raise ValueError('stability API did not return qualified statuses')
        internal, spin_stable = bool(internal), bool(spin_stable)
        result.update({'internal_stable_numerically': internal,
                       'rhf_to_uhf_stable_numerically': spin_stable,
                       'residual_accepts_unstable_reference': result['accepted'] and not (internal and spin_stable),
                       'stability_aware_accept': branch_gate(result['accepted'], internal, spin_stable)})
        if not spin_stable:
            occupied = solver.mo_occ > 0
            density = np.array([c[:, occupied] @ c[:, occupied].T for c in external_orbitals])
            unrestricted = scf.UHF(mol)
            unrestricted.conv_tol, unrestricted.max_cycle = 1e-10, 50
            lower = float(unrestricted.kernel(dm0=density))
            qualified = unrestricted.converged and math.isfinite(lower)
            result['uhf_converged'] = bool(qualified)
            if qualified:
                result.update({'uhf_energy_hartree': lower,
                               'rhf_minus_uhf_hartree': energy - lower,
                               'uhf_spin_square': float(unrestricted.spin_square()[0])})
        cases.append(result)
    valid = [c for c in cases if c['status'] == 'converged']
    return {'schema_version': 1, 'experiment': 'molecular-instability-v1',
            'source_head_sha': os.environ.get('RESEARCH_HEAD_SHA'),
            'producer_run_id': os.environ.get('GITHUB_RUN_ID'), 'pyscf_version': __version__,
            'calibration_sha256': digest, 'frozen_factor': factor, 'cases': cases,
            'cases_qualified_numerically': len(valid), 'cases_unqualified': len(cases) - len(valid),
            'residual_accepts_unstable_references': sum(c['residual_accepts_unstable_reference'] for c in valid),
            'lower_uhf_branches_found': sum(c.get('rhf_minus_uhf_hartree', 0) > 1e-6 for c in valid),
            'false_accepts_against_same_rhf_reference': sum(c['false_accept'] for c in valid),
            'maximum_scf_calculations': 32, 'rigorous_error_bound': False,
            'stability_certified': False, 'production_policy_enabled': False,
            'promotion_authority': False,
            'scope': 'Numerical RHF internal and RHF-to-UHF stability; not exact ground-state accuracy. UHF may be spin contaminated.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    with args.calibration.open('rb') as source:
        data = source.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError('calibration snapshot too large')
    report = experiment(json.loads(data), hashlib.sha256(data).hexdigest())
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}))
    for case in report['cases']:
        print(json.dumps({k: v for k, v in case.items() if k not in ('input', 'observations')}))


if __name__ == '__main__':
    main()
