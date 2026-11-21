"""Exact solver invariants and full ideal-circuit controls; no physical claims."""
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
import random
import unittest
from unittest.mock import patch

from merlin.engineering_ir import EngineeringProject, Net, Part, Pin
from dot_ai_os import simulation_research as dc


SOURCE = "4b1d5e75916570e0a2d37cc2371b3dc27339ad9a"


def circuit(edges, *, source_voltage="5", measured="OUT"):
    pins = (Pin("1", "one"), Pin("2", "two"))
    parts = [Part("V1", "Ideal source", pins)]
    endpoints = {"VIN": ["V1.1"], "GND": ["V1.2"]}
    specs = {"V1": {"kind": "V", "value": source_voltage}}
    for index, (left, right, resistance) in enumerate(edges, 1):
        ref = f"R{index}"
        parts.append(Part(ref, "Ideal resistor", pins))
        endpoints.setdefault(left, []).append(ref + ".1")
        endpoints.setdefault(right, []).append(ref + ".2")
        specs[ref] = {"kind": "R", "value": resistance}
    project = EngineeringProject("Bounded exact circuit", "mm", tuple(parts),
        tuple(Net(node, tuple(pins)) for node, pins in sorted(endpoints.items())))
    base = dc.CircuitCandidate("baseline", specs)
    alternative = dc.CircuitCandidate("identical", deepcopy(specs))
    objective = dc.CircuitObjective("GND", measured, "2.5", "12", "1")
    return project, base, alternative, objective


def compare(fixture):
    project, base, alternative, objective = fixture
    return dc.compare_virtual_circuits(project, base, (alternative,), objective, source_commit=SOURCE)


def independent_edge_checks(test, observation, edges, source_voltage):
    """Recompute KCL and power directly from edge voltages, not solver rows."""
    volts = {node: Fraction(value) for node, value in observation["node_voltage_v"].items()}
    test.assertEqual(volts["VIN"], Fraction(source_voltage))
    test.assertEqual(volts["GND"], 0)
    balances = {node: Fraction(0) for node in volts}
    power = Fraction(0)
    for index, (left, right, resistance) in enumerate(edges, 1):
        current = (volts[left] - volts[right]) / Fraction(resistance)
        test.assertEqual(Fraction(observation["branch_current_a_declared_pin_order"][f"R{index}"]), current)
        balances[left] += current
        balances[right] -= current
        dissipation = current * (volts[left] - volts[right])
        test.assertEqual(Fraction(observation["resistor_power_w"][f"R{index}"]), dissipation)
        power += dissipation
    for node in balances.keys() - {"VIN", "GND"}:
        test.assertEqual(balances[node], 0, node)
    source_current = Fraction(observation["branch_current_a_declared_pin_order"]["V1"])
    test.assertEqual(source_current, -balances["VIN"])
    test.assertEqual(balances["GND"] - source_current, 0)
    test.assertEqual(power, Fraction(observation["total_resistor_power_w"]))
    test.assertEqual(power + Fraction(source_voltage) * source_current, 0)


class CountedFraction(Fraction):
    """Instrument arithmetic cost without a flaky wall-clock assertion."""
    operations = 0

    def _count(self, other, method):
        type(self).operations += 1
        return type(self)(method(self, other))

    def __add__(self, other):
        return self._count(other, Fraction.__add__)

    def __radd__(self, other):
        return self._count(other, Fraction.__radd__)

    def __sub__(self, other):
        return self._count(other, Fraction.__sub__)

    def __rsub__(self, other):
        return self._count(other, Fraction.__rsub__)

    def __mul__(self, other):
        return self._count(other, Fraction.__mul__)

    def __rmul__(self, other):
        return self._count(other, Fraction.__rmul__)

    def __truediv__(self, other):
        return self._count(other, Fraction.__truediv__)

    def __rtruediv__(self, other):
        return self._count(other, Fraction.__rtruediv__)


