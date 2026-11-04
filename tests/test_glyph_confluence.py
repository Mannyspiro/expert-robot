import unittest

from merlin.glyph_foundry import Expr, TypeRef, build_default_registry
from merlin.glyph_normalizer import GlyphNormalizer, RewriteRule
from merlin.glyph_confluence import CriticalPairExplorer, PairStatus, one_step_rewrites


class GlyphConfluenceTests(unittest.TestCase):
    def setUp(self):
        self.registry = build_default_registry()
        self.neg = self.registry.primitive_expr("NEGATE_INT")
        self.double_negation = Expr(
            "compose", (self.neg, self.neg), TypeRef("Int"), TypeRef("Int")
        )

    def test_two_overlapping_routes_to_identity_are_joinable(self):
        identity = self.registry.identity(TypeRef("Int"))
        rules = (
            RewriteRule("TO_IDENTITY_A", "first route to identity",
                        lambda e: e == self.double_negation, lambda e, r: identity),
            RewriteRule("TO_IDENTITY_B", "second route to identity",
                        lambda e: e == self.double_negation, lambda e, r: identity),
        )
        report = CriticalPairExplorer(self.registry, rules).analyze_expression(
            self.double_negation
        )
        self.assertEqual(report.pair_count, 1)
        self.assertEqual(report.joinable_count, 1)
        self.assertEqual(report.results[0].status, PairStatus.JOINABLE)

    def test_default_double_negation_rule_has_one_redex(self):
        rules = GlyphNormalizer(self.registry).rules
        rewrites = one_step_rewrites(self.double_negation, self.registry, rules)
        self.assertEqual(len(rewrites), 1)
        self.assertEqual(rewrites[0].rule_id, "INT_DOUBLE_NEGATION")

    def test_deliberately_divergent_rules_produce_non_joinable_witness(self):
        identity = self.registry.identity(TypeRef("Int"))
        rules = (
            RewriteRule(
                "TO_IDENTITY", "double negation to identity",
                lambda e: e == self.double_negation,
                lambda e, r: identity,
            ),
            RewriteRule(
                "TO_NEGATION", "double negation to negation",
                lambda e: e == self.double_negation,
                lambda e, r: self.neg,
            ),
        )
        report = CriticalPairExplorer(self.registry, rules).analyze_expression(
            self.double_negation
        )
        self.assertEqual(report.pair_count, 1)
        self.assertEqual(report.non_joinable_count, 1)
        self.assertEqual(report.results[0].status, PairStatus.NON_JOINABLE)
        self.assertNotEqual(report.results[0].left_normal_form,
                            report.results[0].right_normal_form)

    def test_nested_overlapping_redexes_are_found(self):
        rules = GlyphNormalizer(self.registry).rules
        inner = self.double_negation
        outer = Expr("compose", (self.neg, inner), TypeRef("Int"), TypeRef("Int"))
        rewrites = one_step_rewrites(outer, self.registry, rules)
        positions = {(rewrite.rule_id, rewrite.position) for rewrite in rewrites}
        self.assertIn(("INT_DOUBLE_NEGATION", (1,)), positions)

    def test_non_overlapping_redexes_are_not_reported_as_critical_pairs(self):
        # Two double-negation redexes occur in disjoint branches of a pair.
        inner = self.double_negation
        pair = Expr(
            "pair", (inner, inner), TypeRef("Int"),
            self.registry.pair(inner, inner).output_type,
        )
        report = CriticalPairExplorer(self.registry).analyze_expression(pair)
        self.assertEqual(report.pair_count, 0)

    def test_step_budget_is_global_within_each_branch(self):
        # A rewrite at a nested node and one at its parent require two steps.
        abs_expr = self.registry.primitive_expr("ABS_INT")
        nested = Expr(
            "compose", (abs_expr, self.double_negation),
            TypeRef("Int"), TypeRef("Nat"),
        )
        rules = GlyphNormalizer(self.registry).rules
        from merlin.glyph_confluence import _bounded_normal_form
        normalized, _trace, complete = _bounded_normal_form(
            nested, self.registry, rules, max_steps=1
        )
        self.assertFalse(complete)
        self.assertEqual(normalized.output_type, TypeRef("Nat"))


if __name__ == "__main__":
    unittest.main()
