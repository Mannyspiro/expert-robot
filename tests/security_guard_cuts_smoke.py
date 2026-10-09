import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from experiment_security_guard_cuts import optimum, greedy, verify, experiment

edges = [(0,1),(0,2),(1,3),(2,3),(3,4)]
assert optimum(edges) == (3,)
assert greedy(edges) == (1,2)
assert verify(edges, (3,), 1)
assert not verify(edges, (1,), 1)  # bypass route remains
assert not verify(edges, (1,2), 6)  # valid cut, but not minimum cost
assert not verify(edges, (3,3), 2)
assert not verify(edges, (3,), 0)
assert not verify([(0,1),(1,0)], (1,), 1)
assert not verify(edges, (3,), True)
assert not verify(edges + [(0,1)], (3,), 1)
assert verify([], (), 0)
r = experiment()
assert r['graphs_checked'] == r['witnesses_verified'] == 512
assert r['graphs_where_greedy_costs_more'] > 0
print('Offline complete DAG family and independent cut-witness tamper checks: PASS')
