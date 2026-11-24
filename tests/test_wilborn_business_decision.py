import unittest
from wilborn_ops.business_decision import sensitivity,rank_opportunities,implementation_plan
def assumptions(n):
    return dict(monthly_customers=n,price="100",variable_cost="25",fixed_cost="800")
class DecisionTests(unittest.TestCase):
    def test_scenarios_and_plan(self):
        a=dict(pessimistic=assumptions(5),baseline=assumptions(20),optimistic=assumptions(30))
        r=sensitivity(**a)
        self.assertEqual(r["downside_loss"],"425")
        self.assertEqual(r["profit_range"],"1875")
        ranked=rank_opportunities([dict(name="fictional service",evidence_hashes=["a"*64],assumptions=a)])
        self.assertFalse(ranked[0]["evidence_verified"])
        self.assertFalse(implementation_plan(ranked[0])["budget_approved"])
        with self.assertRaises(ValueError):
            rank_opportunities([dict(name="fictional service",evidence_hashes=[],assumptions=a)])
    def test_reversed_scenarios(self):
        with self.assertRaises(ValueError):
            sensitivity(assumptions(30),assumptions(20),assumptions(5))
