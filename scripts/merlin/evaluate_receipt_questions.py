"""Replay frozen questions as plain text and check run, typed value and citation."""
import json
import tempfile
from collections import Counter
from pathlib import Path

from dot_ai_os.bridge import DotContextBridge
from merlin.project_registry import MerlinRegistry
from ask_receipt import ask
from evaluate_multirun_receipts import SUITE, index_sources


def evaluate():
    suite = json.loads(SUITE.read_text())
    counts = Counter()
    failed = []
    with tempfile.TemporaryDirectory() as directory:
        bridge = DotContextBridge(MerlinRegistry(Path(directory)))
        bridge.initialize()
        pins = index_sources(bridge, suite)
        for case in suite["cases"]:
            request, gold = case["request"], case["expected"]
            run = request["run_id"]
            question = f"Run {run}, {request['question']}"
            result = ask(bridge, pins, question)
            citation = None if gold["disposition"] == "abstain" else {
                "source_ref": pins[run], "pointer": request["pointer"]}
            if (result["disposition"] == gold["disposition"]
                    and result.get("value") == gold["value"]
                    and type(result.get("value")) is type(gold["value"])
                    and result.get("citation") == citation):
                counts["frozen_questions"] += 1
            else:
                failed.append(question)
        for question, disposition, value in [
            ("What operation ran?", "clarify_run", None),
            ("For the recovery run, what was the submission status?", "abstain", None),
            ("How many main shard tests ran for the Titan receipt?", "supported", 85),
            ("Did the main shard run 85 tests during the recovery run?", "contradicted", 136),
            ("For the learning run, did the main shard run fewer than 85 tests?", "clarify_field", None),
            ("What operation ran for run 100?", "abstain", None),
            ("What operation ran for the recovery run and the Titan run?", "clarify_field", None),
        ]:
            result = ask(bridge, pins, question)
            if result["disposition"] == disposition and result.get("value") == value:
                counts["boundary_questions"] += 1
            else:
                failed.append(question)
        titan = json.loads(SUITE.with_name("titan-retrieval-v1.json").read_text())
        for case in titan["cases"]:
            question = "Titan, " + case["question"]
            result = ask(bridge, pins, question)
            citation = None if case["pointer"] is None else {
                "source_ref": pins["44174486449"], "pointer": case["pointer"]}
            if (result["disposition"] == case["disposition"]
                    and result.get("value") == case["value"]
                    and type(result.get("value")) is type(case["value"])
                    and result.get("citation") == citation):
                counts["titan_regressions"] += 1
            else:
                failed.append(question)

        for question, disposition in [
            ("Titan, cryptographic security was not verified.", "supported"),
            ("Titan, the learner’s mastery was not updated.", "supported"),
            ("Titan, did replay not return the same canonical receipt?", "contradicted"),
            ("Recovery, what is the vector count?", "abstain"),
            ("What is the vector count?", "clarify_run"),
            ("Titan, were more than five structural vectors recorded?", "clarify_field"),
            ("Titan, the instructor's mastery was updated.", "clarify_field"),
            ("Titan, mastery was updated and security was verified.", "clarify_field"),
            ("Titan, cryptographic security was never independently verified.", "clarify_field"),
        ]:
            result = ask(bridge, pins, question)
            if result["disposition"] == disposition:
                counts["paraphrase_controls"] += 1
            else:
                failed.append(question)
        result = ask(bridge, pins, "Titan, what operation ran?", {"titan": tuple(pins)})
        if result.get("run_ids") == sorted(pins) and result["disposition"] == "clarify_run":
            counts["ambiguous_alias"] += 1
        else:
            failed.append("alias maps to two runs")
    return dict(passed=dict(counts), failures=failed)


if __name__ == "__main__":
    report = evaluate()
    print(json.dumps(report, indent=2))
    raise SystemExit(bool(report["failures"]))
