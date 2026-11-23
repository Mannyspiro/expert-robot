"""Typed finite paradox/constraint preflight for Merlin's scientific research.

This classifier is intentionally narrow. It checks Boolean claims only within
their explicitly comparable scope and a few exact representation invariants.
It cannot prove general logical consistency, solve self-reference, establish
new mathematics, or relax security gates.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Sequence

def _name(text, label):
    if not isinstance(text,str) or not 1<=len(text)<=200 or not text.strip():
        raise ValueError(label+" requires bounded nonempty text")
    return text

@dataclass(frozen=True)
class ScopedClaim:
    subject: str
    predicate: str
    truth: bool
    time: str
    domain: str
    units: str
    frame: str = "classical_two_valued"

    def __post_init__(self):
        for k in ("subject","predicate","time","domain","units","frame"):
            _name(getattr(self,k),k)
        if type(self.truth) is not bool:
            raise ValueError("explicit Boolean truth assertion required")

    def key(self):
        return (self.subject,self.predicate,self.time,self.domain,self.units,self.frame)

def assess_claims(left:ScopedClaim, right:ScopedClaim)->dict:
    if not isinstance(left,ScopedClaim) or not isinstance(right,ScopedClaim):
        raise TypeError("typed claims are required")
    same_topic=(left.subject,left.predicate)==(right.subject,right.predicate)
    changed=[k for k in ("time","domain","units","frame") if getattr(left,k)!=getattr(right,k)]
    exact=left.key()==right.key()
    if exact and left.truth!=right.truth and left.frame in ("classical","classical_two_valued"):
        status="contradiction_under_shared_classical_scope"
        witness="same predicate and fully identical classical scope, opposite Boolean assertions"
    elif exact and left.truth!=right.truth:
        status="nonclassical_semantics_not_defined"
        witness="opposed labels require explicit inference and negation semantics"
    elif not exact and same_topic and left.truth!=right.truth:
        status="scope_mismatch_requires_mapping"
        witness="opposite assertions are not comparable without a justified scope mapping"
    else:
        status="no_direct_contradiction_found"
        witness="no opposing Boolean assertions with identical declared scope"
    return {
        "schema":"merlin-scoped-paradox/1",
        "status":status,"witness":witness,
        "different_axes":changed,"same_topic":same_topic,
        "logical_system":left.frame if left.frame==right.frame else "incomparable",
        "logical_resolution_proven":False,
        "factual_premises_verified":False,"production_qualified":False,
    }

def check_simplex(weights:Sequence[float], *, tolerance:float=1e-12)->dict:
    if (not isinstance(weights,(list,tuple)) or not 1<=len(weights)<=32
            or type(tolerance) not in (int,float)
            or not math.isfinite(tolerance) or tolerance<0 or tolerance>1e-6):
        raise ValueError("bounded barycentric weights and tolerance required")
    for w in weights:
        if type(w) not in (int,float) or not math.isfinite(w):
            raise ValueError("finite numeric weight required")
    nonnegative=all(x>=-tolerance for x in weights)
    normalized=abs(sum(weights)-1)<=tolerance
    return {"schema":"merlin-simplex-preflight/1",
            "valid":nonnegative and normalized,
            "nonnegative":nonnegative,"normalized":normalized,
            "weight_sum":sum(weights),
            "affine_independence_proven":False,"production_qualified":False}

def check_continuum_boundary(boundary:Sequence[tuple[str,float]],*, tolerance:float=0.0)->dict:
    """Check finite prescribed point values, not general continuous extension.

    If the same boundary point has incompatible values, there can be no
    single-valued extension satisfying both prescriptions exactly.
    """
    if not isinstance(boundary,(list,tuple)) or not 1<=len(boundary)<=128:
        raise ValueError("bounded boundary conditions required")
    if type(tolerance) not in (int,float) or not math.isfinite(tolerance) or not 0<=tolerance<=1e-6:
        raise ValueError("finite nonnegative boundary tolerance required")
    samples={}
    violations=[]
    for item in boundary:
        if not isinstance(item,(tuple,list)) or len(item)!=2:
            raise ValueError("point/value pairs required")
        key,value=item
        _name(key,"boundary point")
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError("finite boundary value required")
        if key in samples and abs(samples[key]-value)>tolerance:
            violations.append(key)
        else:
            samples.setdefault(key,value)
    return {
        "schema":"merlin-continuum-boundary-preflight/1",
        "status":"incompatible_shared_boundary" if violations else "finite_constraints_consistent",
        "incompatible_points":sorted(set(violations)),
        "continuous_extension_proven":False,
        "uniqueness_proven":False,
        "production_qualified":False
    }

def check_glyph_translation(tokens:Sequence[str], dictionary:dict[str,str])->dict:
    """Finite typed glyph dictionary preflight, not full semantic equivalence."""
    if (not isinstance(tokens,(list,tuple)) or not 1<=len(tokens)<=128
            or not isinstance(dictionary,dict) or not 1<=len(dictionary)<=128):
        raise ValueError("bounded glyph representation required")
    if any(not isinstance(k,str) or not 1<=len(k)<=32 or not isinstance(v,str)
           or not 1<=len(v)<=80 for k,v in dictionary.items()):
        raise ValueError("bounded glyph translation required")
    missing=[k for k in tokens if not isinstance(k,str) or k not in dictionary]
    return {"schema":"merlin-glyph-translation-preflight/1",
            "status":"typed_tokens_present" if not missing else "undefined_tokens",
            "undefined_tokens":missing,
            "semantics_preservation_proven":False,
            "novel_mathematical_system_proven":False,
            "production_qualified":False}
