"""Source-grounded Ideonomy enumeration; candidates are never treated as verified facts."""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Mapping

from merlin.artifact_ref import ArtifactRef
from merlin.knowledge_compression import canonical_json, store_knowledge_representation
from merlin.knowledge_graph import EDGE_TYPES, GraphEdge, GraphNode, MerlinKnowledgeGraph
from merlin.knowledge_reconstruction import inspect_knowledge_representation
from merlin.project_registry import MerlinRegistry


IDEONOMY_SCHEMA = "merlin-ideonomy-candidate-set/1"
IDEONOMY_INPUT_SCHEMA = "merlin-ideonomy-input/1"
MAX_IDEONOMY_CANDIDATES = 500
MAX_IDEONOMY_RELATIONS = 2_000
MAX_IDEONOMY_INPUT_CHARS = 200_000
MAX_IDEONOMY_SOURCE_BINDINGS = 2_000
MAX_BINDINGS_PER_CANDIDATE = 20

CANDIDATE_KINDS = frozenset({
    "concept", "claim", "question", "method", "equation", "procedure",
    "counter_hypothesis", "assumption", "definition", "theorem",
    "experiment", "dataset",
})

_NODE_TYPE_BY_KIND = {
    "concept": "model",
    "claim": "claim",
    "question": "claim",
    "method": "module",
    "equation": "equation",
    "procedure": "module",
    "counter_hypothesis": "claim",
    "assumption": "assumption",
    "definition": "model",
    "theorem": "theorem",
    "experiment": "experiment",
    "dataset": "dataset",
}

IDEONOMY_INSTRUCTIONS = (
    "Enumerate candidate concepts, claims, definitions, assumptions, questions, "
    "methods, equations, procedures, counter-hypotheses and relationships. "
    "Preserve alternative interpretations and contradictions. Every candidate "
    "must cite one or more supplied source-binding indexes. Do not assert that "
    "a candidate is true, proven, verified or qualified. Distinguish source "
    "statements from your own hypotheses and identify unresolved questions."
)


class IdeonomyUnavailableError(RuntimeError):
    """Raised when no qualified-enough candidate generator is configured."""


def ideonomy_capability(candidate_generator: Callable[..., Any] | None) -> dict[str, Any]:
    """Report configuration separately from qualification."""
    if not callable(candidate_generator):
        return {
            "capability": "ideonomy.enumerate",
            "state": "unavailable",
            "qualified": False,
            "reason": "no candidate generator is configured",
        }
    return {
        "capability": "ideonomy.enumerate",
        "state": "configured",
        "qualified": False,
        "reason": "candidate generation is configured but not independently qualified",
    }


def _candidate_node_id(candidate_id: str) -> str:
    return "ideonomy-candidate:" + candidate_id


def _source_node_id(source_ref: Mapping[str, Any]) -> str:
    return "artifact-reference:" + hashlib.sha256(canonical_json(source_ref)).hexdigest()[:32]


