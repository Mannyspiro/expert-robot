"""Dimensionless conservative 3D heat diffusion across three selectable worlds."""
import numpy as np

WORLDS={
    "uniform":("Uniform, insulated", (0.11,0.11,0.11),0.0),
    "layered":("Layered anisotropic", (0.16,0.14,0.04),0.0),
    "sink":("Layered with heat sink", (0.16,0.14,0.04),0.075),
}


def solve(world,steps=80,history=None,backend="reference",shape=(20,20,12),offset=0):
    label,coeff,sink=WORLDS[world]
    grid=np.zeros(shape,dtype=float)
    cx,cy,cz=(d//2 for d in shape)
    grid[cx-2+offset:cx+2+offset,cy-2:cy+2,cz:cz+3]=1
    initial=float(grid.sum())
    values=np.full(shape,coeff[2],dtype=float)
    if world!="uniform":
        values[:,:,::3]*=2.5
    lost=0.
    totals=[initial]
    if history is not None: history.append(grid.copy())
    def neighbors():
        out=[]
        for ax,k in enumerate(coeff):
            p=[slice(None)]*3
            q=[slice(None)]*3
            p[ax]=slice(None,-1)
            q[ax]=slice(1,None)
            a,b=tuple(p),tuple(q)
            shared=2*values[a]*values[b]/(values[a]+values[b]) if ax==2 else k
            out.append((a,b,shared))
        return out
    if backend not in ("reference","precomputed"):
        raise ValueError("Unknown heat backend")
    plan=neighbors() if backend=="precomputed" else None
    for _ in range(steps):
        d=np.zeros_like(grid)
        for a,b,shared in (plan if plan is not None else neighbors()):
            flux=shared*(grid[b]-grid[a])
            d[a]+=flux
            d[b]-=flux
        removed=sink*grid[:,:,0]
        lost+=float(removed.sum())
        d[:,:,0]-=removed
        grid+=d
        assert grid.min()>=-1e-14
        totals.append(float(grid.sum()))
        if history is not None: history.append(grid.copy())
    residual=abs(initial-totals[-1]-lost)
    assert residual<1e-10
    return {"world":world,"name":label,"grid":shape,"steps":steps,"initial_heat":initial,
        "remaining_heat":totals[-1],"removed_heat":lost,"balance_error":residual,
        "peak":float(grid.max()),"slice":grid[:,:,min(7,shape[2]-1)].tolist(),"heat_curve":totals}


def frame_field(world,steps):
    history=[]
    solve(world,steps,history)
    # Preserve time and X/Y geometry for a fixed Z slice.
    return [grid[:,:,7] for grid in history]
