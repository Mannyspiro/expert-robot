#!/usr/bin/env python3
"""Generate deterministic CACE mathematical puzzle boxes.

A puzzle box is a deliberately structured research problem whose construction
contains a hidden invariant, obstruction, equivalence, or counterexample seed.
The proposer sees visible_problem + probes; the sealed construction is reserved
for evaluation.

The generator is deterministic and dependency-free.
"""

from __future__ import annotations

import argparse
import json
import random
from fractions import Fraction
from pathlib import Path


FAMILIES = (
    "symmetry_orbit",
    "boundary_mutation",
    "duality",
    "scaling_collapse",
    "spectral_collision",
    "discrete_continuum",
    "metamaterial_cell",
    "certification_gap",
    "historical_geometry_control",
)


def q(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def base(box_id, family, domain, mechanism, seed):
    return {
        "schema_version": "0.1",
        "box_id": box_id,
        "family": family,
        "domain": domain,
        "visible_problem": {
            "objects": [],
            "constraints": [],
            "observables": [],
            "question": "",
        },
        "sealed_construction": {
            "withhold_from_proposer": True,
            "mechanism": mechanism,
            "witnesses": [],
            "counterexample_seed": None,
        },
        "probes": [],
        "success_criteria": {
            "discovery": [],
            "proof": [],
            "efficiency": [],
        },
        "formalization": {
            "lean_namespace": "MathAI.PuzzleBox",
            "target_kind": "theorem",
            "status": "UNSEEN",
            "theorem_ref": None,
        },
        "provenance": {
            "generator": "generate_math_puzzle_boxes.py",
            "seed": seed,
            "source_family": None,
        },
    }


def symmetry_orbit(rng, seed):
    r = rng.randint(2, 11)
    p = (rng.randint(1, 9), rng.randint(1, 9), rng.randint(-4, 4))
    orbit = [
        p,
        (-p[1], p[0], p[2]),
        (-p[0], -p[1], p[2]),
        (p[1], -p[0], p[2]),
    ]
    box = base(
        f"symmetry-orbit-{seed}",
        "symmetry_orbit",
        ["exact_geometry", "group_actions"],
        "C4 orbit under quarter-turn action preserves origin-centered quadratic radius.",
        seed,
    )
    box["visible_problem"]["objects"] = [
        {"kind":"circle","radius_squared":r*r},
        {"kind":"point_set","points":[list(x) for x in orbit]},
    ]
    box["visible_problem"]["constraints"] = [
        "all arithmetic is exact",
        "identify the smallest transformation group explaining repeated observables",
    ]
    vals = [x*x+y*y+z*z for x,y,z in orbit]
    box["visible_problem"]["observables"] = [
        {"name":"rho2","values":vals}
    ]
    box["visible_problem"]["question"] = (
        "Find a minimal exact equivalence relation that removes redundant evaluations."
    )
    box["sealed_construction"]["witnesses"] = [
        {"orbit": [list(x) for x in orbit], "invariant": vals[0]}
    ]
    box["probes"] = [
        {"lens":"symmetry","instruction":"search for a finite group action preserving the observable"},
        {"lens":"exact_geometry","instruction":"state the invariant as an exact algebraic identity"},
    ]
    box["success_criteria"]["discovery"] = ["recover a C4-orbit explanation"]
    box["success_criteria"]["proof"] = ["prove observable invariance under a generator"]
    box["success_criteria"]["efficiency"] = ["reduce four evaluations to one canonical representative"]
    return box


def boundary_mutation(rng, seed):
    n = rng.choice([8, 12, 16])
    opening = rng.randrange(n)
    box = base(
        f"boundary-mutation-{seed}",
        "boundary_mutation",
        ["topology", "graph_theory", "pde_boundary_models"],
        "One missing boundary edge changes cycle rank and may change admissible boundary-condition classes.",
        seed,
    )
    closed_edges = [[i, (i+1)%n] for i in range(n)]
    open_edges = [e for i,e in enumerate(closed_edges) if i != opening]
    box["visible_problem"]["objects"] = [
        {"kind":"cycle_graph","vertices":n,"edges":closed_edges,"label":"A"},
        {"kind":"near_cycle_graph","vertices":n,"edges":open_edges,"label":"B"},
    ]
    box["visible_problem"]["constraints"] = ["A and B differ by exactly one edge"]
    box["visible_problem"]["observables"] = [
        {"name":"edge_count","A":len(closed_edges),"B":len(open_edges)}
    ]
    box["visible_problem"]["question"] = (
        "Determine the smallest invariant that certifies the topological distinction and predict which solver assumptions can change."
    )
    box["sealed_construction"]["witnesses"] = [
        {"A_cycle_rank":1,"B_cycle_rank":0,"removed_edge_index":opening}
    ]
    box["probes"] = [
        {"lens":"topology","instruction":"compare homology/cycle-rank before metric details"},
        {"lens":"counterexample","instruction":"test whether a metric-only classifier can distinguish the pair"},
    ]
    box["success_criteria"]["discovery"] = ["identify cycle-rank or equivalent topological obstruction"]
    box["success_criteria"]["proof"] = ["prove edge removal changes the selected invariant"]
    box["success_criteria"]["efficiency"] = ["use invariant to route solver/boundary-condition logic early"]
    return box


def scaling_collapse(rng, seed):
    k = rng.choice([-2,-1,1,2,3])
    c = rng.randint(1,7)
    xs = [Fraction(i, rng.choice([1,2,3])) for i in range(1,7)]
    ys = [Fraction(c) * (x ** k) for x in xs]
    box = base(
        f"scaling-collapse-{seed}",
        "scaling_collapse",
        ["analysis","dimensional_reasoning","numerical_reuse"],
        f"Exact homogeneous law y={c}*x^{k}.",
        seed,
    )
    box["visible_problem"]["objects"] = [{"kind":"sample_family","x":[q(x) for x in xs]}]
    box["visible_problem"]["observables"] = [{"name":"response","values":[q(y) for y in ys]}]
    box["visible_problem"]["constraints"] = ["samples are exact rationals"]
    box["visible_problem"]["question"] = "Infer the simplest exact scaling law and a normalization that collapses all samples."
    box["sealed_construction"]["witnesses"] = [{"coefficient":c,"exponent":k}]
    box["probes"] = [
        {"lens":"scaling","instruction":"search for exact homogeneity, not floating regression"},
        {"lens":"dimensionless","instruction":"construct a normalized invariant"}
    ]
    box["success_criteria"]["discovery"] = ["recover exact exponent and normalized constant"]
    box["success_criteria"]["proof"] = ["formalize a homogeneity identity with explicit domain assumptions"]
    box["success_criteria"]["efficiency"] = ["reuse one normalized solution across a scale family"]
    return box


def duality(rng, seed):
    a,b,c = [rng.randint(2,9) for _ in range(3)]
    box = base(
        f"duality-{seed}",
        "duality",
        ["algebra","geometry","optimization"],
        "Primal parameter triple is paired with reversed reciprocal-like transform preserving a symmetric objective.",
        seed,
    )
    primal=[a,b,c]
    dual=[c,b,a]
    box["visible_problem"]["objects"]=[
        {"kind":"parameter_tuple","label":"P","values":primal},
        {"kind":"parameter_tuple","label":"D","values":dual},
    ]
    box["visible_problem"]["observables"]=[
        {"name":"symmetric_sum","P":sum(primal),"D":sum(dual)},
        {"name":"symmetric_product","P":a*b*c,"D":c*b*a},
    ]
    box["visible_problem"]["question"]="Find the involution relating P and D and classify observables invariant under it."
    box["sealed_construction"]["witnesses"]=[{"involution":"reverse","fixed_middle":b}]
    box["probes"]=[
        {"lens":"duality","instruction":"search for an involution before fitting unrelated formulas"},
        {"lens":"operator_factorization","instruction":"identify symmetric expressions that descend to the quotient"}
    ]
    box["success_criteria"]["discovery"]=["recover the involution and invariant algebra"]
    box["success_criteria"]["proof"]=["prove the transform is involutive and selected observables invariant"]
    box["success_criteria"]["efficiency"]=["deduplicate dual-equivalent search states"]
    return box


def spectral_collision(rng, seed):
    # Deliberately simple trace/determinant collision for 2x2 integer matrices.
    t = rng.randint(3,9)
    d = rng.randint(1,t*t//4)
    a = rng.randint(0,t)
    b = 1
    c = a*(t-a)-d
    A=[[a,b],[c,t-a]]
    B=[[t-a,b],[c,a]]
    box=base(
        f"spectral-collision-{seed}",
        "spectral_collision",
        ["linear_algebra","spectral_methods"],
        "Two matrices share characteristic polynomial by equal trace and determinant but differ entrywise.",
        seed,
    )
    box["visible_problem"]["objects"]=[
        {"kind":"matrix","label":"A","values":A},
        {"kind":"matrix","label":"B","values":B},
    ]
    box["visible_problem"]["observables"]=[
        {"name":"trace","A":t,"B":t},
        {"name":"determinant","A":d,"B":d},
    ]
    box["visible_problem"]["question"]="Decide what spectral data can and cannot identify about the underlying operator."
    box["sealed_construction"]["witnesses"]=[{"shared_characteristic_polynomial":True}]
    box["probes"]=[
        {"lens":"spectral","instruction":"derive the characteristic polynomial exactly"},
        {"lens":"counterexample","instruction":"use the pair as a counterexample to naive operator identification from spectrum alone"}
    ]
    box["success_criteria"]["discovery"]=["recognize isospectral ambiguity"]
    box["success_criteria"]["proof"]=["prove equal characteristic polynomials"]
    box["success_criteria"]["efficiency"]=["avoid overfitting inverse problems to insufficient spectral observables"]
    box["formalization"]["target_kind"]="counterexample"
    return box


def certification_gap(rng, seed):
    approx = Fraction(rng.randint(1,20), 10)
    eta = Fraction(rng.randint(1,5), 100)
    true_err = eta + Fraction(rng.choice([-1,1]),1000)
    box=base(
        f"certification-gap-{seed}",
        "certification_gap",
        ["numerical_analysis","a_posteriori_error"],
        "Estimator and true-error values are deliberately near a decision boundary.",
        seed,
    )
    box["visible_problem"]["objects"]=[{"kind":"approximation","value":q(approx)}]
    box["visible_problem"]["observables"]=[
        {"name":"estimator_eta","value":q(eta)},
        {"name":"independent_error_probe","value":q(true_err)},
    ]
    box["visible_problem"]["question"]="Find the weakest sufficient condition for a sound accept/reject certificate near the boundary."
    box["sealed_construction"]["witnesses"]=[{"eta":q(eta),"true_error":q(true_err)}]
    box["probes"]=[
        {"lens":"error_estimation","instruction":"separate estimator reliability from numerical convergence"},
        {"lens":"counterexample","instruction":"test any proposed threshold on both sides of the boundary"}
    ]
    box["success_criteria"]["discovery"]=["identify missing reliability/constant assumption"]
    box["success_criteria"]["proof"]=["prove a sound bound with explicit constants"]
    box["success_criteria"]["efficiency"]=["tighten certification without unnecessary refinement"]
    box["formalization"]["target_kind"]="bound"
    return box


def metamaterial_cell(rng, seed):
    n=rng.choice([4,6,8])
    pattern=[rng.choice([0,1]) for _ in range(n)]
    rotated=pattern[1:]+pattern[:1]
    box=base(
        f"metamaterial-cell-{seed}",
        "metamaterial_cell",
        ["metamaterials","periodic_geometry","spectral_methods"],
        "Unit-cell descriptions differ by cyclic relabeling of a periodic orbit.",
        seed,
    )
    box["visible_problem"]["objects"]=[
        {"kind":"unit_cell_ring","label":"A","sectors":pattern},
        {"kind":"unit_cell_ring","label":"B","sectors":rotated},
    ]
    box["visible_problem"]["constraints"]=["periodic boundary interpretation"]
    box["visible_problem"]["question"]="Determine whether the two cells are physically distinct or gauge/orbit-equivalent under periodic relabeling."
    box["sealed_construction"]["witnesses"]=[{"rotation_steps":1,"equivalent_under_cyclic_action":True}]
    box["probes"]=[
        {"lens":"symmetry","instruction":"quotient cyclic relabelings before expensive simulation"},
        {"lens":"spectral","instruction":"predict which spectra should be invariant under cell relabeling"}
    ]
    box["success_criteria"]["discovery"]=["identify cyclic-equivalence class"]
    box["success_criteria"]["proof"]=["prove permutation similarity for the chosen discrete operator model"]
    box["success_criteria"]["efficiency"]=["deduplicate equivalent metamaterial candidates before solving"]
    return box


def historical_geometry_control(rng, seed):
    rings=rng.choice([2,3,4])
    labels=list(range(4))
    shuffled=labels[:]
    rng.shuffle(shuffled)
    box=base(
        f"historical-geometry-control-{seed}",
        "historical_geometry_control",
        ["historical_geometry","experimental_design","causal_inference"],
        "Geometry is held fixed while symbolic identity-position assignment is permuted.",
        seed,
    )
    box["visible_problem"]["objects"]=[
        {"kind":"concentric_rings","count":rings},
        {"kind":"symbol_assignment_A","positions":labels},
        {"kind":"symbol_assignment_B","positions":shuffled},
    ]
    box["visible_problem"]["constraints"]=["same ring geometry","same symbol multiset"]
    box["visible_problem"]["question"]="Design the minimal ablation that separates geometry from symbol-position information."
    box["sealed_construction"]["witnesses"]=[{"geometry_same":True,"symbol_binding_same":labels==shuffled}]
    box["probes"]=[
        {"lens":"exact_geometry","instruction":"prove the geometric state is unchanged"},
        {"lens":"counterexample","instruction":"show why geometry-only evidence cannot identify symbolic causation"}
    ]
    box["success_criteria"]["discovery"]=["separate geometric and symbolic channels"]
    box["success_criteria"]["proof"]=["formalize geometry equivalence independent of label assignment"]
    box["success_criteria"]["efficiency"]=["avoid re-solving geometry when only symbolic metadata changes"]
    return box


def discrete_continuum(rng, seed):
    n0=rng.choice([4,8])
    ns=[n0,2*n0,4*n0,8*n0]
    vals=[Fraction(1,n) for n in ns]
    box=base(
        f"discrete-continuum-{seed}",
        "discrete_continuum",
        ["discrete_geometry","continuum_limit","convergence"],
        "Synthetic first-order convergence sequence.",
        seed,
    )
    box["visible_problem"]["objects"]=[{"kind":"mesh_sequence","cells":ns}]
    box["visible_problem"]["observables"]=[{"name":"error_proxy","values":[q(v) for v in vals]}]
    box["visible_problem"]["question"]="Infer convergence order and propose the exact statement needed to justify extrapolation."
    box["sealed_construction"]["witnesses"]=[{"order":1}]
    box["probes"]=[
        {"lens":"scaling","instruction":"compare successive refinement ratios"},
        {"lens":"error_estimation","instruction":"separate empirical order from a proven convergence theorem"}
    ]
    box["success_criteria"]["discovery"]=["recover first-order convergence"]
    box["success_criteria"]["proof"]=["state assumptions needed for an exact error estimate"]
    box["success_criteria"]["efficiency"]=["predict refinement depth before solving all levels"]
    return box


GENERATORS={
    "symmetry_orbit":symmetry_orbit,
    "boundary_mutation":boundary_mutation,
    "duality":duality,
    "scaling_collapse":scaling_collapse,
    "spectral_collision":spectral_collision,
    "discrete_continuum":discrete_continuum,
    "metamaterial_cell":metamaterial_cell,
    "certification_gap":certification_gap,
    "historical_geometry_control":historical_geometry_control,
}


def generate(seed, families=None):
    rng=random.Random(seed)
    selected=list(families or FAMILIES)
    return {
        "schema_version":1,
        "seed":seed,
        "boxes":[GENERATORS[name](rng,seed*100+i) for i,name in enumerate(selected)],
        "proposer_view_policy":"withhold sealed_construction",
        "evaluation_policy":"compare discovered structure to sealed witnesses only after proposal is frozen",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seed",type=int,default=1)
    p.add_argument("--family",action="append",choices=FAMILIES)
    p.add_argument("-o","--output",type=Path)
    args=p.parse_args()
    payload=generate(args.seed,args.family)
    rendered=json.dumps(payload,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.write_text(rendered,encoding="utf-8")
    else:
        print(rendered,end="")


if __name__=="__main__":
    main()
