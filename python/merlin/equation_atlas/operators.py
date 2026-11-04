"""Validation helpers for the proposed XMG cross-domain operator contract.

This validates declarations and graph composition only; it does not execute physics.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "docs/research/real-world-equation-atlas/XMG_CROSS_DOMAIN_OPERATOR_CONTRACT_V0.1.json"


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def validate_pipeline(steps: list[dict[str, str]], contract: dict[str, Any] | None = None) -> list[str]:
    """Return declaration errors for a linear operator pipeline."""
    spec = contract or load_contract()
    operators = {item["id"]: item for item in spec["operators"]}
    errors: list[str] = []
    previous_output: str | None = None

    for index, step in enumerate(steps):
        op_id = step.get("operator", "")
        input_frame = step.get("input_frame", "")
        output_frame = step.get("output_frame", "")
        op = operators.get(op_id)
        if op is None:
            errors.append(f"step {index}: unknown operator {op_id!r}")
            previous_output = output_frame or None
            continue
        if input_frame not in op["inputs"]:
            errors.append(f"step {index}: {op_id} does not accept {input_frame!r}")
        if output_frame not in op["outputs"]:
            errors.append(f"step {index}: {op_id} does not produce {output_frame!r}")
        if previous_output is not None and input_frame != previous_output:
            errors.append(
                f"step {index}: frame mismatch; previous output {previous_output!r}, "
                f"next input {input_frame!r}"
            )
        previous_output = output_frame or None
    return errors
