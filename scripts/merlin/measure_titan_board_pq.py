"""Exercise the private board/message codec and the pinned Titan recipient envelope."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
from time import perf_counter_ns

from merlin import titan_pq_envelope as pq
from merlin.titan_board_encoding import (
    HANDOFF_SHAPE, NOVEMBER_PROFILE, OPERATIONAL_SHAPE, decode_private_board_message,
    encode_private_board_message, handoff_board_record, public_board_context,
    replay_board_record, synthetic_board_example,
)


BUCKET = 262144
SCHEMA = "titan-board-pq-research-measurement/1"


def _rejects(envelope, seed, context):
    try:
        pq.decrypt(envelope, seed, context)
    except pq.TitanDecryptionError:
        return True
    return False


def measure():
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    clock = perf_counter_ns()
    backend = pq.backend_status()
    if not backend.get("available") or not backend.get("real_roundtrip"):
        raise pq.TitanDependencyUnavailable("required backend unavailable")

    public, seed = pq.generate_recipient_keypair()
    _, wrong_seed = pq.generate_recipient_keypair()
    modern = synthetic_board_example()
    legacy = handoff_board_record()
    context = public_board_context()
    modern_message, legacy_message = b"modern example\x00\xff", b"legacy example\xfe"
    modern_raw = encode_private_board_message(modern_message, modern)
    modern_envelope = pq.encrypt(modern_raw, public, context, pad_to=BUCKET)
    legacy_envelope = pq.encrypt(encode_private_board_message(legacy_message, legacy), public, context, pad_to=BUCKET)
    repeated = pq.encrypt(modern_raw, public, context, pad_to=BUCKET)

    modern_recovered = decode_private_board_message(pq.decrypt(modern_envelope, seed, context))
    legacy_recovered = decode_private_board_message(pq.decrypt(legacy_envelope, seed, context))
    header = json.loads(modern_envelope)["header"]
    legacy_header = json.loads(legacy_envelope)["header"]
    mirror_positions = [(index, point) for index, board in enumerate(modern.initial_boards)
                        for point, cell in enumerate(board) if cell == 3]
    after = replay_board_record(modern_recovered[1])
    checks = {
        "backend_roundtrip": backend["real_roundtrip"] is True,
        "three_modern_boards_with_preserved_mirror": (
            modern.profile == NOVEMBER_PROFILE and modern.geometry.shape == OPERATIONAL_SHAPE
            and len(after) == 3 and bool(mirror_positions)
            and all(after[index][point] == 3 for index, point in mirror_positions)),
        "modern_message_and_full_record_roundtrip": modern_recovered == (modern_message, modern),
        "legacy_message_and_full_record_roundtrip": (
            legacy.geometry.shape == HANDOFF_SHAPE and legacy_recovered == (legacy_message, legacy)),
        "identical_generic_public_headers": (
            header == legacy_header and header == {"schema": pq.SCHEMA, "version": 1,
                "suite": pq.SUITE, "pad_to": BUCKET, "context": public_board_context()}),
        "same_bucket_equal_wire_lengths": len(modern_envelope) == len(legacy_envelope),
        "repeated_encryption_differs": repeated != modern_envelope,
        "wrong_recipient_rejected": _rejects(modern_envelope, wrong_seed, context),
        "wrong_context_rejected": _rejects(modern_envelope, seed, {**context, "purpose": "different-purpose"}),
    }
    return {
        "schema": SCHEMA,
        "scope": "local_research_measurement",
        "versions": {"python": platform.python_version(), "cryptography": backend["cryptography_version"],
                     "openssl_backend": backend["openssl_backend_version"], "suite": pq.SUITE,
                     "envelope": pq.SCHEMA},
        "checks": checks,
        "wire_lengths_bytes": {"padding_bucket": BUCKET, "modern_envelope": len(modern_envelope),
                               "legacy_envelope": len(legacy_envelope)},
        "timing": {"started_utc": started, "elapsed_ns": perf_counter_ns() - clock},
    }


def same_measurement(receipt, expected):
    """Compare all measured fields except wall time; reject extra/missing fields."""
    if not isinstance(expected, dict) or set(expected) != set(receipt):
        return False
    time_fields = expected.get("timing")
    if (not isinstance(time_fields, dict) or set(time_fields) != set(receipt["timing"])
            or not isinstance(time_fields.get("started_utc"), str)
            or type(time_fields.get("elapsed_ns")) is not int or time_fields["elapsed_ns"] < 0):
        return False
    stable = lambda record: json.dumps({key: value for key, value in record.items() if key != "timing"},
                                      sort_keys=True, allow_nan=False)
    return stable(receipt) == stable(expected)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare", type=Path, help="Require matching checks, versions and wire lengths")
    args = parser.parse_args(argv)
    try:
        receipt = measure()
    except pq.TitanDependencyUnavailable:
        print(json.dumps({"schema": SCHEMA, "checks": {"supported_backend": False}}))
        return 2
    except Exception:
        # Third-party exceptions may carry sensitive values. Only fixed statuses are public.
        print(json.dumps({"schema": SCHEMA, "checks": {"completed": False}}))
        return 1
    if args.compare is not None:
        try:
            with args.compare.open("rb") as stream:
                raw = stream.read(16385)
            if len(raw) > 16384 or not same_measurement(receipt, json.loads(raw)):
                raise ValueError("receipt mismatch")
        except (OSError, ValueError, RecursionError):
            print(json.dumps({"schema": SCHEMA, "checks": {"comparison_match": False}}))
            return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if all(value is True for value in receipt["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
