"""Voxel thermal coupon, two-channel synthetic scans, print and verification."""
from collections import Counter
from itertools import product
import json
from pathlib import Path

import numpy as np

SHAPE=(16,16,10)
MATERIAL_BUDGET=48
# Three levels of a virtual material map; conductivities are dimensionless.
K=np.array([0.024,0.05,0.22])
SIGNATURE=np.array([[0.1,0.2],[0.41,0.35],[0.41,0.85]])
LAYOUTS=("spread","vertical","cross","islands")
WORLDS={"uniform":((1.,1.,1.),.12), "layered":((1.25,.8,.58),.12),
        "sink":((.85,.85,1.12),.19), "skew_holdout":((.72,1.19,.61),.07)}


def layout(name):
    specimen=np.zeros(SHAPE,np.int8)
    specimen[3:13,3:13,:7]=1
    coords=list(product(range(3,13),range(3,13),range(2,7)))
    keys={
        "spread":lambda p:(-p[2],abs(p[0]-7)+abs(p[1]-7),p),
        "vertical":lambda p:((p[0]-7.5)**2+(p[1]-7.5)**2,-p[2],p),
        "cross":lambda p:(min(abs(p[0]-7),abs(p[1]-7)),abs(p[0]-7)+abs(p[1]-7)+abs(p[2]-5),p),
        "islands":lambda p:(min((p[0]-a)**2+(p[1]-b)**2 for a,b in ((5,5),(10,5),(5,10),(10,10))),-p[2],p)
    }
    if name!="plain":
        xyz=sorted(coords,key=keys[name])[:MATERIAL_BUDGET]
        for p in xyz:
            specimen[p]=2
    return specimen


def thermal(specimen,world,offset):
    scale,sink=WORLDS[world]
    k=K[specimen]
    temperature=np.zeros(SHAPE)
    temperature[7+offset:9+offset,7:9,1:3]=1
    mass=float(temperature.sum())
    faces=[]
    for axis in range(3):
        left=[slice(None)]*3;right=left.copy()
        left[axis]=slice(None,-1);right[axis]=slice(1,None)
        a,b=tuple(left),tuple(right)
        faces.append((a,b,scale[axis]*(2*k[a]*k[b]/(k[a]+k[b]))*.56))
    loss=0.
    exposed=np.max(np.where(specimen>0,np.indices(SHAPE)[2],0),axis=2)
    i,j=np.indices(SHAPE[:2])
    for step in range(64):
        delta=np.zeros_like(temperature)
        for a,b,weight in faces:
            flux=weight*(temperature[b]-temperature[a])
            delta[a]+=flux;delta[b]-=flux
        removed=temperature[i,j,exposed]*sink*(specimen[i,j,exposed]!=0)
        delta[i,j,exposed]-=removed
        loss+=float(removed.sum())
        temperature+=delta
        assert temperature.min()>=-1e-12
    balance=abs(float(temperature.sum())+loss-mass)
    assert balance<1e-10
    return {"peak_at_64":float(temperature.max()),"removed_heat":loss,"energy_error":balance}


def scan(material,seed,ch=2,noise=.01):
    values=SIGNATURE[material]+np.random.default_rng(seed).normal(0,noise,(*SHAPE,2))
    steps=np.linalg.norm(values[...,:ch][...,None,:]-SIGNATURE[:,:ch],axis=-1)
    rank=np.argsort(steps,axis=-1)
    ranks=np.take_along_axis(steps,rank,axis=-1)
    return np.where((ranks[...,1]-ranks[...,0]>.10)&(ranks[...,0]<.12),rank[...,0],-1).astype("int8")


def print_coupon(blueprint,stock,drop=None):
    if (blueprint<0).any():raise ValueError("Scan contains unresolved voxels")
    need=Counter(blueprint[blueprint>0].tolist())
    reserve=need.copy()
    if drop is not None: reserve[int(blueprint[drop])]+=1
    if any(stock.get(m,0)<n for m,n in reserve.items()): raise ValueError("Feedstock shortage")
    stock=Counter(stock)
    opening=stock.copy()
    printed=np.zeros(SHAPE,np.int8)
    dropped=[]
    for z in range(SHAPE[2]):
        for x,y in np.argwhere(blueprint[:,:,z]>0):
            point=(x,y,z); material=int(blueprint[point])
            if z and not printed[x,y,z-1]: raise ValueError("Unsupported virtual placement")
            if point==drop:
                stock[material]-=1
                dropped.append(material)
            stock[material]-=1
            printed[point]=material
    accounted=stock+Counter(printed[printed>0].tolist())+Counter(dropped)
    assert accounted==opening
    return printed,{"wasted_packets":len(dropped),"remaining_packets":dict(stock),"used":dict(need)}


def scad(out,specimen):
    with out.open("w") as f:
        f.write('// Simulated geometry in nominal voxel units.\n')
        # Model the substrate plus visualized internal high-conductivity cells as two switchable parts.
        f.write('mode="cutaway"; // [cutaway,whole,conductor]\n')
        for m,color in ((1,'[.29,.29,.42,.50]'),(2,'[1,.31,.73,1]')):
            f.write(f'color({color}) {{\n')
            for x,y,z in np.argwhere(specimen==m).tolist():
                condition='mode!="conductor" && (mode=="whole" || y<8)' if m==1 else 'true'
                f.write(f'    if ({condition.replace("y<8",str(y)+"<8")}) translate([{x},{y},{z}]) cube(1);\n')
            f.write('}\n')


def experiment():
    designs={n:layout(n) for n in (*LAYOUTS,"plain")}
    baselines={(w,o):thermal(designs["plain"],w,o) for w,o in (("uniform",0),("layered",0),("sink",0),("skew_holdout",2))}
    values={name:{w:thermal(designs[name],w,0) for w in ("uniform","layered","sink")} for name in LAYOUTS}
    ranked=sorted(LAYOUTS,key=lambda n:max(values[n][w]["peak_at_64"]/baselines[w,0]["peak_at_64"]
                                            for w in ("uniform","layered","sink")))
    winner=ranked[0]
    known=designs[winner]
    read=scan(known,31)
    assert np.array_equal(read,known)
    stock=Counter(read[read>0].tolist())
    spot=tuple(np.argwhere(read==2)[0])
    stock[2]+=1
    a,first=print_coupon(read,stock,spot)
    b,second=print_coupon(read,stock)
    assert np.array_equal(scan(a,51),read) and np.array_equal(scan(b,53),read)
    assert int((read==2).sum())==MATERIAL_BUDGET
    refused=[]
    for name,data,supply in (("one_channel",scan(known,31,1),stock),
                              ("short_stock",read,Counter({1:1,2:48}))):
        try:print_coupon(data,supply)
        except ValueError:refused.append(name)
        else:raise RuntimeError(f"{name} was accepted")
    check=thermal(known,"skew_holdout",2)
    held=baselines["skew_holdout",2]
    held_equal=thermal(designs["spread"],"skew_holdout",2)
    report={"ranked":ranked,"winner":winner,"equal_candidate_budget":MATERIAL_BUDGET,
        "same_budget_control":"spread","discovery":values,
        "plain_controls":{w:v for (w,o),v in baselines.items()},
        "held_out":{"candidate":check,"plain":held,"equal_budget_spread":held_equal,
                    "passes":check["peak_at_64"]<=min(held["peak_at_64"],held_equal["peak_at_64"])},
        "copies_exact":2,"first_copy":first,"second_copy":second,"negative_controls":refused,
        "scope":"Synthetic steady-coefficient transport and voxel printing. Materials and scans are simulated."}
    return report,known
