#!/usr/bin/env python3
"""Generate a narrow SBML L3V2 example and independently inspect stoichiometry.

This is *not* a general SBML parser or a claim of empirical biochemical
parameters. libSBML semantic checking is performed separately in CI.
"""
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

SBML="http://www.sbml.org/sbml/level3/version2/core"
MATH="http://www.w3.org/1998/Math/MathML"
ET.register_namespace("",SBML)


def s(tag):
    return "{"+SBML+"}"+tag


def m(tag):
    return "{"+MATH+"}"+tag


REACTIONS=(
    ("binding",(("E",1),("S",1)),(("ES",1),),("kon","E","S")),
    ("unbinding",(("ES",1),),(("E",1),("S",1)),("koff","ES")),
    ("catalysis",(("ES",1),),(("E",1),("P",1)),("kcat","ES")),
)
SPECIES=("E","S","ES","P")


def build():
    root=ET.Element(s("sbml"),{"level":"3","version":"2"})
    model=ET.SubElement(root,s("model"),{
        "id":"synthetic_closed_enzyme","substanceUnits":"mole",
        "extentUnits":"mole","timeUnits":"second","volumeUnits":"litre"})
    units=ET.SubElement(model,s("listOfUnitDefinitions"))
    for name,parts in (
        ("per_time",(("second",-1),)),
        ("per_amount_time",(("mole",-1),("second",-1)))):
        definition=ET.SubElement(units,s("unitDefinition"),{"id":name})
        listing=ET.SubElement(definition,s("listOfUnits"))
        for kind,exponent in parts:
            ET.SubElement(listing,s("unit"),{
                "kind":kind,"exponent":str(exponent),"scale":"0",
                "multiplier":"1"})
    compartments=ET.SubElement(model,s("listOfCompartments"))
    ET.SubElement(compartments,s("compartment"),{
        "id":"cytosol","size":"1","units":"litre",
        "spatialDimensions":"3","constant":"true"})
    species=ET.SubElement(model,s("listOfSpecies"))
    for name in SPECIES:
        ET.SubElement(species,s("species"),{
            "id":name,"compartment":"cytosol","initialAmount":
                "2" if name in ("E","S") else "0",
            "substanceUnits":"mole","hasOnlySubstanceUnits":"true",
            "boundaryCondition":"false","constant":"false"})
    params=ET.SubElement(model,s("listOfParameters"))
    for name,units in (("kon","per_amount_time"),
                       ("koff","per_time"),("kcat","per_time")):
        ET.SubElement(params,s("parameter"),{
            "id":name,"value":"1","units":units,"constant":"true"})
    reactions=ET.SubElement(model,s("listOfReactions"))
    for name,reactants,products,law in REACTIONS:
        reaction=ET.SubElement(reactions,s("reaction"),{
            "id":name,"reversible":"false"})
        for label,rows in (("listOfReactants",reactants),
                           ("listOfProducts",products)):
            group=ET.SubElement(reaction,s(label))
            for element,n in rows:
                ET.SubElement(group,s("speciesReference"),{
                    "species":element,"stoichiometry":str(n),
                    "constant":"true"})
        kinetic=ET.SubElement(reaction,s("kineticLaw"))
        math=ET.SubElement(kinetic,m("math"))
        apply=ET.SubElement(math,m("apply"))
        ET.SubElement(apply,m("times"))
        for token in law:
            ET.SubElement(apply,m("ci")).text=token
    return ET.tostring(root,encoding="utf-8",xml_declaration=True)


