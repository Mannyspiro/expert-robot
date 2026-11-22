"""SEAL-inspired constrained self-generated examples for local adapter training.

An existing local language model may PROPOSE tiny integer arithmetic examples.
An independent deterministic oracle checks every answer before using data.
The model cannot write code, execute tools, choose a holdout, change permissions,
train/publish weights or authorize its own promotion. Proposals are untrusted.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

SCHEMA = "merlin-verified-proposed-arithmetic/1"
MAX_EXAMPLES = 16
MIN_EXAMPLES = 2


def proposal_prompt():
    return (
        "Produce ONLY a JSON object, no markdown. Use schema "
        "'merlin-arithmetic-candidate/1' and an examples array containing "
        "between 2 and 8 unique integer arithmetic problems. Each example "
        "must have exactly 'operator', 'a', 'b', 'answer'. Operators may be "
        "'add', 'sub', or 'mul'; a and b must be integers in 0..100; "
        "answer must be the exact integer result. Do not use a tool or "
        "reference a test set. Output the JSON object only."
    )


def _question(operator, a, b):
    name = {"add": "plus", "sub": "minus", "mul": "times"}[operator]
    return "Compute " + str(a) + " " + name + " " + str(b) + ". Respond with only the integer."


def verify_proposal(raw, *, heldout_questions: Iterable[str] = ()):
    if not isinstance(raw, str) or not 1 <= len(raw.encode("utf-8")) <= 8192:
        raise ValueError("bounded model JSON proposal required")
    parsed = json.loads(raw)
    if type(parsed) is not dict or set(parsed) != {"schema", "examples"}:
        raise ValueError("exact proposal object required")
    if parsed["schema"] != "merlin-arithmetic-candidate/1":
        raise ValueError("unsupported proposal version")
    rows = parsed["examples"]
    if type(rows) is not list or not MIN_EXAMPLES <= len(rows) <= MAX_EXAMPLES:
        raise ValueError("bounded candidate count required")
    heldout = {x.strip().casefold() for x in heldout_questions}
    if len(heldout) > 128:
        raise ValueError("bounded hidden reference set required")
    seen = set()
    training = []
    for index, sample in enumerate(rows):
        if type(sample) is not dict or set(sample) != {"operator", "a", "b", "answer"}:
            raise ValueError("candidate must have exact typed fields")
        op = sample["operator"]
        if op not in ("add", "sub", "mul") or not isinstance(op, str):
            raise ValueError("only exact arithmetic operators allowed")
        a, b, answer = sample["a"], sample["b"], sample["answer"]
        if any(type(v) is not int or v < 0 or v > 100 for v in (a, b)):
            raise ValueError("bounded exact integer operands required")
        if type(answer) is not int:
            raise ValueError("model-generated label must be an integer")
        oracle = {"add": lambda: a+b, "sub": lambda: a-b,
                  "mul": lambda: a*b}[op]()
        if answer != oracle:
            raise ValueError("independent arithmetic oracle rejected model label")
        question = _question(op, a, b)
        key = question.casefold()
        if key in seen or key in heldout:
            raise ValueError("candidate duplicates or leaks heldout question")
        seen.add(key)
        training.append({"id": "selfgen." + str(index+1),
                         "question": question, "answer": str(oracle)})
    original_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return {"schema": SCHEMA, "source_class":"untrusted_model_proposal",
            "independent_oracle":"python-exact-integer-arithmetic",
            "proposal_sha256":original_sha,
            "accepted_count":len(training),
            "training_rows":training,
            "heldout_labels_exposed_to_proposer":False,
            "model_weights_updated":False,
            "production_qualified":False}


def write_verified_train_json(report, output: Path):
    if type(report) is not dict or report.get("schema") != SCHEMA:
        raise ValueError("verified report required")
    if not isinstance(output, Path) or not output.is_absolute():
        raise ValueError("absolute output path required")
    if not output.parent.is_dir() or output.parent.is_symlink() or output.exists():
        raise ValueError("new output under existing private directory required")
    rows = report.get("training_rows")
    if type(rows) is not list or not MIN_EXAMPLES <= len(rows) <= MAX_EXAMPLES:
        raise ValueError("validated bounded training examples required")
    # Revalidate the serialized roundtrip without trusting an edited report.
    for row in rows:
        if (type(row) is not dict or set(row) != {"id", "question", "answer"}
                or not all(isinstance(v,str) and 0<len(v)<=512 for v in row.values())):
            raise ValueError("malformed checked training row")
    payload = (json.dumps(rows,sort_keys=True,separators=(",",":"),
                          ensure_ascii=False)+"\n").encode()
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(payload)
        file.flush()
        os.fsync(file.fileno())
    return {"training_file_sha256":hashlib.sha256(payload).hexdigest(),
            "training_count":len(rows),
            "model_weights_updated":False}


__all__ = ["SCHEMA","proposal_prompt","verify_proposal","write_verified_train_json"]
