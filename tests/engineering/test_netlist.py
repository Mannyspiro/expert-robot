import unittest

from python.merlin.engineering.netlist import (
    Component, Connection, Net, Netlist, validate_netlist
)


class NetlistIRTests(unittest.TestCase):
    def test_valid_low_voltage_netlist(self):
        spec = Netlist(
            components=(
                Component("supply", ("vout", "gnd"), (("vout", "supply"), ("gnd", "ground")), 12.0, 2.0),
                Component("load", ("vin", "gnd"), (("vin", "input"), ("gnd", "ground")), 12.0, 1.0),
            ),
            nets=(
                Net("positive", (Connection("supply", "vout"), Connection("load", "vin")), 5.0, 0.5),
                Net("return", (Connection("supply", "gnd"), Connection("load", "gnd"))),
            ),
        )
        self.assertEqual(validate_netlist(spec), [])

    def test_supply_ground_short_is_flagged(self):
        spec = Netlist(
            components=(
                Component("supply", ("vout", "gnd"), (("vout", "supply"), ("gnd", "ground")), 12.0, 2.0),
                Component("load", ("vin", "gnd")),
            ),
            nets=(Net("short", (Connection("supply", "vout"), Connection("supply", "gnd"))),),
        )
        self.assertIn("net.supply_ground_short", {i.code for i in validate_netlist(spec)})

    def test_component_rating_is_checked(self):
        spec = Netlist(
            components=(Component("small", ("a", "b"), max_voltage_v=3.3, max_current_a=0.2), Component("load", ("a", "b"))),
            nets=(Net("n", (Connection("small", "a"), Connection("load", "a")), 5.0, 0.5),),
        )
        codes = {i.code for i in validate_netlist(spec)}
        self.assertIn("rating.voltage_exceeded", codes)
        self.assertIn("rating.current_exceeded", codes)

    def test_pin_cannot_be_assigned_to_two_nets(self):
        spec = Netlist(
            components=(Component("x", ("a", "b")), Component("y", ("a", "b"))),
            nets=(
                Net("one", (Connection("x", "a"), Connection("y", "a"))),
                Net("two", (Connection("x", "a"), Connection("y", "b"))),
            ),
        )
        self.assertIn("pin.multiple_nets", {i.code for i in validate_netlist(spec)})


if __name__ == "__main__":
    unittest.main()
