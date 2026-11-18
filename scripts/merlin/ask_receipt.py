"""Ask a bounded question about pinned Merlin run receipts, entirely offline.

PYTHONPATH=python python3 scripts/merlin/ask_receipt.py "How many tests ran in the main shard for the recovery run?"
"""
import argparse
import json
import re
import tempfile
from pathlib import Path

from merlin.project_registry import MerlinRegistry
from dot_ai_os.bridge import DotContextBridge
from evaluate_multirun_receipts import SUITE, answer, index_sources

# Explicit source catalog. An alias can resolve to several runs as history grows.
ALIASES = {"learning": ("44174486449",), "titan": ("44174486449",),
           "lms": ("44174486449",), "recovery": ("44151750942",)}
SELECTOR = r"(?:the )?(?:(?:run )?[0-9]+|(?:learning|titan|lms|recovery)(?: run| receipt)?)"
FIELDS = (
    (r"how many (?:main shard tests ran|tests ran in the main shard)", "/tests/tests"),
    (r"how many operation tests ran", "/recovery_operation_tests/tests"),
    (r"what (?:was|is) the submission status", "/demo/submission_status"),
    (r"what operation ran", "/operation"),
    (r"what numeric grade was awarded", "/demo/grade"),
    (r"was (?:the recorded security verification true|cryptographic security verified)",
     "/demo/cryptographic_security_verified"),
)


def ask(bridge, pins, question, aliases=ALIASES):
    text = " ".join(question.lower().strip().rstrip("?.").split())
    prefix = re.fullmatch(rf"(?:for |in )?({SELECTOR}),\s*(.+)", text)
    suffix = re.fullmatch(rf"(.+) (?:in|for|during) ({SELECTOR})", text)
    if prefix:
        selector, body = prefix.groups()
    elif suffix:
        body, selector = suffix.groups()
    else:
        body, selector = text, None

    claim = re.fullmatch(r"did the main shard run ([0-9]{1,9}) tests", body)
    pointer = next((path for pattern, path in FIELDS if re.fullmatch(pattern, body)), None)
    if claim:
        pointer = "/tests/tests"
    if pointer is None:
        return {"disposition": "clarify_field",
                "message": "Which field do you mean: main shard test count, operation test count, "
                           "operation, submission status, numeric grade, or security verification?"}
    if selector is None:
        candidates = sorted(pins)
    else:
        key = selector.removeprefix("the ").removeprefix("run ").split()[0]
        if key.isdecimal():
            candidates = [key] if key in pins else []
        else:
            candidates = sorted(set(aliases.get(key, ())).intersection(pins))
    if not candidates:
        return {"disposition": "abstain", "reason": "unknown_run"}
    if len(candidates) > 1:
        return {"disposition": "clarify_run", "message": "Which run do you mean?",
                "run_ids": candidates}

    run = candidates[0]
    request = {"question": body, "run_id": run, "pointer": pointer}
    if claim:
        request["claim"] = int(claim.group(1))
    elif pointer == "/demo/cryptographic_security_verified":
        request["claim"] = True
    result = answer(bridge, pins, request)
    return dict(result, run_id=run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    args = parser.parse_args()
    suite = json.loads(SUITE.read_text())
    with tempfile.TemporaryDirectory() as directory:
        bridge = DotContextBridge(MerlinRegistry(Path(directory)))
        bridge.initialize()
        result = ask(bridge, index_sources(bridge, suite), args.question)
        if result.get("citation"):
            path = suite["sources"][result["run_id"]][0]
            result["citation"]["url"] = (
                f"https://github.com/Mannyspiro/expert-robot/blob/{suite['revision']}/{path}")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
