import unittest

from merlin.ngspice_engine import validate_netlist


class NgspiceEngineTests(unittest.TestCase):
    def test_accepts_simple_passive_operating_point_netlist(self):
        netlist = """RC operating point
V1 in 0 DC 5
R1 in out 1k
R2 out 0 1k
.op
.end
"""
        self.assertTrue(validate_netlist(netlist).endswith(".end\n"))

    def test_rejects_shell_control_and_external_file_directives(self):
        for directive in (".control", ".include /tmp/other.cir", ".shell echo unsafe"):
            with self.subTest(directive=directive):
                netlist = "Unsafe netlist\nV1 in 0 5\nR1 in 0 1k\n" + directive + "\n.op\n.end\n"
                with self.assertRaisesRegex(ValueError, "forbidden"):
                    validate_netlist(netlist)

    def test_requires_analysis_and_end(self):
        with self.assertRaisesRegex(ValueError, "analysis directive"):
            validate_netlist("No analysis\nR1 in 0 1k\n.end\n")


if __name__ == "__main__":
    unittest.main()
