"""Ask a bounded question about pinned Merlin run receipts, entirely offline.

PYTHONPATH=python python3 scripts/merlin/ask_receipt.py "How many tests ran in the main shard for the recovery run?"
"""
import argparse
from copy import deepcopy
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
    (r"how many tests did the main shard (?:log|record|run)", "/tests/tests"),
    (r"what was the main shard's test (?:tally|count)", "/tests/tests"),
    (r"how many main[- ]shard tests does the receipt (?:show|record)", "/tests/tests"),
    (r"how many operation tests ran", "/recovery_operation_tests/tests"),
    (r"what (?:was|is) the (?:submission (?:status|state)|(?:recorded )?(?:status|state) of "
     r"the (?:(?:synthetic )?learner's )?submission)", "/demo/submission_status"),
    (r"how many (?:structural )?(?:test )?vectors were (?:recorded|used)", "/demo/vector_count"),
    (r"what (?:was|is) the (?:structural )?vector count", "/demo/vector_count"),
    (r"what operation ran", "/operation"),
    (r"what (?:numeric )?grade (?:was awarded|did the reviewer award (?:this|the) learner)",
     "/demo/grade"),
    (r"how many milliseconds did the second lab execution take", "/demo/second_execution_ms"),
    (r"was (?:the recorded security verification true|cryptographic security verified)",
     "/demo/cryptographic_security_verified"),
)


# Match complete propositions so a different actor, comparison, or negation
# cannot silently change the meaning of a source-bound claim.
BOOLEAN_CLAIMS = (
    (r"(?:the demo receipt says )?cryptographic security was (?P<negative>not )?verified",
     "/demo/cryptographic_security_verified"),
    (r"(?:the learner's )?mastery was (?P<negative>not )?updated(?: during this run)?",
     "/demo/mastery_updated"),
    (r"did replay (?P<negative>not )?return (?:an equal|the same|an identical) canonical receipt",
     "/demo/canonical_receipt_replay_equal"),
)


def resolve_field(body):
    count = re.fullmatch(r"did the main shard run ([0-9]{1,9}) tests", body)
    if count:
        return "/tests/tests", int(count.group(1))
    proposition = body.removesuffix(". is this assertion supported or contradicted")
    for pattern, path in BOOLEAN_CLAIMS:
        match = re.fullmatch(pattern, proposition)
        if match:
            return path, match.group("negative") is None
    for pattern, path in FIELDS:
        if re.fullmatch(pattern, body):
            return path, True if path == "/demo/cryptographic_security_verified" else None
    return None, None


def _route(pins, question, aliases):
    text = " ".join(question.lower().replace("’", "'").strip().rstrip("?.").split())
    prefix = re.fullmatch(rf"(?:for |in )?({SELECTOR}),\s*(.+)", text)
    suffix = re.fullmatch(rf"(.+) (?:in|for|during) ({SELECTOR})", text)
    if prefix:
        selector, body = prefix.groups()
    elif suffix:
        body, selector = suffix.groups()
    else:
        body, selector = text, None

    # Recognize complete embedded-selector questions before resolving their field.
    # Keeping full matches preserves uncertainty for comparisons and modified claims.
    embedded = (
        (rf"where did the submission for ({SELECTOR}) stand when the receipt was recorded",
         "what was the submission status"),
        (rf"what numeric grade did ({SELECTOR}) receive", "what numeric grade was awarded"),
    )
    for pattern, canonical in embedded:
        match = re.fullmatch(pattern, text)
        if match:
            selector, body = match.group(1), canonical
            break
    assertion = re.fullmatch(
        rf"i have ([0-9]{{1,9}}) main[- ]shard tests written down for ({SELECTOR})\. is that right", text)
    if assertion:
        count, selector = assertion.groups()
        body = f"did the main shard run {count} tests"
    if selector is None:
        body = body.removesuffix(" for that run")

    pointer, claim = resolve_field(body)
    if pointer is None:
        return {"disposition": "clarify_field",
                "message": "Which field do you mean: main shard test count, operation test count, "
                           "operation, submission status, grade, replay equality, vector count, mastery, "
                           "execution time, or security verification?"}
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
    request = {"question": body, "pointer": pointer}
    if claim is not None:
        request["claim"] = claim
    return candidates, request


