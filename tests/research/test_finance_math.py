import math
import unittest

from merlin.finance_math import cagr, discounted_cash_flow, irr, npv, total_return


class FinanceMathTests(unittest.TestCase):
    def test_cagr_known_example(self):
        self.assertAlmostEqual(cagr(100, 121, 2), 0.10, places=12)

    def test_cagr_rejects_nonpositive_values_and_duration(self):
        for args in ((0, 100, 2), (100, -1, 2), (100, 120, 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                cagr(*args)

    def test_total_return(self):
        self.assertAlmostEqual(total_return(80, 100), 0.25)

    def test_npv_includes_time_zero_flow(self):
        self.assertAlmostEqual(npv(0.10, [-100, 60, 60]), 4.1322314049587)

    def test_npv_rejects_invalid_rate_and_empty_flows(self):
        with self.assertRaises(ValueError):
            npv(-1, [-100, 120])
        with self.assertRaises(ValueError):
            npv(0.1, [])

    def test_irr_conventional_cash_flows(self):
        self.assertAlmostEqual(irr([-100, 60, 60]), 0.1306623863, places=8)

    def test_irr_rejects_multiple_sign_changes(self):
        with self.assertRaises(ValueError):
            irr([-100, 230, -132])

    def test_irr_rejects_unbracketed_or_nonconventional_cash_flows(self):
        with self.assertRaises(ValueError):
            irr([100, 20, 10])

    def test_discounted_cash_flow_explicit_and_terminal(self):
        result = discounted_cash_flow([10, 10], 0.10, 100)
        self.assertTrue(math.isclose(result["explicit_cash_flow_pv"], 17.3553719008))
        self.assertTrue(math.isclose(result["terminal_value_pv"], 82.6446280992))
        self.assertTrue(math.isclose(result["total_value"], 100.0))

    def test_discounted_cash_flow_rejects_empty_forecast(self):
        with self.assertRaises(ValueError):
            discounted_cash_flow([], 0.1)


if __name__ == "__main__":
    unittest.main()
