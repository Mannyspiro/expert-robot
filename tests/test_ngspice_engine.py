import json
import subprocess
import unittest
from unittest.mock import patch

from merlin.ngspice_engine import run_ngspice, validate_netlist


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

    def test_run_enforces_address_space_limit_with_prlimit(self):
        netlist = "RC operating point\\nV1 in 0 DC 5\\nR1 in 0 1k\\n.op\\n.end\\n"
        def which(name):
            return { "ngspice": "/usr/bin/ngspice", "prlimit": "/usr/bin/prlimit" }.get(name)
        with patch("merlin.ngspice_engine.shutil.which", side_effect=which), \\
             patch("merlin.ngspice_engine.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            result = run_ngspice(netlist, max_memory_bytes=268435456)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["/usr/bin/prlimit", "--as=268435456", "--"])
        payload = json.loads(result["artifact_bytes"])
        self.assertIn("address-space limit enforced by prlimit", payload["resource_note"])

    def test_run_refuses_to_claim_memory_bounded_execution_without_prlimit(self):
        with patch("merlin.ngspice_engine.shutil.which",
                   side_effect=lambda name: "/usr/bin/ngspice" if name == "ngspice" else None):
            with self.assertRaisesRegex(RuntimeError, "prlimit is required"):
                run_ngspice("RC operating point\\nV1 in 0 5\\nR1 in 0 1k\\n.op\\n.end\\n")

    def test_requires_analysis_and_end(self):
        with self.assertRaisesRegex(ValueError, "analysis directive"):
            validate_netlist("No analysis\nR1 in 0 1k\n.end\n")


if __name__ == "__main__":
    unittest.main()
