"""Synthetic counterexamples must expose unsafe empirical decisions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from experiment_molecular_approximation import fit_factor, evaluate_rule

factor = fit_factor([{'fine_error_hartree': 2e-5, 'diagnostic_hartree': 1e-5}])
assert abs(factor - 3) < 1e-12
rows = [{'molecule': 'safe', 'fine_error_hartree': 1e-5, 'diagnostic_hartree': 1e-5},
        {'molecule': 'reject', 'fine_error_hartree': 1e-3, 'diagnostic_hartree': 1e-3},
        {'molecule': 'counterexample', 'fine_error_hartree': 1e-3, 'diagnostic_hartree': 0}]
a, b, c = evaluate_rule(rows, factor)
assert a['accept_approximation'] and not a['false_accept']
assert not b['accept_approximation'] and not b['false_accept']
assert c['false_accept'] and c['prediction_underestimated_error']
print('Diagnostic calibration, escalation and false-accept detection: PASS')
