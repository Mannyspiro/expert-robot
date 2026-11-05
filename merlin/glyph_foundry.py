"""Typed, extensible operator-composition engine for Merlin."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from itertools import product
from typing import Any, Callable, Iterator, Sequence

class FoundryError(ValueError): pass
class TypeMismatch(FoundryError): pass
class PromotionError(FoundryError): pass
class EvidenceState(str, Enum):
    PROPOSED="proposed"; TESTED="tested"; FORMALLY_PROVED="formally_proved"
    INDEPENDENTLY_REVIEWED="independently_reviewed"; PROMOTED="promoted"; REJECTED="rejected"

@dataclass(frozen=True, order=True)
class TypeRef:
    name: str
    parameters: tuple["TypeRef", ...] = ()
    def __str__(self):
        return self.name if not self.parameters else f"{self.name}[{', '.join(map(str,self.parameters))}]"

BOOL=TypeRef("Bool")
def product_type(a,b): return TypeRef("Product",(a,b))

@dataclass(frozen=True)
class Primitive:
    id:str; glyph:str; input_type:TypeRef; output_type:TypeRef
    evaluator:Callable[[Any],Any]=field(compare=False,repr=False)
    description:str=""
    def apply(self,x): return self.evaluator(x)

@dataclass(frozen=True)
class Predicate:
    id:str; type_ref:TypeRef
    check:Callable[[Any],bool]=field(compare=False,repr=False)

@dataclass(frozen=True)
class Expr:
    op:str; args:tuple[Any,...]; input_type:TypeRef; output_type:TypeRef
    def canonical(self):
        def c(x): return x.canonical() if isinstance(x,Expr) else x
        return (self.op,tuple(c(x) for x in self.args),str(self.input_type),str(self.output_type))
    def fingerprint(self):
        import hashlib,json
        raw=json.dumps(self.canonical(),separators=(",",":"),default=str)
        return hashlib.sha256(raw.encode()).hexdigest()
    def depth(self): return 1+max((x.depth() for x in self.args if isinstance(x,Expr)),default=0)
    def node_count(self): return 1+sum(x.node_count() for x in self.args if isinstance(x,Expr))
    def evaluate(self,value,registry):
        if self.op=="identity": return value
        if self.op=="primitive": return registry.primitives[self.args[0]].apply(value)
        if self.op=="compose":
            outer,inner=self.args
            return outer.evaluate(inner.evaluate(value,registry),registry)
        if self.op=="pair":
            a,b=self.args
            return (a.evaluate(value,registry),b.evaluate(value,registry))
        if self.op=="project":
            inner,index=self.args
            return inner.evaluate(value,registry)[index]
        if self.op=="equal":
            a,b=self.args
            return a.evaluate(value,registry)==b.evaluate(value,registry)
        if self.op=="constrain":
            inner,pid=self.args; result=inner.evaluate(value,registry)
            if not registry.predicates[pid].check(result): raise FoundryError(f"constraint failed: {pid}")
            return result
        raise FoundryError(f"unknown AST operation: {self.op}")


class ExprArena:
    """Bounded hash-consing arena that shares structurally identical Expr nodes.

    The arena is opt-in: existing tree-based callers keep their current
    behavior. Interning preserves operator IDs, argument order, and exact
    input/output types. The capacity is a hard bound on unique resident nodes.
    """

    def __init__(self, max_nodes: int = 100_000):
        if isinstance(max_nodes, bool) or not isinstance(max_nodes, int) or max_nodes < 1:
            raise FoundryError("max_nodes must be a positive integer")
        self.max_nodes = max_nodes
        self._nodes: dict[str, Expr] = {}

    @property
    def unique_node_count(self) -> int:
        return len(self._nodes)

    def intern(self, expression: Expr) -> Expr:
        if not isinstance(expression, Expr):
            raise FoundryError("only Expr nodes can be interned")
        args = tuple(
            self.intern(value) if isinstance(value, Expr) else value
            for value in expression.args
        )
        canonical = Expr(
            expression.op, args, expression.input_type, expression.output_type
        )
        fingerprint = canonical.fingerprint()
        existing = self._nodes.get(fingerprint)
        if existing is not None:
            if existing.canonical() != canonical.canonical():
                raise FoundryError("expression fingerprint collision")
            return existing
        if len(self._nodes) >= self.max_nodes:
            raise FoundryError("expression arena node budget exhausted")
        self._nodes[fingerprint] = canonical
        return canonical

    def stats(self, expression: Expr) -> dict[str, float | int]:
        """Count expanded tree occurrences versus unique reachable DAG nodes."""
        occurrence_nodes = 0
        reachable: set[str] = set()

        def visit(node: Expr) -> None:
            nonlocal occurrence_nodes
            occurrence_nodes += 1
            reachable.add(node.fingerprint())
            for child in node.args:
                if isinstance(child, Expr):
                    visit(child)

        visit(expression)
        unique_nodes = len(reachable)
        return {
            "occurrence_nodes": occurrence_nodes,
            "unique_nodes": unique_nodes,
            "shared_occurrences": occurrence_nodes - unique_nodes,
            "sharing_ratio": (
                (occurrence_nodes - unique_nodes) / occurrence_nodes
                if occurrence_nodes else 0.0
            ),
            "arena_resident_nodes": self.unique_node_count,
        }

class GlyphRegistry:
    def __init__(self): self.primitives={}; self.predicates={}; self.promoted={}
    def register_primitive(self,p):
        if p.id in self.primitives: raise FoundryError(f"duplicate primitive: {p.id}")
        self.primitives[p.id]=p
    def register_predicate(self,p):
        if p.id in self.predicates: raise FoundryError(f"duplicate predicate: {p.id}")
        self.predicates[p.id]=p
    def primitive_expr(self,pid):
        p=self.primitives[pid]
        return Expr("primitive",(pid,),p.input_type,p.output_type)
    def identity(self,t): return Expr("identity",(),t,t)
    def compose(self,outer,inner):
        if inner.output_type!=outer.input_type: raise TypeMismatch(f"cannot compose {inner.output_type} -> {outer.input_type}")
        if inner.op=="identity": return outer
        if outer.op=="identity": return inner
        return Expr("compose",(outer,inner),inner.input_type,outer.output_type)
    def pair(self,a,b):
        if a.input_type!=b.input_type: raise TypeMismatch("PAIR requires equal input types")
        return Expr("pair",(a,b),a.input_type,product_type(a.output_type,b.output_type))
    def project(self,e,index):
        if e.output_type.name!="Product" or len(e.output_type.parameters)!=2: raise TypeMismatch("PROJECT requires Product")
        if index not in (0,1): raise FoundryError("projection index must be 0 or 1")
        return Expr("project",(e,index),e.input_type,e.output_type.parameters[index])
    def equal(self,a,b):
        if (a.input_type,a.output_type)!=(b.input_type,b.output_type): raise TypeMismatch("EQUAL requires matching signatures")
        return Expr("equal",(a,b),a.input_type,BOOL)
    def constrain(self,e,pid):
        p=self.predicates[pid]
        if p.type_ref!=e.output_type: raise TypeMismatch(f"{pid} expects {p.type_ref}, got {e.output_type}")
        return Expr("constrain",(e,pid),e.input_type,e.output_type)

@dataclass
class Candidate:
    id:str; expression:Expr; description:str=""
    state:EvidenceState=EvidenceState.PROPOSED
    test_receipts:list[str]=field(default_factory=list)
    proof_receipt:str|None=None
    independent_review_receipt:str|None=None
    measured_value:float|None=None
    baseline_value:float|None=None
    higher_is_better:bool=True
    min_relative_gain:float=0.0
    value_receipt:str|None=None
    @property
    def fingerprint(self): return self.expression.fingerprint()

class GlyphFoundry:
    """Finite resumable slices of a potentially unbounded typed composition space."""
    def __init__(self,registry,evidence_verifier=None):
        self.registry=registry
        self.evidence_verifier=evidence_verifier
        self._seen=set()
    def seed_expressions(self): return [self.registry.primitive_expr(k) for k in sorted(self.registry.primitives)]
    def enumerate_compositions(self,max_depth=4,max_nodes=12,max_candidates=1000)->Iterator[Expr]:
        if min(max_depth,max_nodes,max_candidates)<1: raise FoundryError("limits must be positive")
        pool=self.seed_expressions(); emitted=0
        for e in pool:
            fp=e.fingerprint()
            if e.node_count()<=max_nodes and fp not in self._seen:
                self._seen.add(fp); yield e; emitted+=1
                if emitted>=max_candidates:return
        # Compose every pair whose maximum child depth is the preceding layer.
        # Rebuild prior layers on each bounded slice; the persistent seen-set
        # suppresses repeats while retaining all expressions for later layers.
        for layer in range(2,max_depth+1):
            layer_items=[]
            for inner,outer in product(pool,pool):
                if max(inner.depth(),outer.depth()) != layer-1: continue
                if inner.output_type != outer.input_type: continue
                e=self.registry.compose(outer,inner)
                if e.depth()>max_depth or e.node_count()>max_nodes: continue
                fp=e.fingerprint()
                layer_items.append(e)
                if fp in self._seen: continue
                self._seen.add(fp); yield e; emitted+=1
                if emitted>=max_candidates:return
            known={x.fingerprint() for x in pool}
            pool.extend(x for x in layer_items if x.fingerprint() not in known)
    def propose(self,e,description=""): return Candidate(e.fingerprint()[:16],e,description)
    def record_tests(self,c,receipts:Sequence[str]):
        if not receipts or any(not x.strip() for x in receipts): raise PromotionError("test receipts required")
        c.test_receipts.extend(receipts); c.state=EvidenceState.TESTED
    def record_proof(self,c,receipt):
        if not receipt.strip(): raise PromotionError("proof receipt required")
        c.proof_receipt=receipt; c.state=EvidenceState.FORMALLY_PROVED
    def record_independent_review(self,c,receipt):
        if not receipt.strip(): raise PromotionError("independent review receipt required")
        c.independent_review_receipt=receipt; c.state=EvidenceState.INDEPENDENTLY_REVIEWED
    def record_value(self,c,measured,baseline,receipt,min_relative_gain=0.0,higher_is_better=True):
        import math
        if not receipt.strip(): raise PromotionError("benchmark receipt required")
        if not math.isfinite(float(measured)) or not math.isfinite(float(baseline)):
            raise PromotionError("benchmark values must be finite")
        if not math.isfinite(float(min_relative_gain)) or float(min_relative_gain)<0:
            raise PromotionError("minimum relative gain must be finite and nonnegative")
        c.measured_value=float(measured); c.baseline_value=float(baseline)
        c.value_receipt=receipt; c.min_relative_gain=float(min_relative_gain); c.higher_is_better=higher_is_better
    def _demonstrates_value(self,c):
        if c.measured_value is None or c.baseline_value is None or c.value_receipt is None:return False
        delta=c.measured_value-c.baseline_value if c.higher_is_better else c.baseline_value-c.measured_value
        scale=abs(c.baseline_value); gain=delta/scale if scale else delta
        return gain>0 and gain>=c.min_relative_gain
    def promote(self,c,require_proof=True):
        if not c.test_receipts: raise PromotionError("promotion requires tests")
        if require_proof and not c.proof_receipt: raise PromotionError("promotion requires formal proof receipt")
        if not c.independent_review_receipt: raise PromotionError("promotion requires independent review")
        if not self._demonstrates_value(c): raise PromotionError("promotion requires benchmark improvement over baseline")
        if self.evidence_verifier is None:
            raise PromotionError("no trusted evidence verifier configured; receipt strings are not self-authenticating")
        subject=c.fingerprint
        required=[("test",r) for r in c.test_receipts]
        if require_proof: required.append(("formal_proof",c.proof_receipt))
        required.extend([("independent_review",c.independent_review_receipt),("benchmark",c.value_receipt)])
        if not all(self.evidence_verifier(kind,receipt,subject) for kind,receipt in required):
            raise PromotionError("one or more evidence receipts failed independent verification")
        self.registry.promoted[c.id]=c; c.state=EvidenceState.PROMOTED

def build_default_registry():
    r=GlyphRegistry()
    r.register_primitive(Primitive("IDENTITY_INT","◉",TypeRef("Int"),TypeRef("Int"),lambda x:x,"integer identity"))
    r.register_primitive(Primitive("NEGATE_INT","⊖",TypeRef("Int"),TypeRef("Int"),lambda x:-x,"integer negation"))
    r.register_primitive(Primitive("ABS_INT","|x|",TypeRef("Int"),TypeRef("Nat"),abs,"absolute value"))
    r.register_primitive(Primitive("INT_TO_FLOAT","↦",TypeRef("Int"),TypeRef("Float"),float,"integer-to-float embedding"))
    r.register_predicate(Predicate("NONNEGATIVE_NAT",TypeRef("Nat"),lambda x:x>=0))
    return r
