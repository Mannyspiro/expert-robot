#!/usr/bin/env python3
"""Validate source-grounded Merlin logic-lens case records with the Python stdlib."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from typing import Any

RECORD_STATUSES = {
    "draft", "source_collected", "translation_reviewed",
    "historical_context_reviewed", "formal_reconstruction_candidate",
    "specialist_reviewed", "contested", "unresolved",
}
RIGHTS = {
    "public_domain_verified", "open_license_verified", "metadata_only",
    "preview_only", "restricted", "unknown",
}
CLAIM_STATUSES = {
    "source_report", "supported_interpretation", "contested",
    "candidate", "unknown", "contradicted",
}
MAPPING_KINDS = {
    "literal_translation", "approximate_translation", "contextual_analogue",
    "formal_embedding", "formal_interpretation", "not_translatable_in_context",
}
EQUIVALENCE = {
    "not_claimed", "equivalent_under_assumptions", "structure_preserving",
    "partial", "lossy", "contested",
}


def _obj(value: Any, label: str, errors: list[str]) -> dict:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    return value


def _text(value: Any, label: str, errors: list[str], minimum: int = 1) -> None:
    if not isinstance(value, str) or len(value.strip()) < minimum:
        errors.append(f"{label} must be a non-empty string (minimum {minimum})")


def _list(value: Any, label: str, errors: list[str], minimum: int = 0) -> list:
    if not isinstance(value, list) or len(value) < minimum:
        errors.append(f"{label} must be an array with at least {minimum} item(s)")
        return []
    return value


def validate_case(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    root = _obj(data, "case", errors)
    required = {
        "schema_version", "case_id", "title", "scope", "problem_context",
        "historical_context", "sources", "argument_reconstruction",
        "translation_records", "claims", "interpretations", "review",
        "record_status",
    }
    missing = required - root.keys()
    if missing:
        errors.append("case missing fields: " + ", ".join(sorted(missing)))
        return errors
    if root["schema_version"] != 1:
        errors.append("schema_version must equal 1")
    ident = root["case_id"]
    if not isinstance(ident, str) or not re.fullmatch(r"logic:[a-z0-9][a-z0-9._:-]{2,127}", ident):
        errors.append("case_id must be a stable logic: identifier")
    _text(root["title"], "title", errors, 3)
    if root["record_status"] not in RECORD_STATUSES:
        errors.append("record_status is not recognized")

    scope = _obj(root["scope"], "scope", errors)
    for key in ("tradition_or_school", "community_or_context", "region", "scope_note"):
        _text(scope.get(key), f"scope.{key}", errors, 2 if key != "scope_note" else 20)
    scope_note = scope.get("scope_note")
    if isinstance(scope_note, str):
        note = scope_note.lower()
        boundary_markers = ("specific", "named", "texts", "community", "school",
                            "period", "corpus", "case", "documented", "subset", "bounded")
        if not any(marker in note for marker in boundary_markers):
            errors.append("scope.scope_note must state a concrete boundary for the case")
        broad_claims = ("all members of", "all people in", "the entire culture believes",
                        "everyone in this culture", "a culture thinks")
        if any(marker in note for marker in broad_claims) and not any(
            phrase in note for phrase in ("does not generalize", "not representative", "not a claim about")
        ):
            errors.append("scope.scope_note must not make an unsupported whole-culture generalization")
    languages = _list(scope.get("languages"), "scope.languages", errors, 1)
    for i, lang in enumerate(languages):
        _text(lang, f"scope.languages[{i}]", errors, 2)
    dates = _obj(scope.get("date_range"), "scope.date_range", errors)
    for key in ("start", "end", "date_basis"):
        _text(dates.get(key), f"scope.date_range.{key}", errors, 1)

    problem = _obj(root["problem_context"], "problem_context", errors)
    _text(problem.get("problem_as_understood"), "problem_context.problem_as_understood", errors, 20)
    _text(problem.get("why_it_mattered"), "problem_context.why_it_mattered", errors, 10)
    tools = _list(problem.get("available_tools_and_knowledge"), "problem_context.available_tools_and_knowledge", errors, 1)
    for i, item in enumerate(tools):
        _text(item, f"problem_context.available_tools_and_knowledge[{i}]", errors, 2)

    historical = _obj(root["historical_context"], "historical_context", errors)
    _text(historical.get("social_and_material_context"), "historical_context.social_and_material_context", errors, 10)
    for key in ("institutions", "contributors_and_transmission", "uncertainties"):
        _list(historical.get(key), f"historical_context.{key}", errors)

    sources = _list(root["sources"], "sources", errors, 1)
    source_ids: set[str] = set()
    for i, source_value in enumerate(sources):
        source = _obj(source_value, f"sources[{i}]", errors)
        for key in ("source_id", "title", "creator", "edition_or_version", "language", "canonical_url", "locator", "provenance"):
            _text(source.get(key), f"sources[{i}].{key}", errors, 2 if key != "provenance" else 5)
        sid = source.get("source_id")
        if isinstance(sid, str):
            if sid in source_ids:
                errors.append(f"duplicate source_id: {sid}")
            source_ids.add(sid)
        if source.get("source_kind") not in {"primary", "secondary_scholarship", "translation", "artifact", "oral_history", "other"}:
            errors.append(f"sources[{i}].source_kind is not recognized")
        if source.get("rights_status") not in RIGHTS:
            errors.append(f"sources[{i}].rights_status is not recognized")
        if source.get("rights_status") == "open_license_verified" and not source.get("license_uri"):
            errors.append(f"sources[{i}] open-license content requires license_uri")
        url = source.get("canonical_url")
        if isinstance(url, str) and not url.startswith(("https://", "http://", "urn:")):
            errors.append(f"sources[{i}].canonical_url must be an http(s) URL or stable URN")

    reconstruction = _obj(root["argument_reconstruction"], "argument_reconstruction", errors)
    if reconstruction.get("reconstruction_status") not in {"not_started", "candidate", "reviewed", "contested"}:
        errors.append("argument_reconstruction.reconstruction_status is not recognized")
    _text(reconstruction.get("conclusion"), "argument_reconstruction.conclusion", errors, 2)
    premises = _list(reconstruction.get("premises"), "argument_reconstruction.premises", errors)
    steps = _list(reconstruction.get("inference_steps"), "argument_reconstruction.inference_steps", errors)
    if reconstruction.get("reconstruction_status") in {"candidate", "reviewed", "contested"} and not (premises or steps):
        errors.append("a non-empty reconstruction requires premises or inference_steps")
    cited = _list(reconstruction.get("source_ids"), "argument_reconstruction.source_ids", errors, 1)
    for sid in cited:
        if sid not in source_ids:
            errors.append(f"argument reconstruction references unknown source_id: {sid}")

    formal = root.get("formal_reconstruction")
    if formal is not None:
        formal = _obj(formal, "formal_reconstruction", errors)
        for key in ("logic_system_id", "formal_system_version", "syntax", "semantics"):
            _text(formal.get(key), f"formal_reconstruction.{key}", errors, 2)
        if not _list(formal.get("inference_rules"), "formal_reconstruction.inference_rules", errors, 1):
            pass
        if formal.get("formal_status") not in {"candidate", "tested", "formalized", "proved", "refuted", "unresolved"}:
            errors.append("formal_reconstruction.formal_status is not recognized")
        if formal.get("formal_status") == "proved" and not formal.get("preservation_claims"):
            errors.append("proved formal reconstruction must state what its mapping preserves")

    translations = _list(root["translation_records"], "translation_records", errors)
    for i, item_value in enumerate(translations):
        item = _obj(item_value, f"translation_records[{i}]", errors)
        for key in ("source_expression", "target_expression", "source_language_or_system", "target_language_or_system"):
            _text(item.get(key), f"translation_records[{i}].{key}", errors)
        if item.get("mapping_kind") not in MAPPING_KINDS:
            errors.append(f"translation_records[{i}].mapping_kind is not recognized")
        if item.get("equivalence_status") not in EQUIVALENCE:
            errors.append(f"translation_records[{i}].equivalence_status is not recognized")
        if item.get("equivalence_status") in {"partial", "lossy", "contested"} and not item.get("lost_or_changed_features"):
            errors.append(f"translation_records[{i}] must describe lost_or_changed_features")

    claims = _list(root["claims"], "claims", errors, 1)
    claim_ids: set[str] = set()
    for i, item_value in enumerate(claims):
        item = _obj(item_value, f"claims[{i}]", errors)
        for key in ("claim_id", "statement"):
            _text(item.get(key), f"claims[{i}].{key}", errors, 3)
        cid = item.get("claim_id")
        if isinstance(cid, str):
            if cid in claim_ids:
                errors.append(f"duplicate claim_id: {cid}")
            claim_ids.add(cid)
        if item.get("epistemic_status") not in CLAIM_STATUSES:
            errors.append(f"claims[{i}].epistemic_status is not recognized")
        claim_sources = _list(item.get("source_ids"), f"claims[{i}].source_ids", errors, 1)
        for sid in claim_sources:
            if sid not in source_ids:
                errors.append(f"claims[{i}] references unknown source_id: {sid}")
        _list(item.get("limitations"), f"claims[{i}].limitations", errors)

    interpretations = _list(root["interpretations"], "interpretations", errors, 1)
    for i, item_value in enumerate(interpretations):
        item = _obj(item_value, f"interpretations[{i}]", errors)
        _text(item.get("interpretation_id"), f"interpretations[{i}].interpretation_id", errors, 3)
        _text(item.get("statement"), f"interpretations[{i}].statement", errors, 10)
        supporting = _list(item.get("supporting_source_ids"), f"interpretations[{i}].supporting_source_ids", errors, 1)
        for sid in supporting:
            if sid not in source_ids:
                errors.append(f"interpretations[{i}] references unknown source_id: {sid}")
        if item.get("status") not in {"working", "supported", "contested", "withdrawn"}:
            errors.append(f"interpretations[{i}].status is not recognized")

    review = _obj(root["review"], "review", errors)
    if not isinstance(review.get("specialist_review_required"), bool):
        errors.append("review.specialist_review_required must be boolean")
    if review.get("review_status") not in {"not_reviewed", "in_review", "reviewed_with_caveats", "contested", "approved_for_teaching"}:
        errors.append("review.review_status is not recognized")
    if root["record_status"] == "specialist_reviewed" and review.get("review_status") not in {"reviewed_with_caveats", "approved_for_teaching", "contested"}:
        errors.append("specialist_reviewed record requires completed specialist review")
    if root["record_status"] == "specialist_reviewed" and review.get("specialist_review_required") and not review.get("reviewer_expertise"):
        errors.append("specialist-reviewed record requires reviewer_expertise")

    for i, asset_value in enumerate(_list(root.get("learning_assets", []), "learning_assets", errors)):
        asset = _obj(asset_value, f"learning_assets[{i}]", errors)
        if asset.get("rights_status") not in {"public_domain_verified", "open_license_verified", "metadata_only", "link_only", "generated_labeled", "unknown"}:
            errors.append(f"learning_assets[{i}].rights_status is not recognized")
        for sid in _list(asset.get("source_ids"), f"learning_assets[{i}].source_ids", errors):
            if sid not in source_ids:
                errors.append(f"learning_assets[{i}] references unknown source_id: {sid}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.case.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read case: {exc}")
        return 2
    errors = validate_case(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: logic-lens case {data['case_id']} has source, scope, reconstruction and review links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
