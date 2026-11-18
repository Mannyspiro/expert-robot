"""Offline benchmark for structured receipt questions. Run with PYTHONPATH=python.

The caller supplies the run ID and object-field pointer. The candidate receives
only that request and source pins. It never sees the expected answers.
"""
import hashlib
import json
import re
import tempfile
from collections import Counter
from pathlib import Path

from dot_ai_os.bridge import DotContextBridge
from merlin.project_registry import MerlinRegistry

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "config/merlin/evals/titan-multirun-v1.json"


def index_sources(bridge, suite):
    pins = {}
    for run_id, (path, blob) in suite["sources"].items():
        raw = (ROOT / path).read_bytes()
        if hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() != blob:
            raise ValueError(f"Source changed: {path}")
        if json.loads(raw)["run_id"] != run_id:
            raise ValueError(f"Run binding changed: {path}")
        url = f"https://github.com/Mannyspiro/expert-robot/blob/{suite['revision']}/{path}"
        pins[run_id] = bridge.ingest(
            namespace="merlin", source_id=path, title=Path(path).stem,
            content=raw, source_url=url, source_version=suite["revision"],
            epistemic="historical_report", captured_at="2026-11-18T00:00:00Z",
        )["source_ref"]
    return pins


def answer(bridge, pins, request, *, bind_run=True):
    """Resolve bound lookups by exact receipt reference and unbound controls by first hit."""
    abstain = {"disposition": "abstain", "value": None, "citation": None}
    run_id = request["run_id"]
    pointer = request["pointer"]
    if not re.fullmatch(r"(?:/[A-Za-z0-9_]+)+", pointer):
        raise ValueError("Expected a slash-separated object-field path")
    if bind_run:
        ref = pins.get(run_id)
        if not ref or not ref["logical_path"].startswith("context/merlin/"):
            return abstain
    else:
        query = " ".join((run_id, request["question"], pointer.replace("/", " ")))
        hits = bridge.search(query, namespace="merlin")["hits"]
        if not hits:
            return abstain
        ref = hits[0]["source_ref"]
    page = bridge.fetch(ref, length_bytes=16000)
    if page["next_start_byte"] is not None:
        return abstain  # This bounded probe accepts complete small receipts only.
    node = json.loads(page["text"])
    if bind_run and node.get("run_id") != run_id:
        return abstain
    for field in pointer[1:].split("/"):
        if not isinstance(node, dict) or field not in node:
            return abstain
        node = node[field]
    if not isinstance(node, (str, bool, int, float)):
        return abstain
    agrees = "claim" not in request or (
        type(node) is type(request["claim"]) and node == request["claim"])
    return {"disposition": "supported" if agrees else "contradicted", "value": node,
            "citation": {"source_ref": ref, "pointer": pointer}}


def evaluate(bridge, pins, cases, bind_run):
    counts = Counter()
    failures = []
    for index, case in enumerate(cases, 1):
        request = case["request"]
        result = answer(bridge, pins, request, bind_run=bind_run)
        gold = case["expected"]
        citation = None if gold["disposition"] == "abstain" else {
            "source_ref": pins[request["run_id"]], "pointer": request["pointer"]}
        if (result == dict(gold, citation=citation)
                and type(result["value"]) is type(gold["value"])):
            counts[gold["disposition"]] += 1
        else:
            failures.append(index)
    return {"passed": dict(counts), "failed_cases": failures}


def main():
    suite = json.loads(SUITE.read_text())
    with tempfile.TemporaryDirectory() as directory:
        bridge = DotContextBridge(MerlinRegistry(Path(directory)))
        bridge.initialize()
        pins = index_sources(bridge, suite)
        baseline = evaluate(bridge, pins, suite["cases"], False)
        candidate = evaluate(bridge, pins, suite["cases"], True)
        print(json.dumps({"first_hit": baseline, "bound_run": candidate}, indent=2))
        return int(bool(candidate["failed_cases"]))


if __name__ == "__main__":
    raise SystemExit(main())
