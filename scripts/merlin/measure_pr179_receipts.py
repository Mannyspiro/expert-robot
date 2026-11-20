"""Replay one preregistered PR 179 retrieval trial offline against two exact Git trees."""
import argparse
from collections import Counter
from functools import partial
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[2]
PROTOCOL = HERE / "tests/fixtures/pr179-fresh-receipts-v1.json"
PROTOCOL_HASH = "305931db77d884f57ee4ff453a3096be96c2b5aff02728fe0df7513d731fbe3b"


def pinned(path, git_blob):
    raw = path.read_bytes()
    if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != git_blob:
        raise ValueError(f"upstream blob mismatch at {path}")
    return raw


def typed_equal(left, right):
    return type(left) is type(right) and left == right


def byte_span(raw, pointer, value):
    actual = json.loads(raw)
    for field in pointer.strip("/").split("/"):
        actual = actual[field]
    if not typed_equal(actual, value):
        raise ValueError("source pointer/value mismatch")
    token = (json.dumps(field) + ": " + json.dumps(value)).encode()
    if raw.count(token) != 1:
        raise ValueError("citation span is ambiguous or missing")
    start = raw.index(token)
    return {"start_byte": start, "end_byte": start + len(token), "sha256": hashlib.sha256(token).hexdigest()}


def check_answer(result, gold, run_for_ref, corpus):
    citation = result.get("citation")
    checked = None
    if citation:
        matched = [run for run, ref in run_for_ref.items() if ref == citation.get("source_ref")]
        if len(matched) == 1:
            run = matched[0]
            pointer = citation["pointer"]
            checked = {"run": run, "pointer": pointer, **byte_span(corpus[run], pointer, result.get("value"))}
    same_action = result["disposition"] == gold["disposition"]
    if "run" in gold:
        expected = {"run": gold["run"], "pointer": gold["pointer"],
                    **byte_span(corpus[gold["run"]], gold["pointer"], gold["value"])}
        passed = same_action and typed_equal(result.get("value"), gold["value"]) and checked == expected
    else:
        passed = same_action and result.get("value") is None and citation is None
    return {"action": result["disposition"], "value": result.get("value"), "citation": checked, "passed": passed}


def passage(bridge, pins, corpus, revision, query, gold):
    expected_run = gold["run"]
    span = byte_span(corpus[expected_run], gold["pointer"], gold["value"])
    for hit in bridge.search(query, namespace="merlin", limit=2)["hits"]:
        run = next((k for k, ref in pins.items() if ref == hit["source_ref"]), None)
        if run is None:
            raise ValueError("unrecognized source")
        start, end = hit["start_byte"], hit["end_byte"]
        raw = corpus[run][start:end]
        if (not 0 <= start < end <= len(corpus[run]) or raw != hit["text"].encode()
                or hashlib.sha256(raw).hexdigest() != hit["excerpt_sha256"]
                or hit["source_version"] != revision):
            raise ValueError("passage failed immutable byte/version check")
        if run == expected_run and start <= span["start_byte"] and end >= span["end_byte"]:
            return True
    return False


def measure(candidate_root, baseline_bridge):
    raw = PROTOCOL.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROTOCOL_HASH:
        raise ValueError("preregistration changed")
    protocol = json.loads(raw)
    for path, blob in protocol["code_blobs"].items():
        pinned(baseline_bridge if path == "base" else candidate_root / path, blob)
    corpus = {run: pinned(candidate_root / path, blob) for run, (path, blob) in protocol["sources"].items()}
    for case in protocol["cases"]:
        gold = case["expected"]
        if "run" in gold:
            byte_span(corpus[gold["run"]], gold["pointer"], gold["value"])
    sys.path[:0] = [str(candidate_root / "python"), str(candidate_root / "scripts/merlin")]
    import ask_receipt
    from evaluate_multirun_receipts import index_sources
    from merlin.project_registry import MerlinRegistry
    from dot_ai_os.bridge import DotContextBridge
    module_spec = importlib.util.spec_from_file_location("frozen_base_bridge", baseline_bridge)
    baseline = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(baseline)
    results = []
    with tempfile.TemporaryDirectory() as directory:
        registry = MerlinRegistry(Path(directory))
        candidate = DotContextBridge(registry)
        candidate.initialize()
        pins = index_sources(candidate, {"revision": protocol["source_revision"], "sources": protocol["sources"]})
        base = baseline.DotContextBridge(registry)
        for case in protocol["cases"]:
            question, gold = case["question"], case["expected"]
            bound = ask_receipt.ask(candidate, pins, question)
            with patch.object(ask_receipt, "answer", partial(ask_receipt.answer, bind_run=False)):
                unbound = ask_receipt.ask(candidate, pins, question)
            row = {"id": case["id"], "expected": gold["disposition"],
                   "first_hit": check_answer(unbound, gold, pins, corpus),
                   "run_bound": check_answer(bound, gold, pins, corpus)}
            if "run" in gold:
                row["lexical_top_two_covers_oracle"] = {name: passage(bridge, pins, corpus, protocol["source_revision"], question, gold)
                                                        for name, bridge in (("base", base), ("candidate", candidate))}
            results.append(row)
    totals = {arm: sum(row[arm]["passed"] for row in results) for arm in ("first_hit", "run_bound")}
    fixed = [row["id"] for row in results if row["run_bound"]["passed"] and not row["first_hit"]["passed"]]
    regressed = [row["id"] for row in results if row["first_hit"]["passed"] and not row["run_bound"]["passed"]]
    positive = [row for row in results if "lexical_top_two_covers_oracle" in row]
    passage_totals = {arm: sum(row["lexical_top_two_covers_oracle"][arm] for row in positive)
                      for arm in ("base", "candidate")}
    return {"schema": "merlin-pr179-frozen-receipt-result/1", "protocol_sha256": PROTOCOL_HASH,
            "base_commit": protocol["base_commit"], "candidate_commit": protocol["candidate_commit"],
            "source_revision": protocol["source_revision"], "cases": len(results), "exact_decisions": totals,
            "expected_actions": dict(Counter(row["expected"] for row in results)),
            "corrected_cases": fixed, "newly_failed_cases": regressed,
            "differential_gate_passed": bool(fixed and not regressed),
            "passage_oracle_cases": len(positive), "top_two_exact_passages": passage_totals,
            "results": results, "scope": "two_pinned_receipts_offline_source_aware_controlled_trial"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", required=True, type=Path, help="Checkout at the frozen PR head")
    parser.add_argument("--baseline-bridge", required=True, type=Path, help="dot_ai_os/bridge.py from the frozen base")
    args = parser.parse_args()
    print(json.dumps(measure(args.candidate_root.resolve(), args.baseline_bridge.resolve()), indent=2, sort_keys=True))
