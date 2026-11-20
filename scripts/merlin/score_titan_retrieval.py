"""Score independent JSON predictions against the frozen LMS/Titan receipt.

Use --questions to export blind prompts. Score a JSON object keyed by question
ID. Each answer has disposition, value and citation. A citation contains the
source path, commit and JSON pointer. Abstentions have null value and citation.
The exit status is zero only for a complete passing submission.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "config/merlin/evals/titan-retrieval-v1.json"


def score(suite, answers):
    source = suite["source"]
    raw = (ROOT / source["path"]).read_bytes()
    header = f"blob {len(raw)}\0".encode()
    if hashlib.sha1(header + raw).hexdigest() != source["git_blob"]:
        raise ValueError("Frozen receipt bytes changed")
    receipt = json.loads(raw)
    if not isinstance(answers, dict):
        raise ValueError("Expected an object keyed by question ID")
    failures = {}
    totals = {}
    for case in suite["cases"]:
        key = case["id"]
        disposition = case["disposition"]
        pointer = case["pointer"]
        citation = None
        if pointer is not None:
            node = receipt
            for field in pointer[1:].split("/"):
                node = node[field]
            if type(node) is not type(case["value"]) or node != case["value"]:
                raise ValueError(f"Reference disagrees with receipt at {pointer}")
            citation = dict(path=source["path"], commit=source["commit"], pointer=pointer)
        expected = dict(disposition=disposition, value=case["value"], citation=citation)
        prediction = answers.get(key)
        errors = [field for field, value in expected.items()
                  if not isinstance(prediction, dict) or field not in prediction
                  or type(prediction[field]) is not type(value) or prediction[field] != value]
        counts = totals.setdefault(disposition, {"passed": 0, "total": 0})
        counts["total"] += 1
        if errors:
            failures[key] = errors
        else:
            counts["passed"] += 1
    extra = sorted(set(answers) - {case["id"] for case in suite["cases"]})
    return dict(passed=not failures and not extra, by_disposition=totals,
                failures=failures, unexpected_ids=extra)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--questions", action="store_true")
    group.add_argument("--answers", type=Path)
    args = parser.parse_args()
    suite = json.loads(SUITE.read_text())
    if args.questions:
        print(json.dumps([{k: row[k] for k in ("id", "question")} for row in suite["cases"]], indent=2))
        return 0
    result = score(suite, json.loads(args.answers.read_text()))
    print(json.dumps(result, indent=2))
    return int(not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
