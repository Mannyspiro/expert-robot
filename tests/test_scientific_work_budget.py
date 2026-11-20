import itertools
import json
from pathlib import Path
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from merlin import scientific_loop as loop


class ScientificWorkBudgetTest(unittest.TestCase):
    def setUp(self):
        # The cheapest pair occurs outside the prefix; partial ranks are genuinely different.
        self.primitives = [{"id": f"p{i:02}", "domain": f"d{i}", "estimated_cost": 12-i} for i in range(12)]
        self.pairs = {frozenset((a["id"], b["id"])) for a, b in itertools.combinations(self.primitives, 2)}
        self.plan = {"trigger": "compute ceiling", "problem": "Which compatible group costs least?", "limit": 1}

    def counted(self, size, **options):
        seen = []
        def instrumented(values, number):
            for group in itertools.combinations(values, number):
                if isinstance(group[0], dict):
                    seen.append(tuple(p["id"] for p in group))
                yield group
        with patch.object(loop, "combinations", instrumented):
            report = loop.enumerate_combination_report(self.primitives, self.pairs, **self.plan, work_budget=size, **options)
        return report, seen

    def test_actual_count_zero_one_seven_full_and_crossing_pair_triple_boundary(self):
        for cap, count in ((0, 0), (1, 1), (7, 7), (67, 67), (286, 286), (500, 286), (None, 286)):
            with self.subTest(cap=cap):
                report, seen = self.counted(cap)
                counts = report["coverage"]
                self.assertEqual(len(seen), count)
                self.assertEqual(counts["examined"], count)
                self.assertEqual(counts["unexamined"], 286-count)
                self.assertEqual(counts["eligible_omitted_by_limit"], max(0, count-1))
                self.assertEqual(counts["search_complete"], count == 286)
                if count == 67:
                    self.assertEqual(seen[-1], ("p00", "p01", "p02"))

    def test_deterministic_prefix_and_complete_legacy_ranking(self):
        partial, seen = self.counted(7)
        self.assertEqual((partial, seen), self.counted(7))
        self.assertEqual(partial["coverage"]["ranking_scope"], "visited_prefix_only")
        self.assertEqual(partial["candidates"][0]["primitive_ids"], ["p00", "p07"])
        full, _ = self.counted(None)
        self.assertEqual(full["coverage"]["ranking_scope"], "whole_input_catalogue")
        self.assertEqual(full["candidates"][0]["primitive_ids"], ["p10", "p11"])
        self.assertEqual(full["candidates"], loop.enumerate_useful_combinations(self.primitives, self.pairs, **self.plan))

    def test_filters_consume_budget_and_ledger_absence_is_local(self):
        known = {frozenset(("p00", "p01"))}
        report, seen = self.counted(1, observed_groups=known, ledger_ref="fixture:ledger-v1", gaps_only=True)
        self.assertEqual(len(seen), 1)
        self.assertEqual(report["candidates"], [])
        self.assertEqual(report["coverage"]["known_groups_filtered"], 1)
        self.assertEqual(report["coverage"]["rejected"], 1)
        report, _ = self.counted(2, observed_groups=known, ledger_ref="fixture:ledger-v1", gaps_only=True)
        self.assertEqual(report["candidates"][0]["ledger_status"], "absent_from_supplied_ledger")
        self.assertEqual(report["candidates"][0]["epistemic_status"], "hypothesis_combination")
        self.pairs.clear()
        report, seen = self.counted(7)
        self.assertEqual(len(seen), 7)
        self.assertEqual(report["coverage"]["rejected"], 7)
        self.assertEqual(report["coverage"]["returned"], 0)

    def test_invalid_budget_or_unnamed_ledger_is_rejected(self):
        for value in (-1, True, 2.5, "7"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.counted(value)
        with self.assertRaises(ValueError): self.counted(1, gaps_only=True)
        with self.assertRaises(ValueError): self.counted(1, observed_groups=set())

    def test_normal_cli_exposes_lacuna_and_analogy_translation_gate(self):
        root = Path(__file__).resolve().parents[1]
        catalogue = {"primitives": self.primitives, "compatible_pairs": [sorted(p) for p in self.pairs],
            "trigger": self.plan["trigger"], "problem": self.plan["problem"],
            "ledger_ref": "fixture:observation-12", "observed_groups": [["p00", "p01"]],
            "analogy": {"analogy": "prefix scan of a catalogue", "invariant_mapping": {"visit": "one group"},
                        "subproblems": ["count inspected groups"]}}
        proc = subprocess.run([sys.executable, str(root / "scripts/merlin/enumerate_idea_space.py"),
            "-", "--work-budget", "7", "--limit", "1", "--gaps-only"], input=json.dumps(catalogue),
            text=True, capture_output=True, cwd=root, env={**os.environ, "PYTHONPATH": str(root/"python")}, check=True)
        result = json.loads(proc.stdout)
        self.assertEqual(result["coverage"]["examined"], 7)
        self.assertEqual(result["coverage"]["known_groups_filtered"], 1)
        self.assertEqual(result["candidates"][0]["ledger_status"], "absent_from_supplied_ledger")
        self.assertIn("mapped invariant", result["analogy"]["translation_back_gate"])


if __name__ == "__main__":
    unittest.main()
