"""Bounded critical-pair exploration for Merlin's typed glyph rewrite systems.

A non-joinable pair is a concrete witness that the explored rewrite system is
not confluent on the supplied expression. Results are scoped to the exact rule
set and expression corpus; they are not universal claims about other systems.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from typing import Iterable

from .glyph_foundry import Expr, GlyphRegistry, TypeMismatch
from .glyph_normalizer import GlyphNormalizer, RewriteRule, RewriteStep


class PairStatus(str, Enum):
    JOINABLE = "joinable"
    NON_JOINABLE = "non_joinable"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class OneStepRewrite:
    rule_id: str
    position: tuple[int, ...]
    expression: Expr


@dataclass(frozen=True)
class CriticalPairResult:
    source_fingerprint: str
    left_rule_id: str
    right_rule_id: str
    left_position: tuple[int, ...]
    right_position: tuple[int, ...]
    left_fingerprint: str
    right_fingerprint: str
    left_normal_form: str | None
    right_normal_form: str | None
    left_complete: bool
    right_complete: bool
    status: PairStatus
    reason: str


@dataclass(frozen=True)
class ConfluenceReport:
    rule_ids: tuple[str, ...]
    expression_count: int
    pair_count: int
    joinable_count: int
    non_joinable_count: int
    unresolved_count: int
    truncated: bool
    results: tuple[CriticalPairResult, ...]

    @property
    def has_non_joinable_witness(self) -> bool:
        return self.non_joinable_count > 0

    @property
    def all_explored_pairs_joinable(self) -> bool:
        return self.pair_count > 0 and not self.truncated and self.unresolved_count == 0 and self.non_joinable_count == 0


def _positions(expression: Expr, prefix: tuple[int, ...] = ()):
    """Yield every expression node in deterministic preorder."""
    yield prefix, expression
    for index, argument in enumerate(expression.args):
        if isinstance(argument, Expr):
            yield from _positions(argument, prefix + (index,))


def _replace_at(expression: Expr, position: tuple[int, ...], rule: RewriteRule,
                registry: GlyphRegistry) -> Expr | None:
    if not position:
        if not rule.matcher(expression):
            return None
        candidate = rule.replacement(expression, registry)
        if (candidate.input_type, candidate.output_type) != (expression.input_type, expression.output_type):
            raise TypeMismatch(f"rewrite {rule.id} changed the expression signature")
        if candidate.node_count() >= expression.node_count():
            return None
        return candidate

    index = position[0]
    if index >= len(expression.args) or not isinstance(expression.args[index], Expr):
        return None
    child = _replace_at(expression.args[index], position[1:], rule, registry)
    if child is None:
        return None
    args = list(expression.args)
    args[index] = child
    return Expr(expression.op, tuple(args), expression.input_type, expression.output_type)


def one_step_rewrites(expression: Expr, registry: GlyphRegistry,
                      rules: tuple[RewriteRule, ...]) -> tuple[OneStepRewrite, ...]:
    """Enumerate every single size-decreasing rewrite at every AST position."""
    found = []
    for position, _node in _positions(expression):
        for rule in rules:
            rewritten = _replace_at(expression, position, rule, registry)
            if rewritten is not None:
                found.append(OneStepRewrite(rule.id, position, rewritten))
    return tuple(found)


def _overlap(left: tuple[int, ...], right: tuple[int, ...]) -> bool:
    """Redexes overlap when one AST position is an ancestor of the other."""
    n = min(len(left), len(right))
    return left[:n] == right[:n]


def _bounded_normal_form(expression: Expr, registry: GlyphRegistry,
                         rules: tuple[RewriteRule, ...], max_steps: int):
    """Normalize with one global rewrite budget and fingerprint memoization.

    Cached traces are charged again when a shared subtree occurs at another
    position, so memoization cannot bypass the global step budget.
    """
    spent = 0
    cache: dict[str, tuple[Expr, tuple[RewriteStep, ...]]] = {}

    def visit(node: Expr):
        nonlocal spent
        fingerprint = node.fingerprint()
        cached = cache.get(fingerprint)
        if cached is not None:
            cached_expression, cached_steps = cached
            if spent + len(cached_steps) > max_steps:
                return node, (), False
            spent += len(cached_steps)
            return cached_expression, cached_steps, True

        args = list(node.args)
        trace: list[RewriteStep] = []
        for index, argument in enumerate(args):
            if isinstance(argument, Expr):
                normalized, child_trace, complete = visit(argument)
                args[index] = normalized
                trace.extend(child_trace)
                if not complete:
                    return Expr(node.op, tuple(args), node.input_type, node.output_type), tuple(trace), False

        current = Expr(node.op, tuple(args), node.input_type, node.output_type)
        for rule in rules:
            if not rule.matcher(current):
                continue
            candidate = rule.replacement(current, registry)
            if (candidate.input_type, candidate.output_type) != (current.input_type, current.output_type):
                raise TypeMismatch(f"rewrite {rule.id} changed the expression signature")
            if candidate.node_count() >= current.node_count():
                continue
            if spent >= max_steps:
                return current, tuple(trace), False
            before = current.fingerprint()
            after = candidate.fingerprint()
            spent += 1
            trace.append(RewriteStep(rule.id, before, after, rule.status, rule.evidence_ref))
            normalized, child_trace, complete = visit(candidate)
            trace.extend(child_trace)
            if not complete:
                return normalized, tuple(trace), False
            cache[fingerprint] = (normalized, tuple(trace))
            return normalized, tuple(trace), True

        cache[fingerprint] = (current, tuple(trace))
        return current, tuple(trace), True

    return visit(expression)


class CriticalPairExplorer:
    """Explore overlapping one-step rewrites and test whether branches rejoin."""

    def __init__(self, registry: GlyphRegistry,
                 rules: tuple[RewriteRule, ...] | None = None):
        self.registry = registry
        self.rules = rules if rules is not None else GlyphNormalizer(registry).rules

    def analyze_expression(self, expression: Expr, max_pairs: int = 1000,
                           max_steps_per_branch: int = 256) -> ConfluenceReport:
        if max_pairs < 1 or max_steps_per_branch < 1:
            raise ValueError("exploration limits must be positive")

        rewrites = one_step_rewrites(expression, self.registry, self.rules)
        results = []
        truncated = False
        for left, right in combinations(rewrites, 2):
            if not _overlap(left.position, right.position):
                continue
            if left.position == right.position and left.rule_id == right.rule_id:
                continue
            if len(results) >= max_pairs:
                truncated = True
                break

            left_nf, left_trace, left_complete = _bounded_normal_form(
                left.expression, self.registry, self.rules, max_steps_per_branch
            )
            right_nf, right_trace, right_complete = _bounded_normal_form(
                right.expression, self.registry, self.rules, max_steps_per_branch
            )
            if not left_complete or not right_complete:
                status = PairStatus.UNRESOLVED
                reason = "one or both branches exhausted the global normalization step budget"
            elif left_nf.fingerprint() == right_nf.fingerprint():
                status = PairStatus.JOINABLE
                reason = "both branches reached the same normal form under the supplied rules"
            else:
                status = PairStatus.NON_JOINABLE
                reason = "both branches reached distinct normal forms under the supplied rules"

            results.append(CriticalPairResult(
                source_fingerprint=expression.fingerprint(),
                left_rule_id=left.rule_id,
                right_rule_id=right.rule_id,
                left_position=left.position,
                right_position=right.position,
                left_fingerprint=left.expression.fingerprint(),
                right_fingerprint=right.expression.fingerprint(),
                left_normal_form=left_nf.fingerprint() if left_complete else None,
                right_normal_form=right_nf.fingerprint() if right_complete else None,
                left_complete=left_complete,
                right_complete=right_complete,
                status=status,
                reason=reason,
            ))

        counts = {status: sum(result.status == status for result in results) for status in PairStatus}
        return ConfluenceReport(
            rule_ids=tuple(rule.id for rule in self.rules),
            expression_count=1,
            pair_count=len(results),
            joinable_count=counts[PairStatus.JOINABLE],
            non_joinable_count=counts[PairStatus.NON_JOINABLE],
            unresolved_count=counts[PairStatus.UNRESOLVED],
            truncated=truncated,
            results=tuple(results),
        )

    def analyze(self, expressions: Iterable[Expr], max_pairs: int = 5000,
                max_steps_per_branch: int = 256) -> ConfluenceReport:
        if max_pairs < 1:
            raise ValueError("max_pairs must be positive")
        all_results = []
        expression_count = 0
        truncated = False
        for expression in expressions:
            expression_count += 1
            remaining = max_pairs - len(all_results)
            if remaining <= 0:
                truncated = True
                break
            report = self.analyze_expression(
                expression, max_pairs=remaining,
                max_steps_per_branch=max_steps_per_branch,
            )
            all_results.extend(report.results)
            if report.truncated:
                truncated = True
                break

        counts = {status: sum(result.status == status for result in all_results) for status in PairStatus}
        return ConfluenceReport(
            rule_ids=tuple(rule.id for rule in self.rules),
            expression_count=expression_count,
            pair_count=len(all_results),
            joinable_count=counts[PairStatus.JOINABLE],
            non_joinable_count=counts[PairStatus.NON_JOINABLE],
            unresolved_count=counts[PairStatus.UNRESOLVED],
            truncated=truncated,
            results=tuple(all_results),
        )
