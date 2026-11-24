"""Fixed, non-dispatching Wilborn monitoring preflight and receipt contract.

This version admits only request syntax. It cannot import acceptance workloads,
inspect the host, provision isolation, or authorize execution. Expected identities
are review inputs, not observations of acquired sources or effective isolation.
Missing runtime/profile identities stay null; supplying claims cannot enable a
runner. Retained receipts use the existing MerlinRegistry and ArtifactRef.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
import re
import sys
import uuid

from python.merlin.artifact_ref import ArtifactRef


PROFILE_ID = "wilborn_security_monitoring_synthetic_v1"
REQUEST_SCHEMA = "wilborn-security-monitoring-request/1"
RECEIPT_SCHEMA = "wilborn-security-monitoring-preflight/1"
MAX_REQUEST_BYTES = 4096
MAX_RECEIPT_BYTES = 64 * 1024
_REQUEST_FIELDS = frozenset({"schema", "request_id", "profile_id", "reason", "created_at"})
_STAGES = (
    ("identity_and_isolation", 30, "wrapper_preflight"),
    ("producer_regressions", 180, "producer_unittest_inventory"),
    ("canonical_signature_boundary", 30, "cace_attestation_inventory"),
    ("capacity_recovery_handover", 240, "recovery_workload_v3"),
    ("producer_package_display", 120, "source_verified_studio_handoff_v3"),
    ("preservation_and_termination", 30, "wrapper_postflight"),
)
_AUTHORITY_FIELDS = (
    "execution_authorized", "production_qualified", "deployment_authorized",
    "operational_custody_verified", "production_writer_activated",
)
_BLOCKERS = ("BLOCKED_DEPENDENCY_REVIEW", "BLOCKED_PROFILE_NOT_PROVISIONED")


class ProfileContractError(ValueError):
    """A bounded public code, never an echo of untrusted input or host state."""


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProfileContractError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ProfileContractError("NONFINITE_JSON_NUMBER")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ProfileContractError("NONFINITE_JSON_NUMBER")
    return number


def _decode(raw, limit):
    if type(raw) is not bytes or not 0 < len(raw) <= limit:
        raise ProfileContractError("INVALID_JSON_BYTE_BOUND")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=_invalid_constant, parse_float=_finite_float)
    except ProfileContractError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise ProfileContractError("INVALID_JSON") from None
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 16:
            raise ProfileContractError("JSON_STRUCTURE_LIMIT")
        if type(item) is dict:
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
    return value


def _request_id(value):
    if type(value) is not str:
        raise ProfileContractError("REQUEST_ID")
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError
    except ValueError:
        raise ProfileContractError("REQUEST_ID") from None
    return value


def parse_request(raw):
    """Admit bounded audit metadata only; no request field selects executable IO."""
    value = _decode(raw, MAX_REQUEST_BYTES)
    if type(value) is not dict or set(value) != _REQUEST_FIELDS:
        raise ProfileContractError("REQUEST_FIELDS")
    if value["schema"] != REQUEST_SCHEMA or value["profile_id"] != PROFILE_ID:
        raise ProfileContractError("REQUEST_PROFILE")
    _request_id(value["request_id"])
    reason = value["reason"]
    if (type(reason) is not str or not 1 <= len(reason) <= 300
            or reason != reason.strip() or not reason.isprintable()):
        raise ProfileContractError("REQUEST_REASON")
    created = value["created_at"]
    if type(created) is not str or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", created):
        raise ProfileContractError("REQUEST_TIMESTAMP")
    try:
        datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise ProfileContractError("REQUEST_TIMESTAMP") from None
    return value


def profile_manifest():
    """Return a fresh fixed review manifest; null identities deliberately block IO."""
    return {
        "schema": "wilborn-security-monitoring-profile/1",
        "profile_id": PROFILE_ID,
        "status": "contract_only_not_installed",
        "execution_supported": False,
        "expected_candidates": {
            "source_repository": "Mannyspiro/expert-robot",
            "producer_commit": "33303d5947024d10155a66a6dc6d46221088276a",
            "producer_tree": "d76d66364e2f77b8ff1a043d4edf4c58ff64a65a",
            "studio_commit": "0202024ea3e98d5d64e4f158babcee287e2a8eef",
            "studio_tree": "43af8844d996ca10e4b9a7894767ac7594bb6365",
            "package_sha256": "9d179b5f52f9e7ee72b7bf88f024f5480d8d4c4902c547c8e78c6525ebf7d520",
            "package_bytes": 100572,
        },
        "expected_test_inventory": {
            "source_commit": "33303d5947024d10155a66a6dc6d46221088276a",
            "patterns": ["tests/test_wilborn_*.py", "tests/test_cace_attestation.py"],
            "file_count": 43,
            "manifest_sha256": "ee28ba4940b1f72531571654af82d51e3d89957fd89c490acc4c891a0af284fa",
            "encoding": "canonical JSON array sorted by path; each entry has path, bytes, sha256",
            "case_inventory_reviewed_for_execution": False,
        },
        "runtime_requirements": {
            "system": "Linux", "architecture": "aarch64", "python_series": "3.11",
            "cryptography_version": "50.0.2", "python_build_sha256": None,
            "image_sha256": None, "sqlite_build_sha256": None,
            "cryptography_wheel_sha256": None,
        },
        "installation": {
            "reviewed_wrapper_sha256": None, "isolation_configuration_sha256": None,
            "installed_profile_sha256": None, "effective_isolation_evidence_ref": None,
        },
        "required_isolation": {
            "nonroot": True, "reviewed_inputs_only": True, "inputs_readonly": True,
            "private_home_and_tmp": True, "inherited_credentials": False,
            "host_service_access": False, "network": "isolated_fixture_loopback_only",
            "whole_group_limits_and_cleanup": True,
        },
        "budgets": {
            "cpu_cores": 2, "aggregate_cpu_seconds": 600,
            "memory_bytes": 1024 ** 3, "processes": 64,
            "scratch_bytes": 512 * 1024 ** 2, "workload_database_bytes": 64 * 1024 ** 2,
            "wall_seconds": 720, "receipt_bytes": MAX_RECEIPT_BYTES,
        },
        "stages": [{"id": name, "wall_seconds": seconds, "entrypoint_id": entry}
                   for name, seconds, entry in _STAGES],
        "workload_requirements": {
            "schema": "wilborn-security-recovery-workload/3",
            "events_per_segment": [1023, 2, 2], "total_events": 1027,
            "ownership_epoch": 2, "active_segment_index": 2, "displayed_incidents": 20,
            "ingestion_wall_seconds": 210, "internal_wall_seconds": 230,
            "handoff_schema": "merlin-security-handoff-evidence/3",
            "package_source_verified": True,
            "process_crash_evidence": "separate_handovers_and_generations_tests",
        },
    }


def validate_profile_manifest(raw):
    """Compare declared identities to the fixed review manifest, not live sources."""
    value = _decode(raw, MAX_RECEIPT_BYTES)
    if canonical_json(value) != canonical_json(profile_manifest()):
        raise ProfileContractError("PROFILE_MANIFEST_MISMATCH")
    return value


def _blocked_receipt(request):
    manifest = profile_manifest()
    return {
        "schema": RECEIPT_SCHEMA, "profile_id": PROFILE_ID,
        "profile_manifest_sha256": _digest(manifest),
        "request_id": request["request_id"], "request_sha256": _digest(request),
        "status": _BLOCKERS[0], "blockers": list(_BLOCKERS),
        "data_class": "synthetic", "evidence_class": "nonexecuting_preflight",
        "expected_candidates": manifest["expected_candidates"],
        "expected_test_inventory_sha256": manifest["expected_test_inventory"]["manifest_sha256"],
        "candidate_inputs_verified": False, "runtime_verified": False,
        "effective_isolation_verified": False, "test_inventory_verified": False,
        "stages": [{"id": name, "status": "BLOCKED" if index == 0 else "NOT_RUN"}
                   for index, (name, _seconds, _entry) in enumerate(_STAGES)],
        "counts": {"passed_stages": 0, "failed_stages": 0, "blocked_stages": 1,
                   "not_run_stages": len(_STAGES) - 1, "acceptance_tests_run": 0},
        "measurements": {"aggregate_cpu_seconds": None, "elapsed_seconds": None,
                         "peak_memory_bytes": None, "peak_scratch_bytes": None},
        **{field: False for field in _AUTHORITY_FIELDS},
    }


def validate_receipt(raw, request_raw):
    """Validate this version's blocked-only schema and exact request/profile binding.

    No caller can turn measurements or an all-passed stage list into a receipt
    accepted by this contract. Execution receipts require a separately reviewed
    schema and adapter; this function intentionally has no permissive pass branch.
    """
    request = parse_request(request_raw)
    value = _decode(raw, MAX_RECEIPT_BYTES)
    if canonical_json(value) != canonical_json(_blocked_receipt(request)):
        raise ProfileContractError("PREFLIGHT_RECEIPT_MISMATCH")
    return value


def receipt_path(request_id):
    """Canonical existing-registry location; a request never supplies a path."""
    return "security/monitoring/preflight/" + _request_id(request_id) + ".json"


def preflight(request_raw, *, registry=None, prior_receipt_ref=None):
    """Build or read-only reconcile a blocked receipt. Never dispatch or write.

    A host may explicitly retain returned bytes using MerlinRegistry.put_artifact
    in wilborn-demo. A supplied prior version is resolved and rehashed by that
    registry, and must match this complete request and profile. No latest-version
    lookup, replacement, retry, or second receipt store is performed here.
    """
    request = parse_request(request_raw)
    if (registry is None) != (prior_receipt_ref is None):
        raise ProfileContractError("REPLAY_REFERENCE_REQUIRED")
    if prior_receipt_ref is not None:
        try:
            ref = ArtifactRef.from_mapping(prior_receipt_ref)
        except (ValueError, TypeError):
            raise ProfileContractError("REPLAY_REFERENCE_INVALID") from None
        if (ref.project_id != "wilborn-demo"
                or ref.logical_path != receipt_path(request["request_id"])):
            raise ProfileContractError("REPLAY_REFERENCE_SCOPE")
        # Registry integrity failures remain failures; never fall back to a rerun.
        saved = registry.read_artifact_ref(ref.to_dict(), max_bytes=MAX_RECEIPT_BYTES)
        if saved["resolution"]["media_type"] != "application/json":
            raise ProfileContractError("REPLAY_MEDIA_TYPE")
        return validate_receipt(saved["content"], request_raw)
    receipt = _blocked_receipt(request)
    return validate_receipt(canonical_json(receipt), request_raw)


class _BoundedParser(argparse.ArgumentParser):
    def error(self, _message):
        # argparse normally echoes unknown arguments, which may contain private
        # text. Reject options without exporting their values or local paths.
        raise ProfileContractError("CLI_ARGUMENTS")


def _reject(code):
    rejection = {"schema": "wilborn-security-monitoring-rejection/1",
                 "status": "REJECTED_REQUEST", "code": code,
                 "execution_authorized": False}
    sys.stderr.buffer.write(canonical_json(rejection) + b"\n")
    return 2


def main(argv=None):
    parser = _BoundedParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--describe", action="store_true",
                        help="print the fixed review manifest; do not read a request")
    try:
        args = parser.parse_args(argv)
    except ProfileContractError as exc:
        return _reject(str(exc))
    if args.describe:
        sys.stdout.buffer.write(canonical_json(profile_manifest()) + b"\n")
        return 0
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        result = preflight(raw)
    except ProfileContractError as exc:
        return _reject(str(exc))
    sys.stdout.buffer.write(canonical_json(result) + b"\n")
    return 3  # A valid request is blocked, never successful acceptance.
