"""Exact decimal rigid witnesses for persistent atom IDs; experimental only.

Restricts rotations to the 24 proper signed coordinate permutations. No fuzzy
distance hash, arbitrary graph isomorphism, or general rotation qualification.
"""
from fractions import Fraction
from itertools import permutations, product


def signature(graph):
    nodes = graph['nodes']
    if not 2 <= len(nodes) <= 16:
        raise ValueError('bounded molecular graph required')
    ids = [a['id'] for a in nodes]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate atom IDs')
    ordered = sorted(nodes, key=lambda a: a['id'])
    chemistry = tuple((a['id'], a['element'], a.get('isotope'), a.get('formal_charge', 0))
                      for a in ordered)
    positions = []
    for a in ordered:
        if len(a['position']) != 3:
            raise ValueError('three coordinates required')
        p = []
        for x in a['position']:
            s = str(x)
            if len(s) > 64:
                raise ValueError('coordinate encoding too long')
            f = Fraction(s)
            if f.numerator.bit_length() > 512 or f.denominator.bit_length() > 512:
                raise ValueError('coordinate out of bounds')
            p.append(f)
        positions.append(tuple(p))
    bonds = []
    for e in graph['edges']:
        if e.get('relation') != 'bonded_to' or e['source'] not in ids or e['target'] not in ids:
            raise ValueError('unsupported edge')
        bonds.append((tuple(sorted((e['source'], e['target']))), e['bond_order']))
    return chemistry, tuple(sorted(bonds)), positions


def equivalent(left, right):
    try:
        ca, ba, a = signature(left)
        cb, bb, b = signature(right)
        if ca != cb or ba != bb:
            return False
        da = [tuple(p[k] - a[0][k] for k in range(3)) for p in a]
        db = [tuple(p[k] - b[0][k] for k in range(3)) for p in b]
        for perm in permutations(range(3)):
            parity = (-1) ** sum(perm[i] > perm[j] for i in range(3) for j in range(i+1, 3))
            for signs in product((-1, 1), repeat=3):
                if parity * signs[0] * signs[1] * signs[2] != 1:
                    continue
                if all(tuple(signs[k] * p[perm[k]] for k in range(3)) == q
                       for p, q in zip(da, db)):
                    return True
        return False
    except (KeyError, ValueError, TypeError, OverflowError):
        return False
