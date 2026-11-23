import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from experiment_molecular_stress import classify, distort

assert classify(1e-3, 1e-6)['false_accept']
assert classify(1e-3, 1e-6)['underestimate']
assert classify(1e-6, None)['gap_rejected']
assert not classify(1e-6, None)['accepted']
for error, prediction in [(float('nan'), 1), (1, float('nan')), (-1, 1)]:
    try:
        classify(error, prediction)
    except ValueError:
        pass
    else:
        raise AssertionError('malformed observation accepted')
g = {'nodes': [{'position': [1, 0, 0]}], 'verification': {'geometry_validity': True}}
d = distort(g, 1.25)
assert d['nodes'][0]['position'][0] == 1.25
assert not d['verification']['geometry_validity']
assert g['verification']['geometry_validity'] and g['nodes'][0]['position'][0] == 1
print('Stress classification and geometry evidence downgrade: PASS')
