"""Measure local context-bridge passage retrieval. Run with PYTHONPATH=python."""
import json
import tempfile
from pathlib import Path

from dot_ai_os.bridge import DotContextBridge
from merlin.project_registry import MerlinRegistry
from score_titan_retrieval import ROOT, SUITE, score


def main():
    suite = json.loads(SUITE.read_text())
    score(suite, {})  # Validate frozen bytes and reference values before probing.
    source = suite["source"]
    raw = (ROOT / source["path"]).read_bytes()
    with tempfile.TemporaryDirectory() as directory:
        bridge = DotContextBridge(MerlinRegistry(Path(directory)))
        bridge.initialize()
        ref = bridge.ingest(namespace="merlin", source_id="lms-titan-receipt",
                            title="Merlin Learning Titan validation receipt", content=raw,
                            source_url=f"https://github.com/Mannyspiro/expert-robot/blob/{source['commit']}/{source['path']}",
                            source_version=source["commit"], epistemic="historical_report",
                            captured_at="2026-11-18T00:00:00Z")["source_ref"]
        for case in suite["cases"]:
            hits = bridge.search(case["question"])["hits"]
            found = None
            if case["pointer"]:
                field = case["pointer"].split("/")[-1]
                needle = (json.dumps(field) + ": " + json.dumps(case["value"])).encode()
                if raw.count(needle) != 1:
                    raise ValueError(f"Ambiguous reference span for {field}")
                start = raw.index(needle)
                found = any(hit["source_ref"] == ref and hit["source_version"] == source["commit"]
                            and hit["start_byte"] <= start and hit["end_byte"] >= start + len(needle)
                            for hit in hits)
            print(json.dumps(dict(id=case["id"], hits=len(hits), expected_span_returned=found)))


if __name__ == "__main__":
    main()
