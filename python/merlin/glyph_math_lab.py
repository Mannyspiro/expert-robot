"""Formal symbolic glyph-math language for Merlin research.

Glyphs are notation tokens with explicit algebraic semantics. They are not
cryptographic keys, entropy sources, or security primitives.
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from typing import Any

GLYPH_SCHEMA = "merlin-glyph-algebra/1"

@dataclass(frozen=True)
class Glyph:
    symbol: str
    name: str
    arity: int
    semantic: str

GLYPHS = (
    Glyph("⟁", "compose", 2, "function composition: f ⟁ g means f after g"),
    Glyph("⌁", "iterate", 2, "iteration: f ⌁ n means n repeated applications of f"),
    Glyph("⟡", "dual", 1, "formal dual marker; requires a domain-specific duality definition"),
    Glyph("⧖", "invariant", 1, "marks a quantity claimed invariant under a declared transformation"),
    Glyph("⫷", "map", 2, "maps an input object through an explicitly named function"),
    Glyph("⟲", "orbit", 2, "describes an orbit under repeated application of a transformation"),
    Glyph("⋈", "combine", 2, "combines two typed objects using a declared operation"),
    Glyph("⧉", "boundary", 1, "marks a domain or boundary condition"),
)

def glyph_grammar() -> dict[str, Any]:
    return {
        "schema": GLYPH_SCHEMA,
        "tokens": [g.__dict__ for g in GLYPHS],
        "typing_rules": [
            "Every expression declares its domain and codomain.",
            "Composition requires the first codomain to equal the next domain.",
            "Iteration requires a non-negative integer count.",
            "Invariant claims require a named transformation and proof obligation.",
            "Duality is undefined until a pairing or dual-space construction is supplied.",
            "Orbit expressions require a start value, transformation and iteration bound.",
        ],
        "safety_boundary": "Glyphs are a mathematical notation and cannot be used as cryptographic entropy, secret keys, or cipher transforms.",
    }

def canonical_glyph_bytes() -> bytes:
    return (json.dumps(glyph_grammar(), ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")

def glyph_grammar_digest() -> str:
    return hashlib.sha256(canonical_glyph_bytes()).hexdigest()

def validate_expression(expression: dict[str, Any]) -> list[str]:
    errors = []
    op = expression.get("op")
    by_name = {g.name: g for g in GLYPHS}
    if op not in by_name:
        return ["unknown glyph operation"]
    glyph = by_name[op]
    args = expression.get("args")
    if not isinstance(args, list) or len(args) != glyph.arity:
        errors.append("wrong argument count for glyph operation")
    if not isinstance(expression.get("domain"), str) or not expression["domain"].strip():
        errors.append("explicit domain required")
    if not isinstance(expression.get("codomain"), str) or not expression["codomain"].strip():
        errors.append("explicit codomain required")
    if op == "iterate" and isinstance(args, list) and len(args) == 2:
        if not isinstance(args[1], int) or args[1] < 0:
            errors.append("iteration count must be a non-negative integer")
    if op == "invariant" and not expression.get("proof_obligation"):
        errors.append("invariant requires a proof obligation")
    if op == "dual" and not expression.get("duality_definition"):
        errors.append("dual operation requires an explicit duality definition")
    return errors

__all__ = ["Glyph", "GLYPHS", "glyph_grammar", "canonical_glyph_bytes",
           "glyph_grammar_digest", "validate_expression"]

def hermes_glyph_math_research_executor(task, context):
    """Emit canonical glyph grammar as a Hermes research artifact."""
    import json
    objective = str(task.get("objective", "")).strip()
    if task.get("stage") != "research" or not any(
        term in objective.lower() for term in ("glyph", "alien mathematics", "symbolic mathematics")
    ):
        raise ValueError("task must be a glyph-mathematics research task")
    grammar = glyph_grammar()
    report = {
        "schema": "merlin-glyph-math-research/1",
        "task_id": context.task_id,
        "hypothesis_id": context.hypothesis_id,
        "objective": objective,
        "grammar": grammar,
        "grammar_sha256": glyph_grammar_digest(),
        "scope": "formal notation and type constraints only; no cryptographic security claim",
        "promotion_authority": False,
    }
    payload = (json.dumps(report, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False) + "\\n").encode("utf-8")
    return {
        "artifact_bytes": payload,
        "media_type": "application/vnd.merlin.glyph-math+json",
        "summary": "Generated typed glyph-mathematics grammar and deterministic identity.",
        "metadata": {
            "artifact_schema": report["schema"],
            "grammar_sha256": report["grammar_sha256"],
            "glyph_count": len(grammar["tokens"]),
            "promotion_authority": False,
        },
    }

__all__.append("hermes_glyph_math_research_executor")