class VirtualDCSolverTests(unittest.TestCase):
    def assert_solution(self, matrix, right, expected=None):
        before = deepcopy((matrix, right))
        answer = dc._solve(matrix, right)
        self.assertEqual((matrix, right), before)
        self.assertTrue(all(type(value) is Fraction for value in answer))
        self.assertEqual(len(answer), len(right))
        for row, rhs in zip(matrix, right):
            self.assertEqual(sum((a*x for a, x in zip(row, answer)), Fraction(0)), rhs)
        if expected is not None:
            self.assertEqual(answer, expected)
        return answer

    def test_empty_system_preserves_inputs(self):
        self.assert_solution([], [], [])

    def test_single_equation_retains_exact_fraction(self):
        self.assert_solution([[Fraction(3, 7)]], [Fraction(2, 11)], [Fraction(14, 33)])

    def test_pivot_swaps_preserve_solution(self):
        matrix = [[Fraction(0), Fraction(0), Fraction(2)],
                  [Fraction(3), Fraction(4), Fraction(0)],
                  [Fraction(0), Fraction(5), Fraction(6)]]
        expected = [Fraction(2, 7), Fraction(-3, 11), Fraction(5, 13)]
        right = [sum((a*x for a, x in zip(row, expected)), Fraction(0)) for row in matrix]
        self.assert_solution(matrix, right, expected)

    def test_singular_network_error_and_unchanged_inputs(self):
        for matrix, right in [([[0]], [0]), ([[0]], [1]),
                              ([[1, -1], [-1, 1]], [0, 0]),
                              ([[1, 2], [2, 4]], [3, 7])]:
            with self.subTest(matrix=matrix, right=right):
                matrix = [[Fraction(x) for x in row] for row in matrix]
                right = list(map(Fraction, right))
                before = deepcopy((matrix, right))
                with self.assertRaisesRegex(ValueError, "^floating or unconstrained resistor-network component$"):
                    dc._solve(matrix, right)
                self.assertEqual((matrix, right), before)

    def test_seeded_conductance_equations_satisfy_independent_residual(self):
        rng = random.Random(37019)
        for count in (2, 4, 8, 12):
            for repeat in range(6):
                # Symmetric conductance system with an explicit fixed-node shunt.
                # Choose x first; b=A*x independently establishes the exact oracle.
                # This RHS is an algebraic stress case, not a new simulator mode.
                conductance = [[Fraction(0) for _ in range(count)] for _ in range(count)]
                for i in range(count-1):
                    conductance[i][i+1] = conductance[i+1][i] = Fraction(1, rng.randint(100, 1000000))
                extra = 23 - (count-1) - 1
                pairs = [(i, j) for i in range(count) for j in range(i+2, count)]
                rng.shuffle(pairs)
                for i, j in pairs[:extra]:
                    conductance[i][j] = conductance[j][i] = Fraction(1000000, rng.randint(100000001, 1000000000000))
                matrix = [[sum(conductance[i], Fraction(1, 1000) if i == 0 else Fraction(0))
                           if i == j else -conductance[i][j] for j in range(count)] for i in range(count)]
                expected = [Fraction(rng.randint(-100, 100), rng.randint(1, 31)) for _ in range(count)]
                right = [sum((a*x for a, x in zip(row, expected)), Fraction(0)) for row in matrix]
                with self.subTest(count=count, repeat=repeat):
                    self.assert_solution(matrix, right, expected)

    def test_diagonal_network_avoids_zero_fraction_elimination(self):
        count = 12
        matrix = [[CountedFraction(i+1 if i == j else 0) for j in range(count)] for i in range(count)]
        right = [CountedFraction(2*(i+1)) for i in range(count)]
        CountedFraction.operations = 0
        self.assertEqual(dc._solve(matrix, right), [Fraction(2)] * count)
        # Twelve independent equations should need O(n), not O(n^3), arithmetic.
        # The bound permits incidental arithmetic and does not depend on host speed.
        self.assertLessEqual(CountedFraction.operations, 3 * count)

    def test_divider_full_report_and_input_identity(self):
        fixture = circuit([("VIN", "OUT", "1000"), ("OUT", "GND", "1000")])
        project, base, other, objective = fixture
        other.component_specs["R1"]["value"] = "9000"
        other.component_specs["R2"]["value"] = "9000"
        before = deepcopy(tuple(asdict(x) for x in fixture))
        report = compare(fixture)
        self.assertEqual(tuple(asdict(x) for x in fixture), before)
        self.assertEqual(report["selected_for_followup"], "identical")
        for result, resistance, power in zip(report["results"], ("1000", "9000"), ("1/80", "1/720")):
            self.assertEqual(result["node_voltage_v"]["OUT"], "5/2")
            self.assertEqual(result["total_resistor_power_w"], power)
            independent_edge_checks(self, result, [("VIN", "OUT", resistance), ("OUT", "GND", resistance)], "5")
        for field in ("qualification", "promotion_authority", "formal_proof", "physical_safety_certification"):
            self.assertIs(report[field], False)
        self.assertEqual(report["independent_cace_status"], "not_run")

    def test_balanced_bridge_exact_zero_branch(self):
        edges = [("VIN", "OUT", "1000"), ("OUT", "GND", "1000"),
                 ("VIN", "B", "220"), ("B", "GND", "220"), ("OUT", "B", "4700.5")]
        report = compare(circuit(edges))
        for result in report["results"]:
            self.assertEqual(result["node_voltage_v"]["OUT"], "5/2")
            self.assertEqual(result["node_voltage_v"]["B"], "5/2")
            self.assertEqual(result["branch_current_a_declared_pin_order"]["R5"], "0")
            independent_edge_checks(self, result, edges, "5")

    def test_maximum_circuit_has_twelve_exact_unknowns(self):
        path = ["VIN"] + [f"N{i:02}" for i in range(12)] + ["GND"]
        edges = [(left, right, "1000") for left, right in zip(path, path[1:])]
        edges += [("VIN", "GND", "1000")] * 10
        fixture = circuit(edges, measured="N00")
        self.assertEqual(len(fixture[0].parts), dc.MAX_PARTS)
        self.assertEqual(len(fixture[0].nets), dc.MAX_NETS)
        for result in compare(fixture)["results"]:
            for i in range(12):
                self.assertEqual(Fraction(result["node_voltage_v"][f"N{i:02}"]), Fraction(5*(12-i), 13))
            independent_edge_checks(self, result, edges, "5")

    def test_zero_voltage_source_on_asymmetric_network(self):
        edges = [("VIN", "OUT", "100.000001"), ("OUT", "GND", "1000000"),
                 ("OUT", "B", "220"), ("B", "GND", "4700.5"), ("VIN", "B", "1000")]
        for result in compare(circuit(edges, source_voltage="0"))["results"]:
            self.assertEqual(set(result["node_voltage_v"].values()), {"0"})
            self.assertEqual(result["total_resistor_power_w"], "0")
            independent_edge_checks(self, result, edges, "0")

    def test_floating_island_retains_original_error(self):
        edges = [("VIN", "GND", "1000"), ("OUT", "B", "220")]
        with self.assertRaisesRegex(ValueError, "^floating or unconstrained resistor-network component$"):
            compare(circuit(edges))

    def test_source_and_resistance_bounds_fail_before_solver(self):
        for kind, value in (("V", "12.000001"), ("R", "99.999999"), ("R", "1000000.000001"), ("R", "1e3")):
            fixture = circuit([("VIN", "OUT", "1000"), ("OUT", "GND", "1000")])
            for candidate in fixture[1:3]:
                candidate.component_specs["V1" if kind == "V" else "R1"]["value"] = value
            with self.subTest(kind=kind, value=value), patch.object(dc, "_solve") as solver:
                with self.assertRaises(ValueError):
                    compare(fixture)
                solver.assert_not_called()

    def test_unconnected_pin_and_net_part_caps_remain_enforced(self):
        fixture = circuit([("VIN", "OUT", "1000"), ("OUT", "GND", "1000")])
        project, base, other, objective = fixture
        disconnected = replace(project, nets=tuple(replace(net, endpoints=tuple(x for x in net.endpoints if x != "R1.2")) for net in project.nets))
        with self.assertRaises(ValueError):
            compare((disconnected, base, other, objective))
        oversized = circuit([("VIN", "GND", "1000")] * 24, measured="VIN")
        with self.assertRaisesRegex(ValueError, "^bounded explicit component specification objects required$"):
            compare(oversized)
        chain = ["VIN"] + [f"N{i:02}" for i in range(13)] + ["GND"]
        too_many_nets = circuit([(left, right, "1000") for left, right in zip(chain, chain[1:])], measured="N00")
        with self.assertRaisesRegex(ValueError, "2..24 parts and 2..14 nets"):
            compare(too_many_nets)


if __name__ == "__main__":
    unittest.main()
