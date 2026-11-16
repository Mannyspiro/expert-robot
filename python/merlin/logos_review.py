"""Source-bound, non-authoritative Logos review for Ideonomy candidate sets."""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Mapping

from merlin.artifact_ref import ArtifactRef
from merlin.knowledge_compression import canonical_json, store_knowledge_representation
from merlin.knowledge_graph import GraphEdge, MerlinKnowledgeGraph
from merlin.knowledge_reconstruction import inspect_knowledge_representation
from merlin.project_registry import MerlinRegistry
from merlin.hermes_stage_journal import HermesStageJournal

LOGOS_REVIEW_SCHEMA = "merlin-logos-review/1"
_DISPOSITIONS = frozenset({
    "retain_for_testing", "challenge", "insufficient_source", "source_conflict",
})
_FINDING_KINDS = frozenset({"quotation", "interpretation", "hypothesis"})
_PROVENANCE_FIELDS = frozenset({
    "id", "version", "provider_revision", "prompt_digest",
    "config_digest", "adapter_digest",
})


def validate_reviewer_provenance(value: Mapping[str, Any]) -> dict[str, str]:
    """Validate runtime-owned reviewer identity before any model/provider call."""
    if not isinstance(value, Mapping) or set(value) != _PROVENANCE_FIELDS:
        raise ValueError("runtime-owned Logos reviewer provenance is incomplete")
    result = dict(value)
    for field, maximum in (("id", 128), ("version", 128), ("provider_revision", 256)):
        item = result.get(field)
        if not isinstance(item, str) or not item.strip() or len(item) > maximum:
            raise ValueError("Logos reviewer identity and immutable revision are required")
    if result["provider_revision"].strip().casefold() in {
        "latest", "stable", "main", "master", "head", "current", "default",
    }:
        raise ValueError("Logos provider_revision must be immutable, not an alias")
    for field in ("prompt_digest", "config_digest", "adapter_digest"):
        digest = result.get(field)
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)):
            raise ValueError("Logos reviewer digests must be lowercase SHA-256")
    return {key: result[key] for key in sorted(result)}