def _dedupe_bindings(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[bytes] = set()
    for binding in bindings:
        key = canonical_json(binding)
        if key not in seen:
            seen.add(key)
            result.append(binding)
    return result


def enumerate_ideonomy_candidates(
    registry: MerlinRegistry,
    source_representation_ref: Mapping[str, Any],
    candidate_generator: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None,
    *,
    max_candidates: int = MAX_IDEONOMY_CANDIDATES,
    max_relations: int = MAX_IDEONOMY_RELATIONS,
    max_input_characters: int = MAX_IDEONOMY_INPUT_CHARS,
) -> dict[str, Any]:
    """Ask an injected generator for source-indexed candidates and validate them.

    The generator receives text segments and exact source-binding indexes, not
    authority to read or mutate the registry. All generated candidates remain
    unverified hypotheses until separate review and evidence checks occur.
    """
    if not callable(candidate_generator):
        raise IdeonomyUnavailableError("Ideonomy candidate generator is not configured")
    if (isinstance(max_candidates, bool) or not isinstance(max_candidates, int)
            or not 1 <= max_candidates <= MAX_IDEONOMY_CANDIDATES):
        raise ValueError("max_candidates must be between 1 and 500")
    if (isinstance(max_relations, bool) or not isinstance(max_relations, int)
            or not 0 <= max_relations <= MAX_IDEONOMY_RELATIONS):
        raise ValueError("max_relations must be between 0 and 2,000")

    inspection = inspect_knowledge_representation(registry, source_representation_ref)
    manifest = inspection["manifest"]
    if manifest.get("representation_type") != "text_extraction":
        raise ValueError("Ideonomy input must be a verified text_extraction representation")
    extraction = manifest.get("payload")
    if not isinstance(extraction, dict) or extraction.get("schema") != "merlin-text-extraction/1":
        raise ValueError("Ideonomy input extraction payload has an unsupported schema")
    segments = extraction.get("segments")
    if not isinstance(segments, list):
        raise ValueError("text extraction payload is missing segments")
    if (
        isinstance(max_input_characters, bool)
        or not isinstance(max_input_characters, int)
        or not 1 <= max_input_characters <= MAX_IDEONOMY_INPUT_CHARS
    ):
        raise ValueError("max_input_characters must be between 1 and 200,000")
    input_characters = sum(
        len(segment.get("text", "")) for segment in segments
        if isinstance(segment, Mapping) and isinstance(segment.get("text"), str)
    )
    if input_characters > max_input_characters:
        raise ValueError("Ideonomy input exceeds its bounded character budget; chunked enumeration is required")
    segments_by_byte_range = {
        canonical_json(segment["byte_range"]): segment
        for segment in segments
        if isinstance(segment, Mapping) and isinstance(segment.get("byte_range"), Mapping)
    }
    source_binding_entries: list[dict[str, Any]] = []
    for binding in inspection["source_bindings"]:
        if binding.get("locator_type") == "whole_artifact":
            continue
        if binding.get("locator_type") != "byte_range":
            raise ValueError("Ideonomy text input contains an unsupported precise locator type")
        segment = segments_by_byte_range.get(canonical_json(binding.get("locator")))
        if segment is None:
            raise ValueError("Ideonomy source binding does not resolve to an extracted segment")
        source_binding_entries.append({
            "index": len(source_binding_entries),
            "segment_id": segment["segment_id"],
            "binding": binding,
        })
    if not source_binding_entries:
        raise ValueError("Ideonomy requires precise source locators; the extraction has none")
    if len(source_binding_entries) > MAX_IDEONOMY_SOURCE_BINDINGS:
        raise ValueError("Ideonomy source locator count exceeds its bounded input budget")
    request = {
        "schema": IDEONOMY_INPUT_SCHEMA,
        "instructions": IDEONOMY_INSTRUCTIONS,
        "source_representation_ref": inspection["representation_ref"],
        "source_representation_id": inspection["representation_id"],
        "source_artifact_refs": inspection["source_artifact_refs"],
        "source_bindings": source_binding_entries,
        "segments": segments,
        "limits": {
            "max_candidates": max_candidates,
            "max_relations": max_relations,
            "max_input_characters": max_input_characters,
            "max_source_bindings_per_candidate": MAX_BINDINGS_PER_CANDIDATE,
        },
    }
    generated = candidate_generator(request)
    if not isinstance(generated, Mapping):
        raise ValueError("Ideonomy generator must return an object")
    if set(generated) - {"generator", "candidates", "relations"}:
        raise ValueError("Ideonomy generator returned unsupported top-level fields")
    generator = generated.get("generator")
    if not isinstance(generator, Mapping) or set(generator) != {"id", "version"}:
        raise ValueError("Ideonomy generator identity must contain only id and version")
    generator_id = generator.get("id")
    generator_version = generator.get("version")
    if (
        not isinstance(generator_id, str) or not generator_id.strip()
        or len(generator_id) > 128
        or not isinstance(generator_version, str) or not generator_version.strip()
        or len(generator_version) > 128
    ):
        raise ValueError("Ideonomy generator id and version must be non-empty bounded text")

    raw_candidates = generated.get("candidates")
    raw_relations = generated.get("relations", [])
    if not isinstance(raw_candidates, list) or len(raw_candidates) > max_candidates:
        raise ValueError("Ideonomy candidate list is missing or exceeds its budget")
    if not isinstance(raw_relations, list) or len(raw_relations) > max_relations:
        raise ValueError("Ideonomy relation list exceeds its budget")

    local_to_candidate: dict[str, str] = {}
    candidates: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()
    for raw in raw_candidates:
        if not isinstance(raw, Mapping):
            raise ValueError("each Ideonomy candidate must be an object")
        allowed = {
            "local_id", "kind", "content", "rationale",
            "source_binding_indexes", "confidence_estimate",
        }
        if set(raw) - allowed:
            raise ValueError("Ideonomy candidate contains unsupported authority or fields")
        local_id = raw.get("local_id")
        kind = raw.get("kind")
        content = raw.get("content")
        rationale = raw.get("rationale", "")
        indexes = raw.get("source_binding_indexes")
        confidence = raw.get("confidence_estimate")
        if not isinstance(local_id, str) or not local_id.strip() or len(local_id) > 128:
            raise ValueError("candidate local_id must be non-empty bounded text")
        if local_id in local_to_candidate:
            raise ValueError("candidate local_id values must be unique")
        if not isinstance(kind, str) or kind not in CANDIDATE_KINDS:
            raise ValueError("candidate kind is unsupported")
        if not isinstance(content, str) or not content.strip() or len(content) > 8_192:
            raise ValueError("candidate content must be non-empty and at most 8,192 characters")
        if not isinstance(rationale, str) or len(rationale) > 4_096:
            raise ValueError("candidate rationale must be text of at most 4,096 characters")
        if (
            not isinstance(indexes, list) or not indexes
            or len(indexes) > MAX_BINDINGS_PER_CANDIDATE
        ):
            raise ValueError("each candidate requires 1 to 20 source-binding indexes")
        if any(isinstance(index, bool) or not isinstance(index, int) for index in indexes):
            raise ValueError("source-binding indexes must be integers")
        if len(set(indexes)) != len(indexes):
            raise ValueError("source-binding indexes must not repeat")
        if any(index < 0 or index >= len(source_binding_entries) for index in indexes):
            raise ValueError("candidate cites a source-binding index outside the inspected manifest")
        selected_bindings = [source_binding_entries[index]["binding"] for index in indexes]
        if not selected_bindings:
            raise ValueError("candidate requires at least one precise source locator")
        if confidence is not None and (
            isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not 0.0 <= float(confidence) <= 1.0
        ):
            raise ValueError("confidence_estimate must be null or a number between 0 and 1")

        candidate_body = {
            "source_representation_id": inspection["representation_id"],
            "generator": {"id": generator_id, "version": generator_version},
            "kind": kind,
            "content": content.strip(),
            "rationale": rationale.strip(),
            "source_bindings": selected_bindings,
            "confidence_estimate": float(confidence) if confidence is not None else None,
        }
        candidate_id = hashlib.sha256(canonical_json(candidate_body)).hexdigest()
        if candidate_id in candidate_ids:
            raise ValueError("duplicate Ideonomy candidates must be consolidated by the generator")
        candidate_ids.add(candidate_id)
        local_to_candidate[local_id] = candidate_id
        candidates.append({
            "candidate_id": candidate_id,
            "kind": kind,
            "content": content.strip(),
            "rationale": rationale.strip(),
            "source_bindings": selected_bindings,
            "confidence_estimate": float(confidence) if confidence is not None else None,
            "confidence_semantics": "model_estimate_not_truth_probability",
            "epistemic_status": "unverified",
            "authority": "candidate_generation_only",
        })

    relations: list[dict[str, Any]] = []
    relation_keys: set[tuple[str, str, str]] = set()
    for raw in raw_relations:
        if not isinstance(raw, Mapping):
            raise ValueError("each Ideonomy relation must be an object")
        allowed = {"subject_local_id", "predicate", "object_local_id", "rationale"}
        if set(raw) - allowed:
            raise ValueError("Ideonomy relation contains unsupported fields")
        subject_local = raw.get("subject_local_id")
        object_local = raw.get("object_local_id")
        predicate = raw.get("predicate")
        rationale = raw.get("rationale", "")
        if (
            not isinstance(subject_local, str) or not isinstance(object_local, str)
            or subject_local not in local_to_candidate or object_local not in local_to_candidate
        ):
            raise ValueError("Ideonomy relation references an unknown candidate local_id")
        if not isinstance(predicate, str) or predicate not in EDGE_TYPES:
            raise ValueError("Ideonomy relation predicate is not supported by the canonical graph")
        if subject_local == object_local:
            raise ValueError("self-relations are not accepted")
        if not isinstance(rationale, str) or len(rationale) > 4_096:
            raise ValueError("relation rationale must be text of at most 4,096 characters")
        subject = local_to_candidate[subject_local]
        object_ = local_to_candidate[object_local]
        relation_key = (subject, predicate, object_)
        if relation_key in relation_keys:
            raise ValueError("duplicate candidate relation tuple")
        relation_keys.add(relation_key)
        relation_body = {
            "subject_candidate_id": subject,
            "predicate": predicate,
            "object_candidate_id": object_,
            "rationale": rationale.strip(),
        }
        relation_id = hashlib.sha256(canonical_json(relation_body)).hexdigest()
        relations.append({"relation_id": relation_id, **relation_body})

    candidates.sort(key=lambda item: item["candidate_id"])
    relations.sort(key=lambda item: item["relation_id"])
    candidate_set_body = {
        "schema": IDEONOMY_SCHEMA,
        "source_representation_ref": inspection["representation_ref"],
        "source_representation_id": inspection["representation_id"],
        "source_artifact_refs": inspection["source_artifact_refs"],
        "generator": {"id": generator_id, "version": generator_version},
        "candidate_count": len(candidates),
        "relation_count": len(relations),
        "candidates": candidates,
        "relations": relations,
        "authority": "candidate_generation_only",
        "epistemic_status": "unverified",
        "semantic_verification": "not_assessed",
        "qualification": False,
    }
    candidate_set_id = hashlib.sha256(canonical_json(candidate_set_body)).hexdigest()
    return {**candidate_set_body, "candidate_set_id": candidate_set_id}


def store_ideonomy_candidate_set(
    registry: MerlinRegistry,
    graph: MerlinKnowledgeGraph,
    candidate_set: Mapping[str, Any],
    *,
    project_id: str,
    source_repo: str,
    source_commit: str,
) -> dict[str, Any]:
    """Persist candidate set and idempotently project candidate nodes/relations."""
    if not isinstance(candidate_set, Mapping) or candidate_set.get("schema") != IDEONOMY_SCHEMA:
        raise ValueError("unsupported Ideonomy candidate-set schema")
    allowed_set_fields = {
        "schema", "source_representation_ref", "source_representation_id",
        "source_artifact_refs", "generator", "candidate_count", "relation_count",
        "candidates", "relations", "authority", "epistemic_status",
        "semantic_verification", "qualification", "candidate_set_id",
    }
    if set(candidate_set) != allowed_set_fields:
        raise ValueError("Ideonomy candidate set contains unsupported fields")
    source_rep_ref = ArtifactRef.from_mapping(
        candidate_set["source_representation_ref"]
    ).to_dict()
    inspection = inspect_knowledge_representation(registry, source_rep_ref)
    if inspection["representation_id"] != candidate_set.get("source_representation_id"):
        raise ValueError("Ideonomy source representation identity changed")
    if inspection["source_artifact_refs"] != candidate_set.get("source_artifact_refs"):
        raise ValueError("Ideonomy source artifact set changed")
    if (
        candidate_set.get("authority") != "candidate_generation_only"
        or candidate_set.get("semantic_verification") != "not_assessed"
    ):
        raise ValueError("Ideonomy candidate authority must remain candidate_generation_only")
    if candidate_set.get("epistemic_status") != "unverified" or candidate_set.get("qualification") is not False:
        raise ValueError("Ideonomy candidates cannot be marked verified or qualified")

    if candidate_set.get("source_representation_ref") != inspection["representation_ref"]:
        raise ValueError("Ideonomy source representation reference changed")
    generator = candidate_set.get("generator")
    if (
        not isinstance(generator, Mapping) or set(generator) != {"id", "version"}
        or not isinstance(generator.get("id"), str) or not generator.get("id", "").strip()
        or not isinstance(generator.get("version"), str) or not generator.get("version", "").strip()
        or len(generator.get("id", "")) > 128 or len(generator.get("version", "")) > 128
    ):
        raise ValueError("Ideonomy generator provenance is malformed")
    candidates = candidate_set.get("candidates")
    relations = candidate_set.get("relations")
    if (
        not isinstance(candidates, list)
        or len(candidates) > MAX_IDEONOMY_CANDIDATES
        or isinstance(candidate_set.get("candidate_count"), bool)
        or candidate_set.get("candidate_count") != len(candidates)
        or not isinstance(relations, list)
        or len(relations) > MAX_IDEONOMY_RELATIONS
        or isinstance(candidate_set.get("relation_count"), bool)
        or candidate_set.get("relation_count") != len(relations)
    ):
        raise ValueError("Ideonomy candidate or relation counts are invalid")
    valid_bindings = {canonical_json(binding) for binding in inspection["source_bindings"]}
    candidate_ids: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise ValueError("Ideonomy candidate must be an object")
        if set(candidate) != {
            "candidate_id", "kind", "content", "rationale", "source_bindings",
            "confidence_estimate", "confidence_semantics", "epistemic_status", "authority",
        }:
            raise ValueError("Ideonomy candidate contains unsupported fields")
        if (
            not isinstance(candidate.get("kind"), str) or candidate.get("kind") not in CANDIDATE_KINDS
            or not isinstance(candidate.get("content"), str) or not candidate.get("content", "").strip()
            or len(candidate.get("content", "")) > 8_192
            or candidate.get("content") != candidate.get("content", "").strip()
            or not isinstance(candidate.get("rationale"), str)
            or len(candidate.get("rationale", "")) > 4_096
            or candidate.get("rationale") != candidate.get("rationale", "").strip()
            or candidate.get("epistemic_status") != "unverified"
            or candidate.get("authority") != "candidate_generation_only"
            or candidate.get("confidence_semantics") != "model_estimate_not_truth_probability"
        ):
            raise ValueError("Ideonomy candidate status, kind or content is invalid")
        selected = candidate.get("source_bindings")
        if (
            not isinstance(selected, list) or not selected
            or len(selected) > MAX_BINDINGS_PER_CANDIDATE
            or len({canonical_json(binding) for binding in selected}) != len(selected)
            or any(not isinstance(binding, Mapping) or canonical_json(binding) not in valid_bindings
                   or binding.get("locator_type") == "whole_artifact" for binding in selected)
        ):
            raise ValueError("Ideonomy candidate contains an unbound source locator")
        confidence = candidate.get("confidence_estimate")
        if confidence is not None and (
            isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not 0.0 <= float(confidence) <= 1.0
        ):
            raise ValueError("Ideonomy candidate confidence estimate is invalid")
        candidate_body = {
            "source_representation_id": inspection["representation_id"],
            "generator": {"id": generator["id"], "version": generator["version"]},
            "kind": candidate["kind"],
            "content": candidate["content"],
            "rationale": candidate["rationale"],
            "source_bindings": selected,
            "confidence_estimate": float(confidence) if confidence is not None else None,
        }
        expected_id = hashlib.sha256(canonical_json(candidate_body)).hexdigest()
        if candidate.get("candidate_id") != expected_id or expected_id in candidate_ids:
            raise ValueError("Ideonomy candidate identity is invalid or duplicated")
        candidate_ids.add(expected_id)

    relation_keys: set[tuple[str, str, str]] = set()
    for relation in relations:
        if not isinstance(relation, Mapping) or set(relation) != {
            "relation_id", "subject_candidate_id", "predicate",
            "object_candidate_id", "rationale",
        }:
            raise ValueError("Ideonomy relation must contain only the canonical fields")
        subject = relation.get("subject_candidate_id")
        object_ = relation.get("object_candidate_id")
        predicate = relation.get("predicate")
        rationale = relation.get("rationale")
        if (
            not isinstance(subject, str) or not isinstance(object_, str)
            or subject not in candidate_ids or object_ not in candidate_ids
            or not isinstance(predicate, str) or predicate not in EDGE_TYPES or subject == object_
            or not isinstance(rationale, str) or len(rationale) > 4_096
            or rationale != rationale.strip()
        ):
            raise ValueError("Ideonomy relation endpoints or predicate are invalid")
        relation_key = (subject, predicate, object_)
        if relation_key in relation_keys:
            raise ValueError("Ideonomy relation tuple is duplicated")
        relation_keys.add(relation_key)
        relation_body = {
            "subject_candidate_id": subject,
            "predicate": predicate,
            "object_candidate_id": object_,
            "rationale": rationale,
        }
        expected_relation_id = hashlib.sha256(canonical_json(relation_body)).hexdigest()
        if relation.get("relation_id") != expected_relation_id:
            raise ValueError("Ideonomy relation identity is invalid")

    candidate_set_body = {
        key: value for key, value in candidate_set.items()
        if key != "candidate_set_id"
    }
    expected_set_id = hashlib.sha256(canonical_json(candidate_set_body)).hexdigest()
    if candidate_set.get("candidate_set_id") != expected_set_id:
        raise ValueError("Ideonomy candidate-set identity does not match its canonical content")

    source_refs = [source_rep_ref] + inspection["source_artifact_refs"]
    source_bindings = [{
        "artifact_ref": source_rep_ref,
        "locator_type": "whole_artifact",
        "locator": "source text extraction representation",
    }] + inspection["source_bindings"]
    source_bindings = _dedupe_bindings(source_bindings)

    generator = candidate_set.get("generator")
    if not isinstance(generator, Mapping):
        raise ValueError("Ideonomy generator provenance is missing")
    stored = store_knowledge_representation(
        registry,
        graph,
        project_id=project_id,
        representation_type="ideonomy_candidates",
        payload=dict(candidate_set),
        source_refs=source_refs,
        source_bindings=source_bindings,
        tool_id=str(generator["id"]),
        tool_version=str(generator["version"]),
        loss_character="unknown",
        source_repo=source_repo,
        source_commit=source_commit,
    )

    representation_node_id = stored["graph_node_id"]
    candidate_node_ids: dict[str, str] = {}
    candidates = candidate_set.get("candidates")
    relations = candidate_set.get("relations")
    if not isinstance(candidates, list) or not isinstance(relations, list):
        raise ValueError("Ideonomy candidate set is malformed")
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        node_id = _candidate_node_id(candidate_id)
        candidate_node_ids[candidate_id] = node_id
        first_source = candidate["source_bindings"][0]["artifact_ref"]
        graph.add_node(GraphNode(
            node_id,
            _NODE_TYPE_BY_KIND[candidate["kind"]],
            candidate["content"][:240],
            {
                "candidate_set_id": candidate_set["candidate_set_id"],
                "candidate_id": candidate_id,
                "candidate_kind": candidate["kind"],
                "content": candidate["content"],
                "rationale": candidate["rationale"],
                "source_bindings": candidate["source_bindings"],
                "confidence_estimate": candidate["confidence_estimate"],
                "confidence_semantics": candidate["confidence_semantics"],
                "epistemic_status": "unverified",
                "authority": "candidate_generation_only",
                "representation_ref": stored["representation_ref"],
            },
            evidence_class="unverified_candidate",
            source_uri="registry://sha256/" + first_source["sha256"],
        ))
        graph.add_edge(GraphEdge(
            representation_node_id, "contains", node_id,
            {
                "candidate_set_id": candidate_set["candidate_set_id"],
                "candidate_id": candidate_id,
                "epistemic_status": "unverified",
            },
        ))
        by_source: dict[bytes, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
        for binding in candidate["source_bindings"]:
            source_ref = binding["artifact_ref"]
            key = canonical_json(source_ref)
            if key not in by_source:
                by_source[key] = (source_ref, [])
            by_source[key][1].append(binding)
        for source_ref, bindings in by_source.values():
            graph.add_edge(GraphEdge(
                node_id, "derived_from", _source_node_id(source_ref),
                {
                    "candidate_id": candidate_id,
                    "source_artifact_ref": source_ref,
                    "source_bindings": bindings,
                },
            ))

    for relation in relations:
        graph.add_edge(GraphEdge(
            candidate_node_ids[relation["subject_candidate_id"]],
            relation["predicate"],
            candidate_node_ids[relation["object_candidate_id"]],
            {
                "relation_id": relation["relation_id"],
                "candidate_set_id": candidate_set["candidate_set_id"],
                "rationale": relation["rationale"],
                "epistemic_status": "unverified",
            },
        ))

    return {
        "candidate_set": dict(candidate_set),
        "stored_representation": stored,
        "candidate_graph_node_ids": candidate_node_ids,
        "authority": "candidate_generation_only",
        "semantic_verification": "not_assessed",
        "qualification": False,
    }


__all__ = [
    "IDEONOMY_SCHEMA", "IDEONOMY_INPUT_SCHEMA", "CANDIDATE_KINDS",
    "MAX_IDEONOMY_CANDIDATES", "MAX_IDEONOMY_RELATIONS",
    "MAX_IDEONOMY_INPUT_CHARS", "MAX_IDEONOMY_SOURCE_BINDINGS",
    "IdeonomyUnavailableError", "ideonomy_capability",
    "enumerate_ideonomy_candidates", "store_ideonomy_candidate_set",
]
