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


def measure(candidate_root):
    raw = (HERE / "tests/fixtures/second-run-receipts.json").read_bytes()
    protocol = json.loads(raw)
    original = json.loads((HERE / "tests/fixtures/pr179-fresh-receipts-v1.json").read_bytes())
    for path, blob in original["code_blobs"].items():
        if path != "base":
            pinned(candidate_root / path, blob)
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
    return dict(protocol_sha256=hashlib.sha256(raw).hexdigest(),candidate_commit=original["candidate_commit"],
                results=cases,passed={arm:sum(c[arm]["passed"] for c in cases) for arm in ("first_hit","bound")})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root",required=True,type=Path)
    print(json.dumps(measure(parser.parse_args().candidate_root.resolve()),indent=2))
