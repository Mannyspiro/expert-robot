"""Exact equivalence accepts rigid witnesses and rejects changed chemistry."""
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from molecular_symmetry_equivalence import equivalent

g = {'nodes': [{'id': 'a', 'element': 'O', 'formal_charge': 0, 'isotope': None,
               'position': ['0.1', '0', '0']},
              {'id': 'b', 'element': 'H', 'formal_charge': 0, 'isotope': None,
               'position': ['1.1', '0', '0']}],
     'edges': [{'source': 'a', 'target': 'b', 'relation': 'bonded_to', 'bond_order': 1}]}
h = copy.deepcopy(g)
h['nodes'][0]['position'] = ['2', '3.1', '4']
h['nodes'][1]['position'] = ['2', '4.1', '4']
h['nodes'].reverse()
assert equivalent(g, h)
for target, key, value in [('nodes', 'element', 'C'), ('nodes', 'isotope', 18),
                           ('nodes', 'formal_charge', 1), ('edges', 'bond_order', 2)]:
    changed = copy.deepcopy(g)
    changed[target][0][key] = value
    assert not equivalent(g, changed)
changed = copy.deepcopy(g)
changed['nodes'][1]['position'][0] = '1.100000000000001'
assert not equivalent(g, changed)
changed['nodes'][1]['id'] = 'a'
assert not equivalent(g, changed)
print('Exact symmetry witnesses and chemistry/deformation rejection: PASS')
