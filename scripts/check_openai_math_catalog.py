#!/usr/bin/env python3
"""Fail-closed offline checks for the PINNED upstream OpenAI math intake catalogue.

This validates catalogue structure and project registrations only.
It neither compiles upstream proofs nor claims imported declarations are certified.
"""
import argparse
import json
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "docs/openai-math-catalog-2026-10-09.json"
EXPECTED_COMMIT = "fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb"
EXPECTED_YAML_BLOB = "275eee8cfab7ce49d3a5e88f02cbb8f28fe6fee6"
EXPECTED_LOCAL = {
    "MathAI.Graph.l1Distance_append",
    "MathAI.Graph.l1AppendReal_norm_sub",
}


class InvalidCatalogue(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidCatalogue(message)


def validate(catalog):
    require(catalog.get("schema_version") == 1, "schema version")
    require(catalog.get("source_repo") == "openai/math", "source repository")
    require(catalog.get("source_commit") == EXPECTED_COMMIT, "source commit")
    require(catalog.get("formalization_yaml_blob_sha") == EXPECTED_YAML_BLOB,
            "source formalization blob")
    require(catalog.get("upstream_review_status") == "unchecked",
            "source review status changed without audit")
    require(catalog.get("production_or_promotion_authority") is False, "authority")
    require(catalog.get("source_toolchain") == "leanprover/lean4:v4.34.1",
            "toolchain pin")
    require(catalog.get("source_mathlib_revision") ==
            "d13f23b723b8a846827a245b89c10fc7d3f11612", "mathlib pin")
    papers = catalog.get("papers")
    declarations = catalog.get("declared_results")
    require(isinstance(papers, list) and len(papers) == 173, "paper count")
    require(isinstance(declarations, list) and len(declarations) == 200,
            "declaration count")
    require(catalog.get("paper_count") == len(papers), "paper count field")
    require(catalog.get("declaration_count") == len(declarations),
            "declaration count field")
    titles = []
    for item in papers:
        title = item.get("title")
        path = item.get("source_pdf_path", "")
        require(isinstance(title, str) and bool(title.strip()), "empty title")
        require(isinstance(path, str) and path.startswith("../preprints/")
                and path.endswith(".pdf") and ".." not in path[3:],
                "unsafe/missing manuscript path")
        titles.append(title)
    require(len(set(titles)) == len(titles), "duplicate paper title")
    names = []
    for item in declarations:
        name = item.get("declaration", "")
        source = item.get("module_file", "")
        comparator = item.get("comparator_config", "")
        require(isinstance(name, str) and bool(re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", name)),
            "invalid qualified declaration")
        require(isinstance(source, str) and source.startswith("OAI/")
                and source.endswith(".lean") and ".." not in source,
                "invalid module path")
        require(isinstance(comparator, str) and comparator.startswith(
            "ComparatorChallenges/") and comparator.endswith(".json")
                and ".." not in comparator, "invalid comparator config")
        require(item.get("state") == "upstream_declared_not_imported",
                "upstream theorem wrongly marked imported")
        names.append(name)
    require(len(set(names)) == len(names), "duplicate upstream declaration")
    require(not set(names) & EXPECTED_LOCAL,
            "upstream and local declaration namespace confused")
    local = catalog.get("local_adaptations", [])
    require({row.get("name") for row in local} == EXPECTED_LOCAL,
            "local adaptation set mismatch")
    for row in local:
        require(row.get("qualification") == "pending",
                "catalogue has unsubstantiated qualification")
        require(row.get("source") == "formal/MathAI/Graph/L1Append.lean",
                "local source mismatch")
    return {"schema_version": 1, "experiment": "openai-math-catalog-offline-audit-v1",
            "upstream_source_commit": EXPECTED_COMMIT,
            "manuscripts_indexed": len(papers),
            "upstream_declarations_indexed": len(names),
            "upstream_declarations_imported_as_is": 0,
            "local_adaptations_registered": len(local),
            "all_records_unqualified": True, "network_operations": 0,
            "formal_checker_executed_by_this_script": False,
            "authority_expanded": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    report = validate(catalog)
    # Mutation checks: detect forged qualification and lost upstream declaration.
    changed = json.loads(json.dumps(catalog))
    changed["declared_results"][0]["state"] = "verified"
    try:
        validate(changed)
        raise AssertionError("forged qualification was accepted")
    except InvalidCatalogue:
        pass
    changed = json.loads(json.dumps(catalog))
    changed["declared_results"][1]["declaration"] = changed["declared_results"][0]["declaration"]
    try:
        validate(changed)
        raise AssertionError("duplicate declaration was accepted")
    except InvalidCatalogue:
        pass
    report["adversarial_catalog_mutations_rejected"] = 2
    destination = Path(args.report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
