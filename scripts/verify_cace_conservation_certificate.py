#!/usr/bin/env python3
"""Independent SymPy verifier for finite, exact CACE conservation receipts.

Checks the rank, completeness, basis independence, graph component span,
source/certificate digests and fail-closed qualification flags. A hash is
integrity/provenance evidence, not a cryptographic signature.
"""
import argparse, hashlib, json
from fractions import Fraction as Q
from pathlib import Path
from sympy import Matrix, Rational

KEYS={'schema','source_sha256','species','reactions','stoichiometry',
      'method','rank','left_nullspace_basis','candidate_conservation_laws',
      'scope','lean_kernel_checked','cace_runtime_checked',
      'biological_mechanism_validated','authority_expanded','certificate_sha256'}

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()

def parse(s):
    if not isinstance(s,str) or not s or len(s)>160 or any(c not in '0123456789-/' for c in s) or s.count('/')>1:
        raise ValueError('malformed rational')
    q=Q(s)
    if max(q.numerator.bit_length(),q.denominator.bit_length())>256 or str(q)!=s:
        raise ValueError('noncanonical rational or oversized value')
    return Rational(q.numerator,q.denominator)

def verify(c):
    if not isinstance(c,dict) or set(c)!=KEYS or c['schema']!='cace-conservation-exact-v2':
        raise ValueError('unknown certificate schema')
    if c['scope']!='exact rational stoichiometric linear invariants only' or any(c[k] is not False for k in
           ('lean_kernel_checked','cace_runtime_checked','biological_mechanism_validated','authority_expanded')):
        raise ValueError('fabricated qualification')
    species,reactions=c['species'],c['reactions']
    for names,limit in ((species,64),(reactions,128)):
        if not isinstance(names,list) or not 1<=len(names)<=limit or len(set(names))!=len(names) or not all(
            isinstance(x,str) and x.isascii() and 1<=len(x)<=80 for x in names):
            raise ValueError('invalid species or reactions')
    raw=c['stoichiometry']
    if not isinstance(raw,list) or len(raw)!=len(species) or any(not isinstance(row,list) or len(row)!=len(reactions) for row in raw):
        raise ValueError('invalid matrix dimensions')
    A=Matrix([[parse(x) for x in row] for row in raw])
    spec={'species':species,'reactions':reactions,'stoichiometry':raw}
    if hashlib.sha256(canonical(spec)).hexdigest()!=c['source_sha256']:
        raise ValueError('source digest mismatch')
    body={k:v for k,v in c.items() if k!='certificate_sha256'}
    if hashlib.sha256(canonical(body)).hexdigest()!=c['certificate_sha256']:
        raise ValueError('certificate digest mismatch')
    rank=A.rank()
    rows=c['left_nullspace_basis']
    if not isinstance(rows,list) or len(rows)>len(species) or any(not isinstance(row,list) or len(row)!=len(species) for row in rows):
        raise ValueError('basis dimension')
    B=Matrix([[parse(x) for x in row] for row in rows]) if rows else Matrix.zeros(0,len(species))
    if type(c['rank']) is not int or type(c['candidate_conservation_laws']) is not int or c['rank']!=rank or len(rows)!=len(species)-rank or c['candidate_conservation_laws']!=len(rows):
        raise ValueError('rank/nullity claim invalid')
    if B.rank()!=len(rows) or B*A!=Matrix.zeros(len(rows),len(reactions)):
        raise ValueError('incorrect, incomplete, or dependent basis')
    edges=[]
    for j in range(A.cols):
        nz=[(i,A[i,j]) for i in range(A.rows) if A[i,j]!=0]
        if len(nz)!=2 or sorted(v for _,v in nz)!=[-1,1]:
            edges=None;break
        edges.append((next(i for i,x in nz if x==-1),next(i for i,x in nz if x==1)))
    method='component_graph' if edges is not None else 'rational_rref'
    if c['method']!=method:
        raise ValueError('incorrect optimization method')
    if edges is not None:
        # Independent graph algorithm: BFS instead of producer's union-find.
        adj=[set() for _ in species]
        for a,b in edges:adj[a].add(b);adj[b].add(a)
        seen=set();groups=[]
        for i in range(len(species)):
            if i in seen:continue
            todo=[i];group=set()
            while todo:
                v=todo.pop()
                if v in group:continue
                group.add(v);todo.extend(adj[v]-group)
            seen.update(group);groups.append(group)
        if len(groups)!=len(rows):
            raise ValueError('number of component invariants wrong')
        indicators=Matrix([[int(i in group) for i in range(len(species))] for group in groups])
        if indicators.rank()!=len(groups) or indicators*A!=Matrix.zeros(len(groups),len(reactions)):
            raise ValueError('invalid component indicators')
        if B.col_join(indicators).rank()!=len(groups):
            raise ValueError('certificate basis not component-indicator span')
    return {'valid':True,'rank':rank,'conservation_laws':len(rows),
            'method':method,'certificate_sha256':c['certificate_sha256'],
            'formal_kernel_verification':False,'cace_runtime_executed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('certificate',type=Path)
    args=p.parse_args()
    print(json.dumps(verify(json.loads(args.certificate.read_text(encoding='utf-8')))))
