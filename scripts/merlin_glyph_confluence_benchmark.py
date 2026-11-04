"""Deterministic Avrea benchmark for XMG-1E critical-pair exploration."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Running a file under scripts/ sets sys.path[0] to that directory rather
# than the repository root. Add the project root so the merlin package is
# importable both in CI and from an arbitrary working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from merlin.glyph_foundry import Expr, TypeRef, build_default_registry
from merlin.glyph_normalizer import GlyphNormalizer, RewriteRule
from merlin.glyph_confluence import CriticalPairExplorer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/merlin-xmg1e-confluence.json")
    args = parser.parse_args()
    registry = build_default_registry()
    neg = registry.primitive_expr("NEGATE_INT")
    double_neg = Expr("compose", (neg, neg), TypeRef("Int"), TypeRef("Int"))
    identity = registry.identity(TypeRef("Int"))
    fork_rules = (
        RewriteRule("CONTROL_TO_ID", "synthetic positive-control branch to identity",
                    lambda e: e == double_neg, lambda e, r: identity),
        RewriteRule("CONTROL_TO_NEG", "synthetic positive-control branch to negation",
                    lambda e: e == double_neg, lambda e, r: neg),
    )
    control = CriticalPairExplorer(registry, fork_rules).analyze_expression(double_neg)
    if control.non_joinable_count != 1 or control.unresolved_count:
        raise SystemExit("XMG-1E failed its deliberately divergent positive control.")
    default_rules = GlyphNormalizer(registry).rules
    nested = Expr("compose", (registry.primitive_expr("ABS_INT"), double_neg),
                  TypeRef("Int"), TypeRef("Nat"))
    default_report = CriticalPairExplorer(registry, default_rules).analyze_expression(nested)
    payload = {
        "schema_version": 1,
        "engine": "Merlin XMG-1E",
        "execution": "deterministic-positive-control-and-default-rule-probe",
        "promotion": "disabled",
        "positive_control": {
            "purpose": "verify detection of a known divergent rewrite fork",
            "rule_ids": list(control.rule_ids),
            "pair_count": control.pair_count,
            "non_joinable_count": control.non_joinable_count,
            "unresolved_count": control.unresolved_count,
            "result": control.results[0].status.value,
            "source_fingerprint": control.results[0].source_fingerprint,
            "left_normal_form": control.results[0].left_normal_form,
            "right_normal_form": control.results[0].right_normal_form,
        },
        "default_rule_probe": {
            "rule_ids": list(default_report.rule_ids),
            "expression_count": default_report.expression_count,
            "pair_count": default_report.pair_count,
            "joinable_count": default_report.joinable_count,
            "non_joinable_count": default_report.non_joinable_count,
            "unresolved_count": default_report.unresolved_count,
            "truncated": default_report.truncated,
        },
        "interpretation": (
            "The positive control validates detection of a constructed divergence. "
            "It is not evidence that the default rewrite set is confluent. "
            "The default probe is scoped to the one recorded expression."
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
