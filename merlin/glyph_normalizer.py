"""Conservative rewrite and normalization engine for Merlin glyph expressions."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Callable
from .glyph_foundry import Expr, GlyphRegistry, TypeMismatch

class RewriteStatus(str, Enum):
    CANDIDATE = "candidate"
    FINITE_TESTED = "finite_tested"
    FORMALLY_PROVED = "formally_proved"

@dataclass(frozen=True)
class RewriteRule:
    id: str
    description: str
    matcher: Callable[[Expr], bool]
    replacement: Callable[[Expr, GlyphRegistry], Expr]
    status: RewriteStatus = RewriteStatus.CANDIDATE
    evidence_ref: str | None = None

@dataclass(frozen=True)
class RewriteStep:
    rule_id: str
    before_fingerprint: str
    after_fingerprint: str
    status: RewriteStatus
    evidence_ref: str | None

@dataclass(frozen=True)
class NormalizationResult:
    expression: Expr
    steps: tuple[RewriteStep, ...]
    complete: bool
    reason: str

class GlyphNormalizer:
    """Bottom-up, size-decreasing rewrites with explicit evidence labels."""
    def __init__(self, registry: GlyphRegistry, rules: tuple[RewriteRule, ...] | None = None):
        self.registry = registry
        self.rules = rules if rules is not None else self.default_rules()

    @staticmethod
    def _primitive_id(expr: Expr, pid: str) -> bool:
        return expr.op == "primitive" and expr.args == (pid,)

    @classmethod
    def default_rules(cls) -> tuple[RewriteRule, ...]:
        def is_compose(e, outer, inner):
            return (e.op == "compose" and len(e.args) == 2
                    and cls._primitive_id(e.args[0], outer)
                    and cls._primitive_id(e.args[1], inner))
        return (
            RewriteRule("INT_DOUBLE_NEGATION","NEGATE_INT after NEGATE_INT is identity on integers",
                lambda e: is_compose(e,"NEGATE_INT","NEGATE_INT"),
                lambda e,r: r.identity(e.input_type)),
            RewriteRule("INT_ABS_NEGATION","ABS_INT after NEGATE_INT is ABS_INT",
                lambda e: is_compose(e,"ABS_INT","NEGATE_INT"),
                lambda e,r: r.primitive_expr("ABS_INT")),
            RewriteRule("PROJECT_PAIR_LEFT","Left projection of a pair returns its first map",
                lambda e: e.op=="project" and e.args[0].op=="pair" and e.args[1]==0,
                lambda e,r: e.args[0].args[0]),
            RewriteRule("PROJECT_PAIR_RIGHT","Right projection of a pair returns its second map",
                lambda e: e.op=="project" and e.args[0].op=="pair" and e.args[1]==1,
                lambda e,r: e.args[0].args[1]),
            RewriteRule("COMPOSE_IDENTITY_INNER","Composition after identity reduces to the outer map",
                lambda e: e.op=="compose" and e.args[1].op=="identity",
                lambda e,r: e.args[0]),
            RewriteRule("COMPOSE_IDENTITY_OUTER","Identity after composition reduces to the inner map",
                lambda e: e.op=="compose" and e.args[0].op=="identity",
                lambda e,r: e.args[1]),
        )

    def _rebuild(self,e:Expr,max_steps:int)->tuple[Expr,tuple[RewriteStep,...]]:
        a=e.args
        if e.op in ("identity","primitive"): return e,()
        # Rebuild without applying constructor simplifications: every semantic
        # change must be represented by an explicit RewriteStep.
        if e.op=="compose":
            outer_result=self.normalize(a[0],max_steps)
            inner_result=self.normalize(a[1],max_steps)
            outer,inner=outer_result.expression,inner_result.expression
            if inner.output_type!=outer.input_type: raise TypeMismatch("ill-typed compose node")
            return Expr("compose",(outer,inner),e.input_type,e.output_type), outer_result.steps+inner_result.steps
        if e.op=="pair":
            left_result=self.normalize(a[0],max_steps)
            right_result=self.normalize(a[1],max_steps)
            left,right=left_result.expression,right_result.expression
            if left.input_type!=right.input_type: raise TypeMismatch("ill-typed pair node")
            return Expr("pair",(left,right),e.input_type,e.output_type), left_result.steps+right_result.steps
        if e.op=="project":
            inner_result=self.normalize(a[0],max_steps)
            return Expr("project",(inner_result.expression,a[1]),e.input_type,e.output_type),inner_result.steps
        if e.op=="equal":
            left_result=self.normalize(a[0],max_steps)
            right_result=self.normalize(a[1],max_steps)
            left,right=left_result.expression,right_result.expression
            if (left.input_type,left.output_type)!=(right.input_type,right.output_type):
                raise TypeMismatch("ill-typed equality node")
            return Expr("equal",(left,right),e.input_type,e.output_type),left_result.steps+right_result.steps
        if e.op=="constrain":
            inner_result=self.normalize(a[0],max_steps)
            return Expr("constrain",(inner_result.expression,a[1]),e.input_type,e.output_type),inner_result.steps
        raise TypeMismatch(f"normalizer does not understand AST node {e.op!r}")

    def normalize(self,expression:Expr,max_steps:int=256)->NormalizationResult:
        if max_steps<1: raise ValueError("max_steps must be positive")
        current=expression
        steps=[]
        seen={current.fingerprint()}
        for _ in range(max_steps):
            rebuilt,child_steps=self._rebuild(current,max_steps)
            steps.extend(child_steps)
            if rebuilt.fingerprint()!=current.fingerprint():
                current=rebuilt
                seen.add(current.fingerprint())
                continue
            matched=False
            for rule in self.rules:
                if not rule.matcher(current): continue
                candidate=rule.replacement(current,self.registry)
                if candidate.input_type!=current.input_type or candidate.output_type!=current.output_type:
                    raise TypeMismatch(f"rewrite {rule.id} changed the expression signature")
                if candidate.node_count()>=current.node_count(): continue
                fp=candidate.fingerprint()
                if fp in seen: continue
                steps.append(RewriteStep(rule.id,current.fingerprint(),fp,rule.status,rule.evidence_ref))
                current=candidate
                seen.add(fp)
                matched=True
                break
            if not matched:
                return NormalizationResult(current,tuple(steps),True,"normal form reached under current rewrite set")
        return NormalizationResult(current,tuple(steps),False,"step limit reached")

    def compare(self,left:Expr,right:Expr,max_steps:int=256)->dict:
        a=self.normalize(left,max_steps)
        b=self.normalize(right,max_steps)
        same=a.expression.fingerprint()==b.expression.fingerprint()
        return {"same_normal_form":same,
                "claim":"candidate_equivalent_under_rewrite_set" if same else "not_established",
                "left":a.expression.fingerprint(),"right":b.expression.fingerprint(),
                "left_complete":a.complete,"right_complete":b.complete,
                "evidence_status":[s.status.value for s in (*a.steps,*b.steps)]}
