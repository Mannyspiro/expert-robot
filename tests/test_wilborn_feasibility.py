import unittest
from wilborn_ops.feasibility import scenario
class FeasibilityTests(unittest.TestCase):
    def test_projection(self):
        r=scenario(monthly_customers=20,price="100",variable_cost="25",fixed_cost="800")
        self.assertEqual(r["operating_profit_projected"],"700")
        self.assertEqual(r["break_even_customers"],11)
        self.assertFalse(r["verified_real"])
    def test_no_positive_margin(self):
        self.assertIsNone(scenario(monthly_customers=0,price="10",variable_cost="10",fixed_cost="100")["break_even_customers"])
    def test_invalid_inputs(self):
        for p in ("NaN","Infinity","-1","0.001"):
            with self.assertRaises(ValueError):
                scenario(monthly_customers=1,price=p,variable_cost="0",fixed_cost="0")
