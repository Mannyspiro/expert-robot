#!/usr/bin/env python3
"""One-shot local vision-model evidence probe with an exact PNG source pin.

This is an operator-triggered qualification aid, NOT a background sensor, model
installation, automatic promotion, or independent check. The model server
receives the image over loopback and may retain its own logs; inspect it first.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Callable

from model import LocalModel, ModelError, endpoint_parts
from senses import analyze_png
from tools import read_regular

SCHEMA = "merlin-local-vision-probe/1"
MAX_REPORT = 32 * 1024


def _digest(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def probe_image(*, image: Path, expected_sha256: str, model_url: str, model_id: str,
                question: str, timeout: float = 45,
                model_factory: Callable | None = None) -> dict:
    """Record a local model response separately from scientific verification."""
    if not isinstance(expected_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise ValueError("Pin the exact 64-character PNG SHA-256 before running")
    if not isinstance(image, Path) or image.suffix.lower() != ".png":
        raise ValueError("Use a PNG file supplied explicitly by the operator")
    if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 200:
        raise ValueError("A bounded model identifier is required")
    if not isinstance(question, str) or not question.strip() or len(question) > 1000:
        raise ValueError("A bounded preregistered image question is required")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 45:
        raise ValueError("Timeout must be finite and at most 45 seconds")
    endpoint = endpoint_parts(model_url)
    if endpoint is None:
        raise ValueError("An operator-configured local vision model is required")
    # read_regular rejects leaf symlinks, FIFOs, devices and oversize files.
    data = read_regular(image)
    actual = sha256(data).hexdigest()
    if actual != expected_sha256:
        raise ValueError("PNG source bytes differ from pre-registered SHA-256")
    features = analyze_png(data)
    settings = {"model_url": model_url, "model_id": model_id}
    model = model_factory(settings) if model_factory is not None else LocalModel(settings)
    if not callable(getattr(model, "describe_png", None)):
        raise ValueError("Configured provider lacks the bounded PNG adapter")
    started = time.monotonic()
    response = model.describe_png(data, prompt=question, timeout=timeout)
    elapsed = round((time.monotonic() - started) * 1000, 2)
    if (not isinstance(response, dict)
            or response.get("schema") != "merlin-local-vision-interpretation/1"
            or response.get("source_sha256") != actual
            or response.get("model_id") != model_id
            or not isinstance(response.get("caption"), str)
            or not response["caption"].strip()
            or response.get("independent_verification") is not False):
        raise ValueError("Model response does not satisfy exact-source/authority contract")
    result = {
        "schema": SCHEMA, "status": "response_requires_independent_review",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": actual, "source_format": "image/png",
        "source_pixels": [features["width_px"], features["height_px"]],
        "model_id": model_id, "endpoint": {"host": endpoint[0], "port": endpoint[1],
                                           "path": endpoint[2]},
        "question": question, "response": response["caption"],
        "local_transport_elapsed_ms": elapsed,
        "method": "operator_initiated_local_model_request_with_exact_source_pin",
        "no_hosted_api_used_by_adapter": True,
        "real_model_weights_attested": False,
        "model_server_logs_and_network_attested": False,
        "independent_verification": False,
        "grounded_visual_accuracy_measured": False,
        "production_qualified": False,
        "promotion_authority": False,
        "next_test": "Compare with independently held-out visual reference and measured model/process identity.",
    }
    result["receipt_sha256"] = _digest(result)
    if len(json.dumps(result).encode("utf-8")) > MAX_REPORT:
        raise ValueError("Probe evidence report exceeds bounded output ceiling")
    return result


def save_report(path: Path, report: dict) -> None:
    """Create-only private evidence; fail closed instead of replacing prior runs."""
    path = Path(path)
    if path.is_symlink() or not path.parent.is_dir():
        raise ValueError("Evidence output parent must be an existing directory without a leaf symlink")
    body = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if len(body) > MAX_REPORT:
        raise ValueError("Evidence report exceeds byte ceiling")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--image-sha256", required=True,
                        help="Pre-registered exact PNG digest")
    parser.add_argument("--model-url", required=True,
                        help="Existing loopback HTTP chat-completions endpoint")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--out", type=Path, required=True,
                        help="New nonexisting report file path")
    parser.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args()
    try:
        report = probe_image(image=args.image, expected_sha256=args.image_sha256,
                             model_url=args.model_url, model_id=args.model_id,
                             question=args.question, timeout=args.timeout)
        save_report(args.out, report)
    except (ValueError, OSError, ModelError) as exc:
        # Retain null/failed attempts while avoiding any fabricated model result.
        # The source pin is a supplied claim until validated; model effects may
        # remain unknown if a request was interrupted or failed.
        failure = {
            "schema": SCHEMA, "status": "blocked_requires_review",
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "requested_source_sha256": args.image_sha256,
            "requested_model_id": args.model_id,
            "error_type": type(exc).__name__,
            "failure_reason": str(exc)[:300],
            "source_identity_verified": False,
            "model_request_effect": "unknown_or_not_started",
            "real_model_weights_attested": False,
            "independent_verification": False,
            "production_qualified": False,
            "promotion_authority": False,
        }
        failure["receipt_sha256"] = _digest(failure)
        try:
            save_report(args.out, failure)
        except (OSError, ValueError) as output_error:
            print("Evidence could not be saved: " + str(output_error)[:200], file=sys.stderr)
        print(type(exc).__name__ + ": " + str(exc)[:400], file=sys.stderr)
        return 2
    print(json.dumps({"report": str(args.out), "receipt_sha256": report["receipt_sha256"],
                      "status": report["status"], "production_qualified": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