def inspect(data):
    # The review scope is intentionally much smaller than the full SBML schema.
    if len(data)>100000 or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("external entities or large/untrusted XML unsupported")
    root=ET.fromstring(data)
    if root.tag!=s("sbml") or root.attrib!={"level":"3","version":"2"}:
        raise ValueError("unsupported SBML level/version/package")
    models=list(root)
    if len(models)!=1 or models[0].tag!=s("model"):
        raise ValueError("one model required")
    model=models[0]
    expected_sections={"listOfUnitDefinitions","listOfCompartments",
                       "listOfSpecies","listOfParameters","listOfReactions"}
    if {node.tag.removeprefix("{"+SBML+"}") for node in model} != expected_sections:
        raise ValueError("unsupported SBML feature")
    if len(list(model))!=len(expected_sections):
        raise ValueError("duplicate model section")
    species=model.find(s("listOfSpecies"))
    names=[x.attrib.get("id") for x in species]
    if names!=list(SPECIES):
        raise ValueError("species mismatch")
    if any(x.tag!=s("species") or x.get("constant")!="false" or
           x.get("boundaryCondition")!="false" or
           x.get("hasOnlySubstanceUnits")!="true" for x in species):
        raise ValueError("constant/boundary species unsupported")
    reactions=model.find(s("listOfReactions"))
    if len(reactions)!=len(REACTIONS):
        raise ValueError("unexpected reaction count")
    matrix=[]
    for row,(id,reactants,products,law) in zip(reactions,REACTIONS):
        if row.tag!=s("reaction") or row.get("id")!=id or row.get("reversible")!="false":
            raise ValueError("unqualified reaction")
        left=row.find(s("listOfReactants"))
        right=row.find(s("listOfProducts"))
        if left is None or right is None:
            raise ValueError("reactant/product list missing")
        def pairs(lst):
            ans=[]
            for entry in lst:
                if entry.tag!=s("speciesReference") or entry.get("constant")!="true":
                    raise ValueError("unsupported stoichiometry rule")
                ref=entry.get("species")
                if ref not in SPECIES:
                    raise ValueError("undeclared species")
                num=F(entry.get("stoichiometry"))
                if num<=0:
                    raise ValueError("nonpositive coefficient")
                ans.append((ref,num))
            return tuple(ans)
        inputs,outputs=pairs(left),pairs(right)
        if inputs!=tuple((n,F(c)) for n,c in reactants) or outputs!=tuple((n,F(c)) for n,c in products):
            raise ValueError("reaction stoichiometry drift")
        # Model must explicitly retain kinetic expressions: a missing law
        # may be perfectly valid SBML but is not simulation-equivalent.
        kinetic=row.find(s("kineticLaw"))
        if kinetic is None:
            raise ValueError("kineticLaw omitted: numerical experiment unsupported")
        mroot=kinetic.find(m("math"))
        if mroot is None or len(mroot)!=1:
            raise ValueError("unsupported MathML")
        app=mroot[0]
        if app.tag!=m("apply") or len(app)!=len(law)+1 or app[0].tag!=m("times") or tuple(
                x.text for x in app[1:])!=law:
            raise ValueError("kinetic expression drift")
        vec=[sum(v for n,v in outputs if n==sp)-
             sum(v for n,v in inputs if n==sp) for sp in SPECIES]
        matrix.append(vec)
    laws={"total_enzyme":(1,0,1,0),
          "substrate_moiety":(0,1,1,1)}
    for vec in matrix:
        for invariant in laws.values():
            if sum(v*x for v,x in zip(vec,invariant))!=0:
                raise ValueError("conservation violated")
    return {
        "experiment":"sbml-l3v2-synthetic-enzyme-roundtrip-v1",
        "model_scope":"single compartment, three reactions, named mass-action formulas",
        "species":list(SPECIES),"stoichiometry_columns":[[str(x) for x in c] for c in matrix],
        "enzyme_conservation":True,"substrate_moiety_conservation":True,
        "kinetic_expressions_preserved":True,
        "full_sbml_schema_validated_here":False,
        "independent_sbml_library_check_needed":True,
        "full_kinetic_trajectory_cross_solver_reproduced":False,
        "empirical_parameters_used":False,"network_operations":0,
        "authority_expanded":False,
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--sbml",required=True)
    p.add_argument("-o","--report",required=True)
    args=p.parse_args()
    data=build()
    report=inspect(data)
    report["sbml_sha256"]=hashlib.sha256(data).hexdigest()
    # Negative controls must fail closed: stoichiometry change, missing law,
    # and untrusted XML definitions.
    mutants=[
        data.replace(b'species="S" stoichiometry="1"',b'species="P" stoichiometry="1"',1),
        data.replace(b'<kineticLaw>',b'<unexpected>',1).replace(b'</kineticLaw>',b'</unexpected>',1),
        data.replace(b'<?xml version',b'<!DOCTYPE data [<!ENTITY x SYSTEM "file:///etc/passwd">]><?xml version',1),
    ]
    for mutant in mutants:
        try:
            inspect(mutant)
        except (ValueError,ET.ParseError):
            continue
        raise AssertionError("SBML mutation accepted")
    report["mutations_rejected"]=len(mutants)
    Path(args.sbml).write_bytes(data)
    Path(args.report).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report))
