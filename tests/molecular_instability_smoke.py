import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from experiment_molecular_instability import branch_gate

assert branch_gate(True, True, True)
for args in [(True, True, False), (True, False, True), (False, True, True),
             (True, None, True), (True, True, None), (True, 'true', True)]:
    assert not branch_gate(*args)
print('Missing and unstable branch evidence rejects acceptance: PASS')
