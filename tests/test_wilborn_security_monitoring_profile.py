"""Contract tests, not live OCI execution or kernel-isolation qualification."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from python.merlin import project_registry as registry_module
from python.merlin.project_registry import ArtifactSizeLimitError, MerlinRegistry
from wilborn_ops.security_monitoring_profile import (
    MAX_RECEIPT_BYTES, MAX_REQUEST_BYTES, PROFILE_ID, REQUEST_SCHEMA,
    ProfileContractError, canonical_json, parse_request, preflight,
    profile_manifest, receipt_path, validate_profile_manifest, validate_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/merlin/wilborn_security_profile_preflight.py"


def request(**changes):
    value = {"schema": REQUEST_SCHEMA,
             "request_id": "63d3ba1a-27c1-4e50-a8fd-5ee2c69e507b",
             "profile_id": PROFILE_ID, "reason": "Review synthetic acceptance prerequisites",
             "created_at": "2026-11-24T12:00:00Z"}
    value.update(changes)
    return canonical_json(value)


class RequestTests(unittest.TestCase):
    def test_fixed_request_is_accepted_without_execution(self):
        with patch("subprocess.Popen") as process, patch("socket.socket") as socket:
            result = preflight(request())
        process.assert_not_called()
        socket.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED_DEPENDENCY_REVIEW")
        self.assertEqual(result["blockers"], ["BLOCKED_DEPENDENCY_REVIEW",
                                            "BLOCKED_PROFILE_NOT_PROVISIONED"])
        self.assertEqual([s["status"] for s in result["stages"]],
                         ["BLOCKED"] + ["NOT_RUN"] * 5)
        self.assertEqual(result["counts"]["acceptance_tests_run"], 0)
        self.assertTrue(all(v is None for v in result["measurements"].values()))
        for flag in ("execution_authorized", "production_qualified", "deployment_authorized",
                     "operational_custody_verified", "production_writer_activated",
                     "candidate_inputs_verified", "runtime_verified",
                     "effective_isolation_verified", "test_inventory_verified"):
            self.assertIs(result[flag], False)

    def test_unknown_execution_fields_are_rejected(self):
        for field in ("command", "shell", "python", "url", "source_commit", "path", "env",
                      "network_target", "credential", "signing_key", "test_selector",
                      "runtime", "profile_installed", "isolated", "prior_receipt_ref"):
            with self.subTest(field=field), self.assertRaisesRegex(ProfileContractError, "REQUEST_FIELDS"):
                parse_request(request(**{field: "caller controlled"}))

    def test_missing_fields_and_nondictionaries_rejected(self):
        original = json.loads(request())
        for field in original:
            value = dict(original)
            del value[field]
            with self.subTest(field=field), self.assertRaises(ProfileContractError):
                parse_request(canonical_json(value))
        for value in ([], None, True, 1, "request"):
            with self.subTest(value=value), self.assertRaises(ProfileContractError):
                parse_request(canonical_json(value))

    def test_duplicate_and_escaped_duplicate_keys_rejected(self):
        raw = request()
        for extra in (b'"schema":"ignored",', b'"profile_\\u0069d":"ignored",'):
            with self.subTest(extra=extra), self.assertRaisesRegex(ProfileContractError, "DUPLICATE_JSON_KEY"):
                parse_request(b"{" + extra + raw[1:])

    def test_byte_encoding_and_depth_bounds(self):
        for raw in (b"", "not bytes", b"\xff", b"{", b" " * (MAX_REQUEST_BYTES + 1),
                    b"[" * 30 + b"0" + b"]" * 30, b"[" * 1500):
            with self.subTest(raw_type=type(raw).__name__), self.assertRaises(ProfileContractError):
                parse_request(raw)

    def test_nonfinite_json_forms_rejected(self):
        for number in (b"NaN", b"Infinity", b"-Infinity", b"1e999", b"-1e999"):
            with self.subTest(number=number), self.assertRaisesRegex(ProfileContractError, "NONFINITE"):
                parse_request(b'{"value":' + number + b"}")

    def test_other_profile_or_schema_rejected(self):
        for changes in ({"profile_id": "inventory_snapshot"}, {"schema": "merlin-oci-job-request-v1"},
                        {"profile_id": True}, {"schema": {}}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ProfileContractError, "REQUEST_PROFILE"):
                parse_request(request(**changes))

    def test_uuid_is_canonical_and_cannot_supply_path(self):
        for value in (None, 1, "../receipt", "63D3BA1A-27C1-4E50-A8FD-5EE2C69E507B",
                      "63d3ba1a27c14e50a8fd5ee2c69e507b", "urn:uuid:63d3ba1a-27c1-4e50-a8fd-5ee2c69e507b"):
            with self.subTest(value=value), self.assertRaisesRegex(ProfileContractError, "REQUEST_ID"):
                parse_request(request(request_id=value))
            with self.assertRaises(ProfileContractError):
                receipt_path(value)

    def test_reason_has_bounded_printable_text(self):
        for value in (None, 7, "", " ", "leading ", " leading", "x\ny", "x\x00y",
                      "x\u202ey", "x" * 301):
            with self.subTest(value=value), self.assertRaisesRegex(ProfileContractError, "REQUEST_REASON"):
                parse_request(request(reason=value))
        self.assertEqual(len(parse_request(request(reason="x" * 300))["reason"]), 300)

    def test_utc_timestamp_requires_actual_calendar_date(self):
        for value in (True, "2026-11-24", "2026-11-24T12:00:00+00:00",
                      "2026-11-24T12:00:60Z", "2026-02-29T12:00:00Z", "0000-01-01T00:00:00Z"):
            with self.subTest(value=value), self.assertRaisesRegex(ProfileContractError, "REQUEST_TIMESTAMP"):
                parse_request(request(created_at=value))

    def test_request_metadata_is_hashed_not_echoed_or_executed(self):
        secretish = "audit-canary-very-private $(touch /tmp/never-execute)"
        receipt = canonical_json(preflight(request(reason=secretish)))
        self.assertNotIn(secretish.encode(), receipt)
        self.assertNotIn(b"never-execute", receipt)
        self.assertNotIn(b"created_at", receipt)

    def test_key_order_and_whitespace_canonicalize_same_request(self):
        original = json.loads(request())
        reordered = json.dumps(dict(reversed(list(original.items()))), indent=4).encode()
        self.assertEqual(preflight(request()), preflight(reordered))


class ManifestAndReceiptTests(unittest.TestCase):
    def test_manifest_returns_independent_copy_and_explicit_unknowns(self):
        first = profile_manifest()
        changed = profile_manifest()
        changed["expected_candidates"]["producer_commit"] = "0" * 40
        changed["stages"][0]["wall_seconds"] = 999
        self.assertEqual(first, profile_manifest())
        self.assertIs(first["runtime_requirements"]["image_sha256"], None)
        self.assertTrue(all(value is None for value in first["installation"].values()))
        self.assertIs(first["execution_supported"], False)
        self.assertLess(sum(stage["wall_seconds"] for stage in first["stages"]),
                        first["budgets"]["wall_seconds"])

    def test_review_manifest_cannot_change_sources_limits_or_supply_approval(self):
        for section, key, value in (
            ("expected_candidates", "producer_commit", "0" * 40),
            ("expected_candidates", "studio_tree", "0" * 40),
            ("expected_candidates", "package_sha256", "0" * 64),
            ("expected_test_inventory", "manifest_sha256", "0" * 64),
            ("runtime_requirements", "image_sha256", "0" * 64),
            ("installation", "installed_profile_sha256", "0" * 64),
            ("required_isolation", "network", "host"),
            ("budgets", "wall_seconds", 721),
            ("budgets", "processes", 65),
        ):
            value_manifest = profile_manifest()
            value_manifest[section][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ProfileContractError, "MANIFEST_MISMATCH"):
                validate_profile_manifest(canonical_json(value_manifest))
        self.assertEqual(validate_profile_manifest(canonical_json(profile_manifest())), profile_manifest())

    def test_legacy_hermes_limits_cannot_be_substituted(self):
        manifest = profile_manifest()
        manifest["budgets"].update(wall_seconds=120, aggregate_cpu_seconds=60,
                                   processes=32, scratch_bytes=16 * 1024 ** 2)
        manifest["required_isolation"]["network"] = "AF_UNIX"
        with self.assertRaisesRegex(ProfileContractError, "MANIFEST_MISMATCH"):
            validate_profile_manifest(canonical_json(manifest))

    def test_receipt_is_deterministic_bounded_and_request_bound(self):
        raw = canonical_json(preflight(request()))
        self.assertLess(len(raw), MAX_RECEIPT_BYTES)
        self.assertEqual(raw, canonical_json(preflight(request())))
        self.assertEqual(validate_receipt(raw, request()), preflight(request()))
        with self.assertRaisesRegex(ProfileContractError, "RECEIPT_MISMATCH"):
            validate_receipt(raw, request(reason="Changed audit metadata for same request ID"))
        with self.assertRaisesRegex(ProfileContractError, "RECEIPT_MISMATCH"):
            validate_receipt(raw, request(request_id="1884be38-13c9-40dd-bc17-ab17ec88843f"))

    def test_receipt_cannot_assert_success_authority_or_verification(self):
        for key, value in (
            ("status", "PASSED"), ("execution_authorized", True),
            ("production_qualified", True), ("deployment_authorized", True),
            ("operational_custody_verified", True), ("production_writer_activated", True),
            ("candidate_inputs_verified", True), ("runtime_verified", True),
            ("effective_isolation_verified", True), ("test_inventory_verified", True),
            ("execution_authorized", 0), ("profile_manifest_sha256", "0" * 64),
        ):
            receipt = preflight(request())
            receipt[key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ProfileContractError, "RECEIPT_MISMATCH"):
                validate_receipt(canonical_json(receipt), request())

    def test_receipt_rejects_fabricated_counts_measurements_and_stage_outcomes(self):
        mutations = [lambda r: r["counts"].update(acceptance_tests_run=186),
                     lambda r: r["counts"].update(passed_stages=False),
                     lambda r: r["counts"].update(not_run_stages=4),
                     lambda r: r["stages"][1].update(status="PASSED"),
                     lambda r: r["stages"].reverse(),
                     lambda r: r["measurements"].update(aggregate_cpu_seconds=0.0),
                     lambda r: r.update(blockers=[])]
        for mutate in mutations:
            value = preflight(request())
            mutate(value)
            with self.assertRaisesRegex(ProfileContractError, "RECEIPT_MISMATCH"):
                validate_receipt(canonical_json(value), request())

    def test_receipt_rejects_logs_host_fields_duplicates_and_excess_bytes(self):
        for key in ("stdout", "stderr", "host_inventory", "environment", "keys"):
            value = preflight(request())
            value[key] = "must not enter public evidence"
            with self.subTest(key=key), self.assertRaises(ProfileContractError):
                validate_receipt(canonical_json(value), request())
        raw = canonical_json(preflight(request()))
        with self.assertRaisesRegex(ProfileContractError, "DUPLICATE_JSON_KEY"):
            validate_receipt(b'{"status":"PASSED",' + raw[1:], request())
        with self.assertRaisesRegex(ProfileContractError, "BYTE_BOUND"):
            validate_receipt(raw + b" " * MAX_RECEIPT_BYTES, request())


class RegistryReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.registry = MerlinRegistry(self.directory.name)
        self.registry.register_project("wilborn-demo", "Synthetic preflight fixture")
        self.raw = request()
        self.path = receipt_path(parse_request(self.raw)["request_id"])

    def save(self, body=None, media_type="application/json"):
        if body is None:
            body = canonical_json(preflight(self.raw))
        self.registry.put_artifact("wilborn-demo", self.path, body, media_type)
        return self.registry.artifact_ref("wilborn-demo", self.path)

    def test_exact_version_reconciles_without_registry_write(self):
        ref = self.save()
        before = hashlib.sha256(self.registry.db_path.read_bytes()).hexdigest()
        with patch.object(self.registry, "put_artifact", side_effect=AssertionError("unexpected write")):
            result = preflight(self.raw, registry=self.registry, prior_receipt_ref=ref)
        self.assertEqual(result, preflight(self.raw))
        self.assertEqual(before, hashlib.sha256(self.registry.db_path.read_bytes()).hexdigest())
        self.assertEqual(len(self.registry.artifact_history("wilborn-demo", self.path)), 1)

    def test_pinned_prior_version_is_not_replaced_by_latest(self):
        first = self.save()
        second = self.save(canonical_json({"unreviewed": "new version"}))
        self.assertEqual(second["version"], 2)
        self.assertEqual(preflight(self.raw, registry=self.registry, prior_receipt_ref=first), preflight(self.raw))
        with self.assertRaises(ProfileContractError):
            preflight(self.raw, registry=self.registry, prior_receipt_ref=second)

    def test_same_id_different_request_cannot_reuse_saved_receipt(self):
        ref = self.save()
        with self.assertRaisesRegex(ProfileContractError, "RECEIPT_MISMATCH"):
            preflight(request(reason="Different request body"), registry=self.registry, prior_receipt_ref=ref)

    def test_oversized_replay_rejects_before_full_blob_hash_or_read(self):
        ref = self.save(b" " * (MAX_RECEIPT_BYTES + 1))
        with patch.object(registry_module, "_file_sha256", side_effect=AssertionError("full hash called")) as full_hash, \
                patch.object(Path, "read_bytes", side_effect=AssertionError("full read called")) as full_read, \
                patch.object(registry_module.os, "fdopen", side_effect=AssertionError("content read")) as stream:
            with self.assertRaises(ArtifactSizeLimitError):
                preflight(self.raw, registry=self.registry, prior_receipt_ref=ref)
        full_hash.assert_not_called()
        full_read.assert_not_called()
        stream.assert_not_called()

    def test_reference_scope_and_media_type_are_checked(self):
        ref = self.save()
        for changed in ({"project_id": "wilborn-production"}, {"logical_path": "other/path"},
                        {"logical_path": "../receipt.json"}, {"version": True}, {"extra": "host"}):
            with self.subTest(changed=changed), self.assertRaises(ProfileContractError):
                preflight(self.raw, registry=self.registry, prior_receipt_ref=dict(ref, **changed))
        other = self.save(b"{}", media_type="text/plain")
        with self.assertRaisesRegex(ProfileContractError, "MEDIA_TYPE"):
            preflight(self.raw, registry=self.registry, prior_receipt_ref=other)

    def test_corrupt_missing_or_forged_artifact_never_falls_back(self):
        ref = self.save()
        with self.assertRaises(KeyError):
            preflight(self.raw, registry=self.registry, prior_receipt_ref=dict(ref, version=99))
        with self.assertRaises(ValueError):
            preflight(self.raw, registry=self.registry, prior_receipt_ref=dict(ref, sha256="0" * 64))
        blob = self.registry.blobs / ref["sha256"][:2] / ref["sha256"][2:]
        blob.write_bytes(b"tampered")
        with self.assertRaises(RuntimeError):
            preflight(self.raw, registry=self.registry, prior_receipt_ref=ref)

    def test_replay_parameters_must_be_paired(self):
        ref = self.save()
        for parameters in ({"registry": self.registry}, {"prior_receipt_ref": ref}):
            with self.assertRaisesRegex(ProfileContractError, "REFERENCE_REQUIRED"):
                preflight(self.raw, **parameters)


class CliTests(unittest.TestCase):
    def run_cli(self, *args, input_bytes=b"", cwd=None, env=None):
        return subprocess.run([sys.executable, "-I", "-B", str(CLI), *args],
                              input=input_bytes, capture_output=True, timeout=10,
                              cwd=cwd, env=env)

    def test_valid_request_returns_blocked_exit_and_strict_receipt(self):
        child = self.run_cli(input_bytes=request())
        self.assertEqual(child.returncode, 3, child.stderr)
        self.assertEqual(child.stderr, b"")
        self.assertEqual(validate_receipt(child.stdout, request()), preflight(request()))

    def test_rejected_request_does_not_echo_untrusted_data(self):
        marker = "private-metadata-canary"
        child = self.run_cli(input_bytes=request(command=marker))
        self.assertEqual(child.returncode, 2)
        self.assertEqual(child.stdout, b"")
        self.assertNotIn(marker.encode(), child.stderr)
        self.assertEqual(json.loads(child.stderr)["code"], "REQUEST_FIELDS")
        child = self.run_cli(input_bytes=b"x" * (MAX_REQUEST_BYTES + 10))
        self.assertEqual(json.loads(child.stderr)["code"], "INVALID_JSON_BYTE_BOUND")

    def test_describe_is_fixed_and_no_execution_option_exists(self):
        child = self.run_cli("--describe")
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(validate_profile_manifest(child.stdout), profile_manifest())
        for option in ("--execute", "--runtime", "--command", "--source", "--install", "--des"):
            with self.subTest(option=option):
                marker = "private-cli-argument-canary"
                child = self.run_cli(option, marker, input_bytes=request())
                self.assertEqual(child.returncode, 2)
                self.assertEqual(child.stdout, b"")
                self.assertNotIn(marker.encode(), child.stderr)
                self.assertEqual(json.loads(child.stderr)["code"], "CLI_ARGUMENTS")

    def test_isolated_cli_ignores_hostile_cwd_and_pythonpath(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "json.py").write_text("raise RuntimeError('untrusted JSON import')")
            for package in ("wilborn_ops", "python"):
                (root / package).mkdir()
                (root / package / "__init__.py").write_text("raise RuntimeError('untrusted package import')")
            child = self.run_cli(input_bytes=request(), cwd=root,
                                 env={"PYTHONPATH": str(root), "LANG": "C.UTF-8"})
        self.assertEqual(child.returncode, 3, child.stderr)
        self.assertEqual(validate_receipt(child.stdout, request()), preflight(request()))


if __name__ == "__main__":
    unittest.main()
