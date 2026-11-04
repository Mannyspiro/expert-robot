"""Persist cross-domain benchmark receipts and theorem-to-engineering links."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from merlin.engineering_project_store import project_hash
from merlin.observatory_benchmarks import project_fixture
from merlin.proof_observatory import ProofObservatory


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
            receipt,
            theorem_dag,
            "merlin-observatory-fixture",
            revision_hash,
            object_ids,
        )
        return {
            "receipt_sha256": receipt["receipt_sha256"],
            "theorem_dag_sha256": theorem_dag["dag_sha256"],
            "engineering_revision_sha256": revision_hash,
            "links_created": len(links),
            "chain_verified": store.verify_chain(),
        }
    finally:
        store.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Link benchmark evidence to theorem DAG and Engineering IR")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--dag", required=True)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    print(json.dumps(link_benchmark_artifacts(args.receipt, args.dag, args.database), sort_keys=True))
