#!/usr/bin/env python3
"""Independent ODE-method cross-check of a standards-validated synthetic SBML toy.

Read-only libSBML AST evaluator + SciPy DOP853 vs independent hand-derived
mass-action RHS + Radau. All parameters synthetic. This is NOT a live
BioModels reproduction, a measured enzyme mechanism, or proof of kinetics.
"""
import argparse
import hashlib
import json
from pathlib import Path

import libsbml
import numpy as np
from scipy.integrate import solve_ivp


NAMES=("E","S","ES","P")


def ast_value(node, env):
    # Fail closed on unknown SBML MathML syntax: no eval or dynamic execution.
    if node.getType()==libsbml.AST_TIMES:
        value=1.0
        for i in range(node.getNumChildren()):
            value*=ast_value(node.getChild(i),env)
        return value
    if node.isName():
        name=node.getName()
        if name not in env:
            raise ValueError("undefined SBML kinetic symbol "+name)
        return float(env[name])
    if node.isNumber():
        return float(node.getReal())
    raise ValueError("unsupported kinetic AST node "+str(node.getType()))


def load_model(path):
    d=libsbml.readSBMLFromFile(str(path))
    d.checkConsistency()
    errors=[d.getError(i).getMessage() for i in range(d.getNumErrors())
            if d.getError(i).getSeverity()>=libsbml.LIBSBML_SEV_ERROR]
    if errors:
        raise ValueError("SBML semantic validation failed: "+str(errors[:3]))
    model=d.getModel()
    if model.getNumSpecies()!=4 or model.getNumReactions()!=3:
        raise ValueError("unexpected species/reactions")
    species=tuple(model.getSpecies(i).getId() for i in range(4))
    if species!=NAMES:
        raise ValueError("species order mismatch")
    reactions=tuple(model.getReaction(i) for i in range(3))
    rates={model.getParameter(i).getId():model.getParameter(i).getValue()
           for i in range(model.getNumParameters())}
    if set(rates)!={"kon","koff","kcat"}:
        raise ValueError("unknown parameters")
    matrix=np.zeros((4,3))
    for j,reaction in enumerate(reactions):
        if not reaction.isSetKineticLaw():
            raise ValueError("missing kinetic equation")
        for ref in reaction.getListOfReactants():
            matrix[NAMES.index(ref.getSpecies()),j]-=ref.getStoichiometry()
        for ref in reaction.getListOfProducts():
            matrix[NAMES.index(ref.getSpecies()),j]+=ref.getStoichiometry()
    expect=np.array([[-1,1,1],[-1,1,0],[1,-1,-1],[0,0,1]])
    if not np.array_equal(matrix,expect):
        raise ValueError("unexpected reaction topology")
    for row in ((1,0,1,0),(0,1,1,1)):
        if not np.array_equal(np.array(row)@matrix,np.zeros(3)):
            raise ValueError("conservation relation invalid")
    # Keep the owner SBMLDocument alive while borrowed SWIG reaction/AST views are used.
    # Returning only child views can produce a native use-after-free/segfault.
    return d,reactions,rates,matrix


def experiment(path):
    document,reactions,k,matrix=load_model(path)
    assert document.getModel() is not None
    def sbml_rhs(t,y):
        env=dict(zip(NAMES,y))
        env.update(k)
        flux=np.array([ast_value(r.getKineticLaw().getMath(),env)
                       for r in reactions])
        return matrix@flux

    def independent_rhs(t,y):
        e,s,complex,p=y
        forward=k["kon"]*e*s
        reverse=k["koff"]*complex
        catalytic=k["kcat"]*complex
        return np.array([-forward+reverse+catalytic,
                         -forward+reverse,
                         forward-reverse-catalytic,
                         catalytic])

    samples=(np.array([2.,2.,0.,0.]),np.array([1.,3.,0.,0.]),
             np.array([1.,2.,0.5,0.]))
    times=np.linspace(0,2,81)
    results=[]
    for initial in samples:
        producer=solve_ivp(sbml_rhs,(0,2),initial,method="DOP853",
                           rtol=1e-10,atol=1e-12,t_eval=times)
        independent=solve_ivp(independent_rhs,(0,2),initial,method="Radau",
                              rtol=1e-10,atol=1e-12,t_eval=times)
        if not producer.success or not independent.success:
            raise AssertionError("ODE numerical solver unsuccessful")
        max_diff=float(np.max(np.abs(producer.y-independent.y)))
        if max_diff>2e-7:
            raise AssertionError("independent solver drift: "+str(max_diff))
        for row in ((1,0,1,0),(0,1,1,1)):
            conservation=np.array(row)@producer.y
            if max(abs(conservation-conservation[0]))>1e-8:
                raise AssertionError("mass balance drift")
        if min(producer.y.flatten()) < -1e-9:
            raise AssertionError("negative concentrations beyond tolerance")
        results.append({"samples":len(times),"max_solver_difference":max_diff,
                        "max_conservation_residual":float(max(
                            max(abs(np.array(row)@producer.y-
                                    (np.array(row)@producer.y)[0]))
                            for row in ((1,0,1,0),(0,1,1,1))))})
    # Negative control: if catalytic product formation is forgotten,
    # measured substrate-moiety balance cannot be claimed.
    def lost_product_rhs(t,y):
        d=independent_rhs(t,y)
        d[3]=0.
        return d
    bad=solve_ivp(lost_product_rhs,(0,2),samples[0],method="Radau",
                  rtol=1e-9,atol=1e-11,t_eval=times)
    invariant=(bad.y[1]+bad.y[2]+bad.y[3])
    if float(max(abs(invariant-invariant[0])))<=1e-2:
        raise AssertionError("missing product reaction mutant survived")
    return {
      "schema_version":1,"experiment":"sbml-synthetic-enzyme-ode-crosscheck-v1",
      "model_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
      "solvers":["scipy.DOP853","scipy.Radau"],
      "producer_uses_libsbml_kinetic_ast":True,
      "independent_derivation_uses_explicit_mass_action":True,
      "cases":results,
      "total_solution_samples":sum(x["samples"] for x in results),
      "missing_product_mutant_detected":True,
      "real_biomodel_reproduced":False,
      "biochemical_parameters_measured":False,
      "pde_qualification_performed":False,
      "authority_expanded":False,
    }


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--sbml",type=Path,required=True)
    ap.add_argument("-o",required=True)
    args=ap.parse_args()
    report=experiment(args.sbml)
    Path(args.o).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report))
