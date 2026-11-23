#!/usr/bin/env python3
"""Exhaustive *metadata* review of the pinned OpenAI math manuscript catalogue.

This audit is computationally cheap and has NO network access. It verifies
coverage and detects false provenance/qualification flags, NOT mathematical truth.
"""
from collections import Counter
from copy import deepcopy
import argparse
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "docs/openai-math-all-manuscripts-index-2026-10-09.json"
FORMAL = ROOT / "docs/openai-math-catalog-2026-10-09.json"
HEAD = "fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb"


class UnqualifiedEvidence(ValueError):
    pass


def require(x, msg):
    if not x:
        raise UnqualifiedEvidence(msg)


def audit(index, formal):
    require(index.get("schema_version") == 1, "index schema")
    require(index.get("source_repo") == "openai/math", "source repo")
    require(index.get("source_commit") == HEAD == formal.get("source_commit"), "source SHA")
    require(index.get("contents_blob_sha") ==
            "2c68c086fff36a5806c936ad1659cf1a8d0b6dd9", "contents blob")
    require(index.get("formalization_yaml_blob_sha") ==
            formal.get("formalization_yaml_blob_sha"), "formal index blob")
    families, papers, formal_papers = (
        index.get("families"), index.get("manuscripts"), formal.get("papers"))
    require(isinstance(families, list) and len(families) == 372, "family coverage")
    require(isinstance(papers, list) and len(papers) == 719, "manuscript coverage")
    require(isinstance(formal_papers, list) and len(formal_papers) == 173, "Lean sources")
    require(index.get("readme_manuscript_claim") == 719, "reported paper count")
    require(index.get("contents_pdf_links") == 718, "contents link count")
    require(index.get("extra_formalization_pdf_links") == 1, "extra source count")
    require(index.get("manifest_manuscripts") == 719, "indexed paper count")
    require(index.get("independently_verified_mathematical_arguments") == 0,
            "false mathematics verification")
    require(index.get("formal_catalogue_matched_manuscripts") == 173,
            "formal-source count")
    idset = set()
    familycounts = Counter()
    for f in families:
        fid = f.get("id")
        require(isinstance(fid, str) and re.fullmatch(r"[0-9]{3}", fid),
                "invalid family number")
        require(fid not in idset and bool(f.get("title")), "duplicate or empty family")
        idset.add(fid)
        require(type(f.get("paper_count")) is int and f["paper_count"] >= 0,
                "invalid family paper count")
    manifest = {}
    for p in papers:
        path = p.get("pdf_path")
        require(isinstance(path, str) and path.startswith("preprints/")
                and path.endswith(".pdf") and ".." not in path,
                "unsafe/malformed path")
        require(path not in manifest, "duplicate PDF")
        manifest[path] = p
        require(isinstance(p.get("title"), str) and bool(p["title"].strip()),
                "paper title")
        family = p.get("family_id")
        require(family is None or family in idset, "unknown family")
        familycounts[family] += 1
        require(p.get("mathematical_argument_verified") is False,
                "mathematical validity fabricated")
        require(p.get("review_state") == "metadata_screened_only",
                "unsupported review status")
        require(type(p.get("relevance_score")) is int and p["relevance_score"] >= 0,
                "invalid ranking")
        require(isinstance(p.get("relevance_terms"), list), "ranking trace")
    for f in families:
        require(f["paper_count"] == familycounts[f["id"]], "family count mismatch")
    require(familycounts[None] == 1, "expected one out-of-contents Lean PDF")
    formal_paths = set()
    for fp in formal_papers:
        path = fp.get("source_pdf_path", "")
        require(isinstance(path, str) and path.startswith("../preprints/"),
                "invalid formal index paper")
        path = path[3:]
        require(path in manifest, "missing formalized source")
        formal_paths.add(path)
    require(len(formal_paths) == 173, "duplicate formal source")
    require({k for k, p in manifest.items() if p["formal_catalogue_match"]}
            == formal_paths, "false or missing formal match")
    linked_contents_paths = {
        p for p, row in manifest.items() if row["family_id"] is not None
    }
    expected_unlisted = {
        (p["title"], p["source_pdf_path"][3:])
        for p in formal_papers
        if p["source_pdf_path"][3:] not in linked_contents_paths
    }
    recorded_unlisted = {
        (p["title"], p["pdf_path"])
        for p in index.get("unlisted_formalization_sources", [])
    }
    require(expected_unlisted == recorded_unlisted,
            "outside-CONTENTS source mismatch")
    require(all(row.get("state") == "upstream_declared_not_imported"
                for row in formal.get("declared_results", [])), "false import claim")
    require(len(formal.get("declared_results", [])) == 200, "Lean declaration count")
    ranked = sorted(papers, key=lambda p:
                    (-int(p["formal_catalogue_match"]), -p["relevance_score"],
                     p["pdf_path"]))
    return {
        "schema_version": 1,
        "experiment": "openai-math-all-manuscripts-cheap-screen-v1",
        "source_commit": HEAD,
        "families_screened": len(families),
        "manuscripts_screened": len(papers),
        "formalization_source_manuscripts": len(formal_paths),
        "upstream_main_result_declarations_recorded":
            len(formal["declared_results"]),
        "manuscripts_without_listed_Lean_source": len(papers) - len(formal_paths),
        "pdfs_read_or_reproven": 0,
        "formal_results_independently_compiled": 0,
        "mathematical_claims_independently_reproven": 0,
        "network_operations": 0,
        "top_source_priorities": [
            {"title": p["title"], "score": p["relevance_score"]}
            for p in ranked[:25]
        ],
        "production_or_promotion_authority": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()
    index = json.loads(PAPERS.read_text(encoding="utf-8"))
    formal = json.loads(FORMAL.read_text(encoding="utf-8"))
    report = audit(index, formal)
    bad = deepcopy(index)
    bad["manuscripts"][0]["mathematical_argument_verified"] = True
    try:
        audit(bad, formal)
    except UnqualifiedEvidence:
        pass
    else:
        raise AssertionError("false formal validity was admitted")
    bad = deepcopy(index)
    bad["manuscripts"][-1]["formal_catalogue_match"] = False
    try:
        audit(bad, formal)
    except UnqualifiedEvidence:
        pass
    else:
        raise AssertionError("source-to-formal mismatch was admitted")
    bad = deepcopy(index)
    bad["manuscripts"][1]["pdf_path"] = bad["manuscripts"][0]["pdf_path"]
    try:
        audit(bad, formal)
    except UnqualifiedEvidence:
        pass
    else:
        raise AssertionError("duplicate manuscript path was admitted")
    report["adversarial_mutations_rejected"] = 3
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "top_source_priorities"}))


if __name__ == "__main__":
    main()
