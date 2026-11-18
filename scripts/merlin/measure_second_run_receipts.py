"""Score run-bound questions against the original bytes of two nested receipts."""
import argparse
from functools import partial
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch

from measure_pr179_receipts import HERE, check_answer, pinned


def measure(candidate_root, fixture="second-run-receipts.json", implementation=None):
    raw = (HERE / "tests/fixtures" / fixture).read_bytes()
    protocol = json.loads(raw)
    original = json.loads((HERE / "tests/fixtures/pr179-fresh-receipts-v1.json").read_bytes())
    for path, blob in original["code_blobs"].items():
        if path != "base":
            pinned(candidate_root / path, implementation["parser_blob"] if implementation and path == "scripts/merlin/ask_receipt.py" else blob)
    sys.path[:0] = [str(candidate_root / "python"), str(candidate_root / "scripts/merlin")]
    import ask_receipt
    from dot_ai_os.bridge import DotContextBridge
    from merlin.project_registry import MerlinRegistry

    cases = []
    corpus, offsets = {}, {}
    with tempfile.TemporaryDirectory() as directory:
        bridge = DotContextBridge(MerlinRegistry(Path(directory)))
        bridge.initialize()
        pins = {}
        for run, source in protocol["sources"].items():
            data = (HERE / source["path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != source["sha256"]:
                raise ValueError("historical source changed")
            marker, = re.finditer(rb'^  "receipt": (?=\{)', data, re.MULTILINE)
            start = marker.end()
            text = data[start:].decode()
            receipt, end = json.JSONDecoder().raw_decode(text)
            if receipt != json.loads(data)["receipt"] or str(receipt["run_id"]) != run:
                raise ValueError("run binding changed")
            corpus[run] = text[:end].encode()
            offsets[run] = start
            pins[run] = bridge.ingest(namespace="merlin", source_id=source["path"]+"#/receipt",
                title="Learning service run receipt", content=corpus[run],
                source_url="https://github.com/Mannyspiro/expert-robot/blob/"+protocol["source_revision"]+"/"+source["path"],
                source_version=protocol["source_revision"], epistemic="historical_report",
                captured_at="2026-11-18T00:00:00Z")["source_ref"]
        for case in protocol["cases"]:
            question = case["question"]
            row = {"question":question}
            for arm, bind in (("first_hit",False),("bound",True)):
                with patch.object(ask_receipt, "answer", partial(ask_receipt.answer,bind_run=bind)):
                    answer = ask_receipt.ask(bridge,pins,question)
                grade = check_answer(answer,case["expected"],pins,corpus)
                citation = grade["citation"]
                if citation:
                    start = offsets[citation["run"]]
                    citation["outer_start_byte"] = start + citation["start_byte"]
                    citation["outer_end_byte"] = start + citation["end_byte"]
                row[arm] = grade
            cases.append(row)
    return dict(protocol_sha256=hashlib.sha256(raw).hexdigest(),candidate_commit=implementation["commit"] if implementation else original["candidate_commit"],
                results=cases,passed={arm:sum(c[arm]["passed"] for c in cases) for arm in ("first_hit","bound")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root",required=True,type=Path)
    parser.add_argument("--fixture", choices=("second-run-receipts.json","separate-author-receipts.json"), default="second-run-receipts.json")
    parser.add_argument("--implementation", type=Path, help="Explicit revision and parser blob for a follow-up comparison")
    args = parser.parse_args()
    implementation = json.loads(args.implementation.read_bytes()) if args.implementation else None
    print(json.dumps(measure(args.candidate_root.resolve(),args.fixture,implementation),indent=2))
