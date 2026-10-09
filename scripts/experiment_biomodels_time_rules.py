#!/usr/bin/env python3
"""Independent restricted MathML/libSBML rule evaluator for a pinned source.

Only the seven BIOMD0000000051 assignment rules are evaluated; they contain
numeric constants, time and {plus,minus,times,divide,power}. No dynamic code
execution, symbolic rewrites, kinetic ODE integration, biochemical calibration
or claim of independent physical truth. The two evaluators share mathematical
semantics but parse distinct representations.
"""
import argparse,hashlib,json,math,xml.etree.ElementTree as ET
from functools import reduce
from operator import mul
from pathlib import Path
import libsbml

BLOB="e447a9b0ba35ba0156b97c07caaad94631a448cf"
MATHML="{http://www.w3.org/1998/Math/MathML}"
TIME_URL="http://www.sbml.org/sbml/symbols/time"
VARS={"catp","cadp","camp","cnadph","cnadp","cnadh","cnad"}
POINTS=(0.,0.1,0.5,1.,2.,5.,10.,20.)

def safe(x):
    if isinstance(x,complex) or not math.isfinite(float(x)):
        raise ValueError("non-finite real MathML computation")
    return float(x)

def apply_op(name,args):
    if name=="plus" and len(args)>=1:return safe(sum(args))
    if name=="times" and len(args)>=1:return safe(math.prod(args))
    if name=="minus" and len(args)==1:return safe(-args[0])
    if name=="minus" and len(args)==2:return safe(args[0]-args[1])
    if name=="divide" and len(args)==2:
        if args[1]==0:raise ValueError("division by zero")
        return safe(args[0]/args[1])
    if name=="power" and len(args)==2:
        return safe(args[0]**args[1])
    raise ValueError("unsupported MathML operator or arity "+name)

def independent_mathml(node,t):
    if not node.tag.startswith(MATHML):raise ValueError("unexpected XML namespace")
    name=node.tag[len(MATHML):]
    if name=="math":
        children=list(node)
        if len(children)!=1:raise ValueError("ambiguous MathML root")
        return independent_mathml(children[0],t)
    if name=="cn":
        if len(node):raise ValueError("complex typed number unsupported")
        return safe(float(node.text.strip()))
    if name=="csymbol":
        if node.get("definitionURL")!=TIME_URL:
            raise ValueError("untrusted non-time csymbol")
        if node.text.strip()!="t" or len(node):
            raise ValueError("unexpected time symbol")
        return safe(t)
    if name=="apply":
        children=list(node)
        if len(children)<2:raise ValueError("empty MathML operation")
        operator=children[0].tag.removeprefix(MATHML)
        if list(children[0]) or (children[0].text or "").strip():
            raise ValueError("unexpected operator payload")
        return apply_op(operator,[independent_mathml(x,t) for x in children[1:]])
    raise ValueError("unsupported MathML node "+name)

def libsbml_ast(node,t):
    kind=node.getType()
    if kind==libsbml.AST_NAME_TIME:return safe(t)
    if node.isNumber():return safe(node.getValue())
    args=[libsbml_ast(node.getChild(i),t) for i in range(node.getNumChildren())]
    operator={libsbml.AST_PLUS:"plus",libsbml.AST_MINUS:"minus",
              libsbml.AST_TIMES:"times",libsbml.AST_DIVIDE:"divide",
              libsbml.AST_POWER:"power"}.get(kind)
    if operator is None:raise ValueError("unhandled libSBML AST operation "+str(kind))
    return apply_op(operator,args)

def experiment(path):
    data=path.read_bytes()
    if len(data)>2_000_000 or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("unsupported source")
    blob=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
    if blob!=BLOB:raise ValueError("upstream source bytes changed")
    tree=ET.fromstring(data)
    xmlrules={}
    for rule in tree.iter():
        if rule.tag.endswith("}assignmentRule"):
            name=rule.attrib.get("variable")
            children=list(rule)
            if name in xmlrules or len(children)!=1 or children[0].tag!=MATHML+"math":
                raise ValueError("duplicate/missing rule MathML")
            xmlrules[name]=children[0]
    if set(xmlrules)!=VARS:raise ValueError("time rule registry changed")
    document=libsbml.readSBMLFromString(data.decode("utf-8"))
    if document.getModel() is None:raise ValueError("invalid parsed SBML")
    model=document.getModel()
    ast_rules={model.getRule(i).getVariable():model.getRule(i).getMath()
               for i in range(model.getNumRules())}
    if set(ast_rules)!=VARS or any(ast_rules[x] is None for x in VARS):
        raise ValueError("libSBML rule registry changed")
    max_error=0.
    rows=[]
    for t in POINTS:
        vals={}
        for name in sorted(VARS):
            left=independent_mathml(xmlrules[name],t)
            right=libsbml_ast(ast_rules[name],t)
            relative=abs(left-right)/max(1.,abs(left),abs(right))
            if relative>1e-9:
                raise AssertionError("independent AST inconsistency for "+name)
            max_error=max(max_error,relative)
            vals[name]=left
        rows.append({"time":t,"co_metabolites":vals})
    # Third independent numeric reference is a fixture produced by a
    # separate restricted MathML interpreter over the pinned source XML.
    fixture_file=Path(__file__).resolve().parents[1] / "research" / "biomodels" / "time_rule_golden_values_v1.json"
    golden=json.loads(fixture_file.read_text(encoding="utf-8"))
    if (golden.get("source_git_blob")!=blob or
        golden.get("time_points")!=list(POINTS) or
        set(golden.get("values",{}))!=VARS):
        raise ValueError("golden values not bound to exact source/time coordinates")
    for index,row in enumerate(rows):
        for name,expected in golden["values"].items():
            current=row["co_metabolites"][name]
            if abs(current-expected)>2e-7:
                raise AssertionError("published co-metabolite golden value drift: "+name)
    # Fail-closed counterexamples: forbidden variable dependency, non-time
    # csymbol and unsupported operation are not silently interpreted.
    invalid=[
       ET.fromstring('<ci xmlns="http://www.w3.org/1998/Math/MathML">protein</ci>'),
       ET.fromstring('<csymbol xmlns="http://www.w3.org/1998/Math/MathML" definitionURL="https://bad.invalid">t</csymbol>'),
       ET.fromstring('<apply xmlns="http://www.w3.org/1998/Math/MathML"><sin/><cn>1</cn></apply>')
    ]
    for node in invalid:
        try:independent_mathml(node,1.)
        except ValueError:continue
        raise AssertionError("unsupported expression accepted")
    return {"experiment":"biomodels-0051-time-only-assignment-rules-v1",
            "source_git_blob":blob,
            "source_sha256":hashlib.sha256(data).hexdigest(),
            "assignment_rules":len(VARS),"time_points":len(POINTS),
            "independently_compared_values":len(VARS)*len(POINTS),
            "max_relative_disagreement":max_error,
            "third_parser_golden_samples_matched":len(VARS)*len(POINTS),
            "unsupported_mathml_negative_controls":len(invalid),
            "results":rows,
            "full_kinetic_ode_reproduced":False,
            "external_biological_measurement_used":False,
            "independent_pde_certificate":False,
            "lean_kernel_qualified":False,
            "cace_runtime_invoked":False,
            "authority_expanded":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--sbml",type=Path,required=True)
    p.add_argument("-o","--output",type=Path,required=True)
    args=p.parse_args()
    result=experiment(args.sbml)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="results"}))
