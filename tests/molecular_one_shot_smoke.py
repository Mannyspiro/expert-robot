import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from experiment_molecular_one_shot import predict

assert predict(1e-6, .5, 2) == 4e-6
assert predict(1e-6, 0, 2) is None
assert predict(1e-6, -1, 2) is None
for args in [(float('nan'), .5, 2), (-1, .5, 2), (1, .5, .5)]:
    try:
        predict(*args)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid diagnostic accepted')
print('Residual diagnostic finite checks and small-gap rejection: PASS')
