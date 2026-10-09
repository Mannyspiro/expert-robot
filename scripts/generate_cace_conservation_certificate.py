#!/usr/bin/env python3
"""Produce exact-rational stoichiometric certificates. Research-only; no Lean check."""
import argparse, hashlib, json
from fractions import Fraction as Q
from pathlib import Path

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()

def parse(x):
    if not isinstance(x,str) or not x or len(x)>160 or any(c not in '0123456789-/' for c in x) or x.count('/')>1:
        raise ValueError('bounded exact rational expected')
    q=Q(x)
    if max(q.numerator.bit_length(),q.denominator.bit_length())>256:
        raise ValueError('excessive rational size')
    return q

def normalize(spec):
    if not isinstance(spec,dict) or set(spec)!={'species','reactions','stoichiometry'}:
        raise ValueError('unsupported source schema')
    sp,rx=spec['species'],spec['reactions']
    for names,limit in ((sp,64),(rx,128)):
        if not isinstance(names,list) or not 1<=len(names)<=limit or len(set(names))!=len(names) or not all(isinstance(x,str) and x.isascii() and 1<=len(x)<=80 for x in names):
            raise ValueError('invalid species/reaction ids')
    raw=spec['stoichiometry']
    if not isinstance(raw,list) or len(raw)!=len(sp) or any(not isinstance(row,list) or len(row)!=len(rx) for row in raw):
        raise ValueError('invalid stoichiometric shape')
    a=[[parse(x) for x in row] for row in raw]
    return {'species':sp,'reactions':rx,'stoichiometry':[[str(x) for x in row] for row in a]},a

def component_basis(a):
    m,n=len(a),len(a[0]);edges=[]
    for j in range(n):
        nz=[(i,a[i][j]) for i in range(m) if a[i][j]!=0]
        if len(nz)!=2 or sorted(v for _,v in nz)!=[Q(-1),Q(1)]:
            return None
        edges.append((next(i for i,x in nz if x==-1),next(i for i,x in nz if x==1)))
    parent=list(range(m))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,j in edges:
        parent[root(i)]=root(j)
    groups=sorted(set(root(i) for i in range(m)))
    return [[Q(int(root(i)==g)) for i in range(m)] for g in groups]

def rref_basis(a):
    m,n=len(a),len(a[0])
    t=[[a[i][j] for i in range(m)] for j in range(n)]
    rank=0;pivots=[]
    for j in range(m):
        k=next((k for k in range(rank,n) if t[k][j]),None)
        if k is None:continue
        t[rank],t[k]=t[k],t[rank]
        d=t[rank][j];t[rank]=[v/d for v in t[rank]]
        for i in range(n):
            if i==rank:continue
            f=t[i][j];t[i]=[v-f*w for v,w in zip(t[i],t[rank])]
        pivots.append(j);rank+=1
        if rank==n:break
    rows=[]
    for j in range(m):
        if j in pivots:continue
        v=[Q(0)]*m;v[j]=1
        for i,p in enumerate(pivots):v[p]=-t[i][j]
        rows.append(v)
    return rows

def generate(spec):
    normalized,a=normalize(spec)
    components=component_basis(a)
    basis=components if components is not None else rref_basis(a)
    m,n=len(a),len(a[0]);rank=m-len(basis)
    assert all(sum((v[i]*a[i][j] for i in range(m)),Q(0))==0 for v in basis for j in range(n))
    body={'schema':'cace-conservation-exact-v2',
          'source_sha256':hashlib.sha256(canonical(normalized)).hexdigest(),**normalized,
          'method':'component_graph' if components is not None else 'rational_rref',
          'rank':rank,'left_nullspace_basis':[[str(x) for x in row] for row in basis],
          'candidate_conservation_laws':len(basis),
          'scope':'exact rational stoichiometric linear invariants only',
          'lean_kernel_checked':False,'cace_runtime_checked':False,
          'biological_mechanism_validated':False,'authority_expanded':False}
    body['certificate_sha256']=hashlib.sha256(canonical(body)).hexdigest()
    return body

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('-o','--output',type=Path,required=True)
    args=p.parse_args()
    receipt=generate(json.loads(args.input.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'rank':receipt['rank'],'conservation_laws':receipt['candidate_conservation_laws'],'method':receipt['method'],'lean_checked':False}))
