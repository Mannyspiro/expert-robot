"""Bounded failure decisions and explicit reframing; no autonomous patch execution.

A fingerprint groups symptoms within one immutable outbox delivery, not proven
root causes. Exception messages are intentionally neither rendered nor retained.
The existing outbox owns durability; this module creates no store or authority.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Any

SCHEMA = "merlin-failure-plan/1"
REFRAMES = {
    "admission": ("constraint_satisfaction", "schema and authority", "input identity"),
    "telemetry": ("separate_observation_from_execution", "durable task state", "no false completion"),
    "execution": ("minimal_subproblem", "original input/output contract", "resource and trust bounds"),
    "result_validation": ("typed_interface_boundary", "artifact identity", "original acceptance criteria"),
    "acknowledgement": ("transaction_state_machine", "receipt/event atomicity", "lease ownership"),
}


def _integer(value: Any, label: str) -> int:
    if type(value) is not int or not 1 <= value <= 1_000_000:
        raise ValueError(label + " must be a positive bounded integer")
    return value


def _category(error: Exception) -> tuple[str, bool]:
    if isinstance(error, PermissionError):
        return "admission_denied", True
    if isinstance(error, (ValueError, TypeError, KeyError, sqlite3.IntegrityError, sqlite3.ProgrammingError)):
        return "invalid_contract", True
    if isinstance(error, (MemoryError, TimeoutError, FileNotFoundError, NotImplementedError)):
        return "resource_or_capability_block", True
    if isinstance(error, InterruptedError):
        return "interrupted", False
    if isinstance(error, (OSError, sqlite3.OperationalError)):
        return "storage_or_transport", False
    return "execution_failure", False


def failure_plan(*, error: Exception, event_id: str, phase: str, attempt: int,
                 max_attempts: int, max_same_failures: int = 2,
                 previous_error: str | None = None) -> dict[str, Any]:
    """Choose bounded retry or stop/reframe without interpreting exception prose.

    An unknown error is not called transient: one policy-bounded retry may help
    discriminate it. Unchanged invalid contracts are stopped immediately. The
    host must still revalidate approval, lease and idempotency on any retry.
    """
    if not isinstance(error, Exception):
        raise ValueError("an Exception instance is required")
    if not isinstance(event_id, str) or not re.fullmatch(r"evt_[0-9a-f]{64}", event_id):
        raise ValueError("a canonical outbox event ID is required")
    if not isinstance(phase, str) or phase not in REFRAMES:
        raise ValueError("unsupported failure phase")
    _integer(attempt, "attempt"); _integer(max_attempts, "max_attempts")
    _integer(max_same_failures, "max_same_failures")
    category, permanent = _category(error)
    fingerprint = hashlib.sha256(json.dumps(
        [SCHEMA, event_id, phase, category], separators=(",", ":")
    ).encode()).hexdigest()
    repeats, history = 1, "none_or_legacy"
    invalid_history = False
    if isinstance(previous_error, str) and len(previous_error) <= 2000:
        try:
            previous = json.loads(previous_error)
        except (ValueError, RecursionError):
            previous = None
        if isinstance(previous, dict) and previous.get("schema") == SCHEMA:
            count, previous_attempt = previous.get("same_failure_count"), previous.get("attempt")
            if (type(count) is not int or type(previous_attempt) is not int
                    or not 1 <= count <= previous_attempt or previous_attempt != attempt - 1
                    or previous.get("event_id") != event_id):
                history, invalid_history = "invalid", True
            elif previous.get("fingerprint") == fingerprint:
                repeats, history = count + 1, "same_symptom_group"
            else:
                history = "different_symptom_group"
    stop = permanent or invalid_history or repeats >= max_same_failures or attempt >= max_attempts
    action = "quarantine_and_reframe" if stop else "retry_same_approved_task"
    if category == "admission_denied":
        action = "reject_no_execution"
    target, invariant_a, invariant_b = REFRAMES[phase]
    return {
        "schema": SCHEMA, "event_id": event_id, "fingerprint": fingerprint,
        "phase": phase, "category": category, "attempt": attempt,
        "same_failure_count": repeats, "history": history, "action": action,
        "classification": "provisional_symptom_group_not_root_cause",
        "root_cause": "not_established", "resolved": False,
        "reframe": {"kind": "heuristic", "target": target,
                    "preserve": [invariant_a, invariant_b],
                    "translation_back_gate": "rerun_original_acceptance_tests"},
        "next_actions": ["retain_exact_source_and_input_refs", "reproduce_with_negative_control",
                         "compare_competing_causes_and_smaller_subproblems",
                         "test_patch_original_acceptance_and_adjacent_regressions"],
        "authority_effect": "none", "promotion_authority": False,
    }


def encode_failure_plan(plan: dict[str, Any]) -> str:
    """Fit the existing outbox last_error field without silently truncating JSON."""
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded) > 2000:
        raise ValueError("failure plan exceeds the existing outbox field")
    return encoded
