"""Negative controls for read-only OCI Python 3.11 ABI evidence.

Run using standard library only. Fixtures are synthetic headers and text; no
foreign architecture code is executed and no system library is modified.
"""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "oci_abi_probe", ROOT / "scripts" / "merlin_oci_host_abi_probe.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def arm64_header():
    raw = bytearray(24)
    raw[:4] = b"\x7fELF"
    raw[4] = 2
    raw[5] = 1
    raw[18:20] = (183).to_bytes(2, "little")
    return bytes(raw)


def fake_ldconfig(*pairs):
    return "\n".join(
        "\t%s (libc6,AArch64) => %s" % (lib, path)
        for lib, path in pairs) + "\n"


class AbiEvidenceTests(unittest.TestCase):
    def test_pinned_core_does_not_inherit_optional_crypt(self):
        self.assertEqual(probe.ENTRYPOINT_SHA256,
                         "6cfad927461ace659b09716fad2efa828c6a4b084b7be8181c3982a9f36f464c")
        self.assertNotIn("libcrypt.so.1", probe.REQUIREMENTS)
        self.assertIn("libcrypt.so.1", probe.OPTIONAL)
        self.assertEqual(set(probe.REQUIREMENTS["libc.so.6"]), {"GLIBC_2.17"})

    def test_ldconfig_filters_paths_and_library_names(self):
        raw = fake_ldconfig(
            ("libc.so.6", "/lib/aarch64-linux-gnu/libc.so.6"),
            ("libc.so.6", "/tmp/attacker-libc.so.6"),
            ("libc.so.6", "/lib/../etc/shadow"),
            ("libm.so.6", "/usr/lib/aarch64-linux-gnu/libm.so.6"),
            ("libm.so.60", "/lib/aarch64-linux-gnu/libm.so.6"),
            ("libcrypt.so.1", "/usr/lib/aarch64-linux-gnu/libcrypt.so.1"))
        result = probe.parse_ldconfig(raw)
        self.assertEqual(result["libc.so.6"], ["/lib/aarch64-linux-gnu/libc.so.6"])
        self.assertEqual(result["libm.so.6"], ["/usr/lib/aarch64-linux-gnu/libm.so.6"])
        self.assertEqual(result["libcrypt.so.1"],
                         ["/usr/lib/aarch64-linux-gnu/libcrypt.so.1"])
        self.assertNotIn("libm.so.60", result)

    def test_ldconfig_deduplicates_and_bounds_candidates(self):
        one = "libm.so.6"
        paths = ["/lib/aarch64-linux-gnu/libm%d.so" % i for i in range(30)]
        listing = fake_ldconfig(*[(one, p) for p in paths], (one, paths[0]))
        self.assertEqual(len(probe.parse_ldconfig(listing)[one]), 16)

    def test_ldconfig_rejects_unbounded_stdout(self):
        with self.assertRaises(ValueError):
            probe.parse_ldconfig("x" * (probe.MAX_LDCONFIG_BYTES + 1))

    def test_elf_version_definitions_exclude_version_needs(self):
        output = """Version definition section '.gnu.version_d' contains 3 entries:
  0x001c: Rev: 1  Name: GLIBC_2.17
  0x002c: Rev: 1  Name: GLIBC_2.34
Version needs section '.gnu.version_r' contains 1 entry:
  0x0010: Name: GLIBC_99.99
"""
        self.assertEqual(probe.parse_version_definitions(output),
                         {"GLIBC_2.17", "GLIBC_2.34"})
        self.assertNotIn("GLIBC_99.99", probe.parse_version_definitions(output))

    def test_version_needs_are_not_wrongly_accepted_as_definitions(self):
        self.assertEqual(probe.parse_version_definitions(
            "Version needs section '.gnu.version_r'\n Name: GCC_3.0"), set())

    def test_version_output_size_is_bounded(self):
        with self.assertRaises(ValueError):
            probe.parse_version_definitions("A" * (probe.MAX_READELF_BYTES + 1))

    def test_different_architecture_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "fake"
            arm = bytearray(arm64_header())
            p.write_bytes(arm)
            self.assertTrue(probe._elf_header(str(p)))
            arm[18:20] = (62).to_bytes(2, "little")
            p.write_bytes(arm)
            self.assertFalse(probe._elf_header(str(p)))
            arm[18:20] = (183).to_bytes(2, "little")
            arm[4] = 1
            p.write_bytes(arm)
            self.assertFalse(probe._elf_header(str(p)))

    def test_host_library_resolution_does_not_accept_path_traversal(self):
        for path in ("/lib/../../etc/passwd", "/tmp/libc.so.6", "../lib/libc.so.6"):
            with self.subTest(path=path):
                entry, reason = probe._safe_system_path(path)
                self.assertIsNone(entry)
                self.assertEqual(reason, "unapproved_library_path")

    def test_symlink_target_outside_fixed_roots_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "outside"
            target.write_bytes(arm64_header())
            library_dir = root / "system"
            library_dir.mkdir()
            (library_dir / "libexample.so").symlink_to(target)
            with mock.patch.object(probe, "ROOTS", (str(library_dir) + "/",)):
                entry, reason = probe._safe_system_path(str(library_dir / "libexample.so"))
            self.assertIsNone(entry)
            self.assertEqual(reason, "library_symlink_outside_system_roots")

    def test_static_elf_hash_and_provided_versions_are_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "libc.so.6"
            binary = arm64_header() + b"synthetic-data"
            p.write_bytes(binary)
            stat0 = p.stat()
            definitions = ("Version definition section '.gnu.version_d':\n"
                           "Name: GLIBC_2.17\nName: GLIBC_2.28\n")
            with mock.patch.object(probe, "_safe_system_path",
                                   return_value=((str(p), stat0), None)), \
                    mock.patch.object(probe, "_fixed_command",
                                      return_value=(definitions, None)) as cmd:
                result = probe.inspect_library(str(p), ("GLIBC_2.17",))
            self.assertTrue(result["observed"])
            self.assertTrue(result["required_versions_observed"])
            self.assertEqual(result["sha256"], hashlib.sha256(binary).hexdigest())
            self.assertEqual(result["elf_machine"], "AArch64")
            self.assertEqual(result["bytes"], len(binary))
            self.assertEqual(cmd.call_count, 1)

    def test_missing_version_definition_never_counts_as_match(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "libc.so.6"
            p.write_bytes(arm64_header())
            with mock.patch.object(probe, "_safe_system_path",
                                   return_value=((str(p), p.stat()), None)), \
                    mock.patch.object(probe, "_fixed_command",
                                      return_value=("Version needs section:\n Name: GLIBC_2.17\n", None)):
                value = probe.inspect_library(str(p), ("GLIBC_2.17",))
            self.assertTrue(value["observed"])
            self.assertFalse(value["required_versions_observed"])

    def test_unavailable_utility_retains_unknown_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "libc.so.6"
            p.write_bytes(arm64_header())
            with mock.patch.object(probe, "_safe_system_path",
                                   return_value=((str(p), p.stat()), None)), \
                    mock.patch.object(probe, "_fixed_command",
                                      return_value=(None, "utility_missing")):
                value = probe.inspect_library(str(p), ("GLIBC_2.17",))
            self.assertTrue(value["observed"])
            self.assertFalse(value["required_versions_observed"])
            self.assertEqual(value["version_probe_error"], "utility_missing")

    def test_optional_crypt_missing_does_not_invalidate_core_static_evidence(self):
        def available(path, versions):
            return {"observed": True, "required_versions_observed": True}
        with mock.patch.object(probe, "_fixed_command",
                               return_value=("", None)), \
                mock.patch.object(probe, "inspect_library",
                                  side_effect=available):
            finding = probe.inventory()
        self.assertTrue(finding["core_static_libraries_observed"])
        self.assertFalse(finding["production_qualified"])
        self.assertFalse(finding["runtime_startup_verified"])
        self.assertFalse(finding["provisioning_authority"])
        self.assertFalse(finding["interpreter_installed"])

    def test_missing_core_version_blocks_without_installation(self):
        def incomplete(path, versions):
            return {"observed": False, "required_versions_observed": False}
        with mock.patch.object(probe, "_fixed_command",
                               return_value=("", "utility_missing")), \
                mock.patch.object(probe, "inspect_library",
                                  side_effect=incomplete):
            finding = probe.inventory()
        self.assertFalse(finding["core_static_libraries_observed"])
        self.assertEqual(finding["decision"], "host_static_dependency_evidence_incomplete")
        self.assertFalse(finding["native_interpreter_executed"])
        self.assertFalse(finding["interpreter_installed"])


if __name__ == "__main__":
    unittest.main()
