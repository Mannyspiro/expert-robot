"""Persist cross-domain benchmark receipts and theorem-to-engineering links."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from merlin.engineering_project_store import project_hash
from merlin.observatory_benchmarks import project_fixture
from merlin.observatory_integrity import verify_database
from merlin.proof_observatory import ProofObservatory
from merlin.theorem_dag import extract_theorem_dag


def link_benchmark_artifacts(receipt_path: str, dag_path: str, database_path: str) -> dict:
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    theorem_dag = json.loads(Path(dag_path).read_text(encoding="utf-8"))
    project = project_fixture()
    revision_hash = project_hash(project)
    object_ids = {
        "geometry": ["cartesian", "sheared", "rotated"],
        "xmg": [
            "glyph:" + receipt["domains"]["xmg"]["expression_fingerprint"],
            "glyph:" + receipt["domains"]["xmg"]["normal_form_fingerprint"],
        ],
        "equation_atlas": [
            "equation:" + item for item in receipt["domains"]["equation_atlas"]["symbolic_check_ids"]
        ],
        "cad": ["assembly:observatory-separated-fixture"],
    }
    store = ProofObservatory(database_path)
    try:
        links = store.record_benchmark_theorem_links(
            receipt, theorem_dag, "merlin-observatory-fixture", revision_hash, object_ids,
        )
    finally:
        store.close()
    integrity = verify_database(database_path, theorem_dag)
    return {
        "receipt_sha256": receipt["receipt_sha256"],
        "theorem_dag_sha256": theorem_dag["dag_sha256"],
        "engineering_revision_sha256": revision_hash,
        "links_created": len(links),
        "integrity": integrity,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Link benchmark evidence and verify all Observatory evidence")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--dag", required=True)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    summary = link_benchmark_artifacts(args.receipt, args.dag, args.database)
    print(json.dumps(summary, sort_keys=True))
    if not summary["integrity"]["ok"]:
        raise SystemExit(2)