def ask(bridge, pins, question, aliases=ALIASES):
    route = _route(pins, question, aliases)
    if isinstance(route, dict):
        return route
    candidates, request = route
    if len(candidates) > 1:
        return {"disposition": "clarify_run", "message": "Which run do you mean?",
                "run_ids": candidates}
    run = candidates[0]
    return dict(answer(bridge, pins, dict(request, run_id=run)), run_id=run)


class ReceiptConversation:
    """One caller-owned dialogue over a snapshot of the caller's allowed receipt refs."""

    def __init__(self, bridge, versions):
        self.bridge = bridge
        self.versions = deepcopy(versions)
        for refs in self.versions.values():
            if not refs or any(type(v) is not int or v < 1 or type(ref.get("version")) is not int
                               or v != ref["version"] for v, ref in refs.items()):
                raise ValueError("receipt versions must match their pinned references")
        self.pending = None

    def turn(self, text):
        reply = text.strip().lower().rstrip(".?!").strip()
        if self.pending:
            candidates, request, requested_version = self.pending
            combined = re.fullmatch(r"(?:yes,?\s+)?run ([0-9]+),?\s+(?:version |v)([0-9]{1,9})", reply)
            if combined:
                run, explicit = combined.groups()
                self.pending = None
                if run not in candidates:
                    return {"disposition": "abstain", "reason": "unknown_run"}
                return self._select([run], request, int(explicit))
            run_reply = re.fullmatch(r"(?:run\s+)?([0-9]+)", reply)
            version_reply = re.fullmatch(r"(?:version\s+|v)([0-9]{1,9})", reply)
            if len(candidates) > 1 and run_reply:
                run = run_reply.group(1)
                if run not in candidates:
                    self.pending = None
                    return {"disposition": "abstain", "reason": "unknown_run"}
                return self._select([run], request, requested_version)
            if len(candidates) == 1 and (version_reply or run_reply and reply.isdecimal() and len(reply) <= 9):
                return self._select(candidates, request, int((version_reply or run_reply).group(1)))
        self.pending = None
        version = None
        if reply == "how many tests were on the main shard":
            text = "how many main shard tests ran"
        count = re.fullmatch(r"did the main shard have ([0-9]{1,9}) tests in the (first|second) receipt(?: too)?", reply)
        lookup = re.fullmatch(r"can you check the (first|second) receipt for the test count", reply)
        if count:
            text = f"did the main shard run {count.group(1)} tests"
            version = {"first":1, "second":2}[count.group(2)]
        elif lookup:
            text = "how many main shard tests ran"
            version = {"first":1, "second":2}[lookup.group(1)]
        route = _route(self.versions, text, ALIASES)
        return route if isinstance(route, dict) else self._select(*route, version=version)

    def _select(self, candidates, request, version=None):
        self.pending = (candidates, request, version)
        if len(candidates) > 1:
            return {"disposition": "clarify_run", "run_ids": list(candidates)}
        run = candidates[0]
        refs = self.versions[run]
        if version is None and len(refs) > 1:
            return {"disposition": "clarify_version", "run_id": run, "versions": sorted(refs)}
        self.pending = None
        ref = refs.get(version) if version is not None else next(iter(refs.values()))
        if ref is None:
            return {"disposition": "abstain", "reason": "unknown_version"}
        return dict(answer(self.bridge, {run:ref}, dict(request, run_id=run)), run_id=run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--follow-up", action="append", default=[], help="Reply to a clarification in this conversation")
    args = parser.parse_args()
    suite = json.loads(SUITE.read_text())
    with tempfile.TemporaryDirectory() as directory:
        bridge = DotContextBridge(MerlinRegistry(Path(directory)))
        bridge.initialize()
        pins = index_sources(bridge, suite)
        if args.follow_up:
            dialogue = ReceiptConversation(bridge, {run:{ref["version"]:ref} for run,ref in pins.items()})
            result = dialogue.turn(args.question)
            for reply in args.follow_up:
                result = dialogue.turn(reply)
        else:
            result = ask(bridge, pins, args.question)
        if result.get("citation"):
            path = suite["sources"][result["run_id"]][0]
            result["citation"]["url"] = (
                f"https://github.com/Mannyspiro/expert-robot/blob/{suite['revision']}/{path}")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
