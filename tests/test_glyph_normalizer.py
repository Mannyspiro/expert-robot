import unittest
from merlin.glyph_foundry import TypeRef, build_default_registry
from merlin.glyph_normalizer import GlyphNormalizer, RewriteRule, RewriteStatus

class GlyphNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.registry=build_default_registry()
        self.normalizer=GlyphNormalizer(self.registry)
    def test_double_negation_reduces_to_identity(self):
        n=self.registry.primitive_expr("NEGATE_INT")
        e=self.registry.compose(n,n)
        result=self.normalizer.normalize(e)
        self.assertTrue(result.complete)
        self.assertEqual(result.expression,self.registry.identity(TypeRef("Int")))
        self.assertEqual(result.steps[0].rule_id,"INT_DOUBLE_NEGATION")
    def test_abs_after_negation_reduces_to_abs(self):
        n=self.registry.primitive_expr("NEGATE_INT")
        a=self.registry.primitive_expr("ABS_INT")
        e=self.registry.compose(a,n)
        result=self.normalizer.normalize(e)
        self.assertEqual(result.expression,a)
        for x in range(-20,21):
            self.assertEqual(e.evaluate(x,self.registry),result.expression.evaluate(x,self.registry))
    def test_pair_projection_reduces_to_component(self):
        n=self.registry.primitive_expr("NEGATE_INT")
        i=self.registry.primitive_expr("IDENTITY_INT")
        p=self.registry.pair(n,i)
        self.assertEqual(self.normalizer.normalize(self.registry.project(p,0)).expression,n)
        self.assertEqual(self.normalizer.normalize(self.registry.project(p,1)).expression,i)
    def test_normal_form_comparison_is_scoped(self):
        n=self.registry.primitive_expr("NEGATE_INT")
        a=self.registry.primitive_expr("ABS_INT")
        result=self.normalizer.compare(self.registry.compose(a,n),a)
        self.assertTrue(result["same_normal_form"])
        self.assertEqual(result["claim"],"candidate_equivalent_under_rewrite_set")
    def test_candidate_rule_is_not_mislabeled_as_proof(self):
        n=self.registry.primitive_expr("NEGATE_INT")
        result=self.normalizer.normalize(self.registry.compose(n,n))
        self.assertEqual(result.steps[0].status,RewriteStatus.CANDIDATE)
        self.assertIsNone(result.steps[0].evidence_ref)
    def test_rewrite_cannot_change_signature(self):
        n=self.registry.primitive_expr("NEGATE_INT")
        bad=RewriteRule("BAD","bad signature",lambda e:e.op=="compose",
                        lambda e,r:r.primitive_expr("ABS_INT"))
        normalizer=GlyphNormalizer(self.registry,(bad,))
        with self.assertRaises(Exception): normalizer.normalize(self.registry.compose(n,n))
    def test_no_unbounded_rewrite_loop(self):
        n=self.registry.primitive_expr("NEGATE_INT")
        result=self.normalizer.normalize(self.registry.compose(n,n),max_steps=1)
        self.assertTrue(result.complete)

if __name__=="__main__": unittest.main()