def validate_logos_review(
    candidate_set: Mapping[str, Any],
    generated: Mapping[str, Any],
    *,
    source_segments: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate complete, typed review coverage without granting epistemic authority.

    A quotation is accepted only when its exact text occurs in a cited, verified
    extraction segment whose byte-range locator matches the candidate binding.
    """
    if not isinstance(candidate_set, Mapping) or candidate_set.get("schema") != "merlin-ideonomy-candidate-set/1":
        raise ValueError("Logos input must be an Ideonomy candidate set")
    body = {key: value for key, value in candidate_set.items() if key != "candidate_set_id"}
    expected = hashlib.sha256(canonical_json(body)).hexdigest()
    if candidate_set.get("candidate_set_id") != expected:
        raise ValueError("Ideonomy candidate-set digest does not match canonical content")
    if (candidate_set.get("authority") != "candidate_generation_only"
            or candidate_set.get("epistemic_status") != "unverified"
            or candidate_set.get("qualification") is not False):
        raise ValueError("Logos accepts only unverified candidate sets")
    candidates = candidate_set.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 500:
        raise ValueError("candidate set is malformed or exceeds the review budget")
    candidate_by_id = {}
    generator = candidate_set.get("generator")
    if not isinstance(generator, Mapping):
        raise ValueError("candidate-set generator provenance is malformed")
    validate_reviewer_provenance(generator)
    source_representation_id = candidate_set.get("source_representation_id")
    if not isinstance(source_representation_id, str) or len(source_representation_id) != 64:
        raise ValueError("candidate-set source representation identity is malformed")
    if (isinstance(candidate_set.get("candidate_count"), bool)
            or candidate_set.get("candidate_count") != len(candidates)):
        raise ValueError("candidate-set count does not match its candidate list")
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or set(candidate) != {
            "candidate_id", "kind", "content", "rationale", "source_bindings",
            "confidence_estimate", "confidence_semantics", "epistemic_status", "authority",
        }:
            raise ValueError("candidate entries contain unsupported fields")
        candidate_id = candidate.get("candidate_id")
        bindings = candidate.get("source_bindings")
        if (not isinstance(candidate_id, str) or len(candidate_id) != 64
                or not isinstance(bindings, list) or not bindings):
            raise ValueError("candidate identity or source bindings are missing")
        if (candidate.get("epistemic_status") != "unverified"
                or candidate.get("authority") != "candidate_generation_only"
                or candidate.get("confidence_semantics") != "model_estimate_not_truth_probability"):
            raise ValueError("candidate epistemic boundary is malformed")
        identity_body = {
            "source_representation_id": source_representation_id,
            "generator": dict(generator), "kind": candidate.get("kind"),
            "content": candidate.get("content"), "rationale": candidate.get("rationale"),
            "source_bindings": bindings,
            "confidence_estimate": candidate.get("confidence_estimate"),
        }
        if hashlib.sha256(canonical_json(identity_body)).hexdigest() != candidate_id:
            raise ValueError("candidate identity does not match its canonical source-bound content")
        candidate_by_id[candidate_id] = candidate
    if len(candidate_by_id) != len(candidates):
        raise ValueError("candidate IDs must be unique")

    segments_by_range: dict[bytes, str] = {}
    if source_segments is not None:
        if not isinstance(source_segments, list) or len(source_segments) > 10_000:
            raise ValueError("verified source segments must be a bounded list")
        for segment in source_segments:
            if (not isinstance(segment, Mapping)
                    or not isinstance(segment.get("byte_range"), Mapping)
                    or not isinstance(segment.get("text"), str)):
                raise ValueError("verified source segment is malformed")
            key = canonical_json(segment["byte_range"])
            if key in segments_by_range:
                raise ValueError("verified source segment byte ranges must be unique")
            segments_by_range[key] = segment["text"]

    if not isinstance(generated, Mapping) or set(generated) != {
        "candidate_reviews", "counter_hypotheses", "falsifiability_questions", "limitations",
    }:
        raise ValueError("Logos response contains unsupported or missing top-level fields")
    reviews = generated["candidate_reviews"]
    if not isinstance(reviews, list) or len(reviews) != len(candidates):
        raise ValueError("Logos must review every candidate exactly once")
    seen = set()
    normalized_reviews = []
    for review in reviews:
        if not isinstance(review, Mapping) or set(review) != {
            "candidate_id", "disposition", "rationale", "findings",
        }:
            raise ValueError("candidate review has unsupported fields")
        candidate_id = review.get("candidate_id")
        if candidate_id not in candidate_by_id or candidate_id in seen:
            raise ValueError("candidate review is unknown or duplicated")
        seen.add(candidate_id)
        disposition = review.get("disposition")
        rationale = review.get("rationale")
        findings = review.get("findings")
        if disposition not in _DISPOSITIONS:
            raise ValueError("Logos disposition is not an allowed non-authoritative state")
        if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 4096:
            raise ValueError("candidate review rationale must be bounded text")
        if not isinstance(findings, list) or len(findings) > 30:
            raise ValueError("candidate findings must be a bounded list")
        candidate_bindings = candidate_by_id[candidate_id]["source_bindings"]
        normalized_findings = []
        for finding in findings:
            if not isinstance(finding, Mapping) or set(finding) != {
                "kind", "text", "source_binding_indexes",
            }:
                raise ValueError("finding must contain kind, text and source_binding_indexes")
            kind, text, indexes = finding["kind"], finding["text"], finding["source_binding_indexes"]
            if kind not in _FINDING_KINDS:
                raise ValueError("finding kind must distinguish quotation, interpretation or hypothesis")
            if not isinstance(text, str) or not text.strip() or len(text) > 4096:
                raise ValueError("finding text must be bounded and non-empty")
            if not isinstance(indexes, list) or len(indexes) > 20:
                raise ValueError("finding source-binding indexes are invalid")
            if any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= len(candidate_bindings) for i in indexes):
                raise ValueError("finding cites a source binding outside this candidate")
            if len(set(indexes)) != len(indexes):
                raise ValueError("finding source-binding indexes must be unique")
            if kind == "quotation":
                if not indexes:
                    raise ValueError("direct quotations require at least one exact source binding")
                if not segments_by_range:
                    raise ValueError("direct quotations require verified extraction text")
                cited_texts = []
                for index in indexes:
                    binding = candidate_bindings[index]
                    if binding.get("locator_type") != "byte_range":
                        raise ValueError("direct quotation binding must identify an exact byte range")
                    segment_text = segments_by_range.get(canonical_json(binding.get("locator")))
                    if segment_text is None:
                        raise ValueError("direct quotation locator does not resolve to verified extraction text")
                    cited_texts.append(segment_text)
                if not any(text.strip() in segment_text for segment_text in cited_texts):
                    raise ValueError("quoted text does not occur in the cited source segment")
            normalized_findings.append({
                "kind": kind, "text": text.strip(),
                "source_bindings": [candidate_bindings[i] for i in indexes],
            })
        normalized_reviews.append({
            "candidate_id": candidate_id, "disposition": disposition,
            "rationale": rationale.strip(), "findings": normalized_findings,
        })
    if seen != set(candidate_by_id):
        raise ValueError("Logos review omitted one or more candidates")

    def validate_auxiliary(name: str, fields: set[str]) -> list[dict[str, Any]]:
        items = generated[name]
        if not isinstance(items, list) or len(items) > 500:
            raise ValueError(name + " must be a bounded list")
        output = []
        for item in items:
            if not isinstance(item, Mapping) or set(item) != fields:
                raise ValueError(name + " entry has unsupported fields")
            candidate_id = item.get("candidate_id")
            statement = item.get("statement")
            indexes = item.get("source_binding_indexes")
            if candidate_id not in candidate_by_id:
                raise ValueError(name + " references an unknown candidate")
            if not isinstance(statement, str) or not statement.strip() or len(statement) > 4096:
                raise ValueError(name + " statement must be bounded non-empty text")
            candidate_bindings = candidate_by_id[candidate_id]["source_bindings"]
            if (not isinstance(indexes, list) or len(indexes) > 20
                    or any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= len(candidate_bindings) for i in indexes)
                    or len(set(indexes)) != len(indexes)):
                raise ValueError(name + " source-binding indexes are invalid")
            output.append({
                "candidate_id": candidate_id, "statement": statement.strip(),
                "source_bindings": [candidate_bindings[i] for i in indexes],
            })
        return output

    counter_hypotheses = validate_auxiliary(
        "counter_hypotheses", {"candidate_id", "statement", "source_binding_indexes"},
    )
    falsifiability_questions = validate_auxiliary(
        "falsifiability_questions", {"candidate_id", "statement", "source_binding_indexes"},
    )
    limitations = generated["limitations"]
    if (not isinstance(limitations, list) or len(limitations) > 100
            or any(not isinstance(x, str) or not x.strip() or len(x) > 2048 for x in limitations)):
        raise ValueError("Logos limitations must be bounded non-empty strings")
    normalized_reviews.sort(key=lambda item: item["candidate_id"])
    counter_hypotheses.sort(key=lambda item: (item["candidate_id"], item["statement"]))
    falsifiability_questions.sort(key=lambda item: (item["candidate_id"], item["statement"]))
    result_body = {
        "schema": LOGOS_REVIEW_SCHEMA,
        "candidate_set_id": candidate_set["candidate_set_id"],
        "candidate_reviews": normalized_reviews,
        "counter_hypotheses": counter_hypotheses,
        "falsifiability_questions": falsifiability_questions,
        "limitations": sorted(set(x.strip() for x in limitations)),
        "authority": "skeptical_review_only",
        "epistemic_status": "unverified",
        "semantic_verification": "not_established",
        "qualification": False,
        "promotion_authority": False,
    }
    return {**result_body, "review_id": hashlib.sha256(canonical_json(result_body)).hexdigest()}


def build_logos_review_stage_handler(
    *, registry: MerlinRegistry, graph: MerlinKnowledgeGraph, project_id: str,
    repository: str, commit_sha: str,
    reviewer: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    reviewer_provenance: Mapping[str, Any],
) -> Callable[[Mapping[str, Any], Any], Mapping[str, Any]]:
    """Build Logos stage: exact candidate-set in, immutable derived review out."""
    if not isinstance(registry, MerlinRegistry) or not isinstance(graph, MerlinKnowledgeGraph):
        raise ValueError("canonical registry and knowledge graph are required")
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("project_id is required")
    if not isinstance(repository, str) or "/" not in repository:
        raise ValueError("repository must be owner/name")
    if (not isinstance(commit_sha, str) or len(commit_sha) != 40
            or any(c not in "0123456789abcdef" for c in commit_sha)):
        raise ValueError("commit_sha must be a full lowercase Git commit SHA")
    if not callable(reviewer):
        raise ValueError("an injected Logos reviewer is required")
    provenance = validate_reviewer_provenance(reviewer_provenance)
    journal = HermesStageJournal(registry.root / "hermes-stage-journal.sqlite3")

    def execute(task: Mapping[str, Any], context: Any) -> Mapping[str, Any]:
        if task.get("stage") != "logos_review":
            raise ValueError("Logos handler received a mismatched task")
        refs = task.get("artifact_refs")
        if not isinstance(refs, list) or len(refs) != 1:
            raise ValueError("logos_review requires exactly one candidate-set ArtifactRef")
        candidate_ref = ArtifactRef.from_mapping(refs[0]).to_dict()
        inspection = inspect_knowledge_representation(registry, candidate_ref)
        manifest = inspection["manifest"]
        if manifest["representation_type"] != "ideonomy_candidates":
            raise ValueError("Logos input must be an ideonomy_candidates representation")
        candidate_set = manifest["payload"]
        if (not isinstance(candidate_set, Mapping)
                or candidate_set.get("source_representation_ref") != inspection["source_artifact_refs"][0]
                or candidate_set.get("source_artifact_refs") != inspection["source_artifact_refs"][1:]):
            raise ValueError("candidate-set source ArtifactRefs do not match its verified representation")
        source_inspection = inspect_knowledge_representation(
            registry, candidate_set["source_representation_ref"],
        )
        extraction_payload = source_inspection["manifest"].get("payload")
        source_segments = extraction_payload.get("segments") if isinstance(extraction_payload, Mapping) else None
        if (source_inspection["manifest"]["representation_type"] != "text_extraction"
                or source_inspection["representation_id"] != candidate_set.get("source_representation_id")
                or source_inspection["source_artifact_refs"] != candidate_set.get("source_artifact_refs")):
            raise ValueError("candidate-set source extraction identity or lineage is invalid")
        allowed_bindings = {canonical_json(binding) for binding in source_inspection["source_bindings"]}
        for candidate in candidate_set.get("candidates", []):
            for binding in candidate.get("source_bindings", []):
                if canonical_json(binding) not in allowed_bindings:
                    raise ValueError("candidate cites a source locator outside the verified extraction manifest")
        budget = task.get("resource_budget")
        if not isinstance(budget, Mapping):
            raise ValueError("Logos requires the canonical resource budget")
        memory_bytes = budget.get("memory_bytes")
        if isinstance(memory_bytes, bool) or not isinstance(memory_bytes, int) or memory_bytes < 4096:
            raise ValueError("Logos memory budget must be at least 4096 bytes")
        candidate_set_bytes = len(canonical_json(candidate_set))
        source_binding_bytes = len(canonical_json(inspection["source_bindings"]))
        input_bytes = candidate_set_bytes + source_binding_bytes
        if input_bytes > max(1024, memory_bytes // 4):
            raise ValueError("Logos candidate-set input exceeds the conservative memory admission budget")
        candidate_set_digest = hashlib.sha256(canonical_json(candidate_set)).hexdigest()
        if candidate_ref["sha256"] != inspection["representation_ref"]["sha256"]:
            raise ValueError("candidate-set ArtifactRef digest changed")
        check_cancelled = getattr(context, "check_cancelled", None)
        if callable(check_cancelled):
            check_cancelled()
        request_identity = {
            "stage": "logos_review", "task_id": context.task_id,
            "hypothesis_id": context.hypothesis_id, "candidate_set_ref": candidate_ref,
            "candidate_set_digest": candidate_set_digest, "reviewer_provenance": provenance,
            "memory_bytes": memory_bytes,
        }
        checkpoint = journal.begin(
            idempotency_key=getattr(context, "idempotency_key", None),
            stage="logos_review", task_id=context.task_id,
            hypothesis_id=context.hypothesis_id, request=request_identity,
        )
        if checkpoint["state"] == "completed":
            return checkpoint["result"]
        if checkpoint["candidate_set"] is not None:
            review = checkpoint["candidate_set"]
        else:
            request = {
                "schema": "merlin-logos-review-input/1",
                "candidate_set_ref": candidate_ref,
                "candidate_set_digest": candidate_set_digest,
                "candidate_set": candidate_set,
                "source_artifact_refs": inspection["source_artifact_refs"],
                "source_bindings": inspection["source_bindings"],
                "instructions": (
                    "Critically review every candidate. Distinguish direct quotations, "
                    "interpretations and hypotheses. Challenge assumptions, identify source "
                    "conflicts, propose counter-hypotheses and falsifiability tests. Do not "
                    "claim truth, proof, verification, qualification or promotion."
                ),
                "limits": {"memory_bytes": memory_bytes, "max_candidates": 500, "max_input_bytes": max(1024, memory_bytes // 4)},
                "idempotency_key": getattr(context, "idempotency_key", None),
            }
            request["source_segments"] = source_segments
            generated = reviewer(request)
            review = validate_logos_review(
                candidate_set, generated, source_segments=source_segments,
            )
            review_body = {key: value for key, value in review.items() if key != "review_id"}
            review_body["reviewer_provenance"] = provenance
            review = {**review_body, "review_id": hashlib.sha256(canonical_json(review_body)).hexdigest()}
            journal.save_generated(getattr(context, "idempotency_key", None), review)
        if callable(check_cancelled):
            check_cancelled()
        source_refs = [candidate_ref] + inspection["source_artifact_refs"]
        source_bindings = [{
            "artifact_ref": candidate_ref, "locator_type": "whole_artifact",
            "locator": "exact Ideonomy candidate-set artifact",
        }] + inspection["source_bindings"]
        stored = store_knowledge_representation(
            registry, graph, project_id=project_id,
            representation_type="other", payload=review,
            source_refs=source_refs, source_bindings=source_bindings,
            tool_id=provenance["id"], tool_version=provenance["version"],
            loss_character="unknown", source_repo=repository, source_commit=commit_sha,
        )
        graph.add_edge(GraphEdge(
            stored["graph_node_id"], "reviews",
            "knowledge-representation:" + inspection["representation_id"],
            {
                "review_id": review["review_id"],
                "candidate_set_id": review["candidate_set_id"],
                "authority": "skeptical_review_only",
                "epistemic_status": "unverified",
                "promotion_authority": False,
            },
        ))
        ref = ArtifactRef.from_mapping(stored["representation_ref"]).to_dict()
        resolution = registry.resolve_artifact_ref(ref)
        if resolution.get("verified") is not True:
            raise RuntimeError("Logos review ArtifactRef failed canonical registry resolution")
        result = {
            "schema": "merlin-hermes-logos-review-result/1",
            "stage": "logos_review", "review_id": review["review_id"],
            "candidate_set_id": review["candidate_set_id"],
            "candidate_count": len(review["candidate_reviews"]),
            "artifact": {"artifact_ref": ref, "sha256": ref["sha256"],
                         "registry_verified": True, "size_bytes": resolution["size_bytes"]},
            "authority": "skeptical_review_only", "epistemic_status": "unverified",
            "semantic_verification": "not_established", "qualification": False,
            "promotion_authority": False, "evidence_refs": [],
            "artifact_refs": [ref], "candidate_set_ref": candidate_ref,
        }
        return journal.complete(getattr(context, "idempotency_key", None), result)
    return execute


__all__ = [
    "LOGOS_REVIEW_SCHEMA", "validate_reviewer_provenance",
    "validate_logos_review", "build_logos_review_stage_handler",
]
