"""Privacy-filtered importer for Gemini master-handoff conversation sections.

The handoff file is a structured summary, not a raw Gemini transcript export.
This importer preserves selected complete sections verbatim, indexes prompt and
response markers without replacing the source text, and stores only an explicit
allowlist. It never stores the complete source archive, so excluded personal
sections are not copied into Merlin's project knowledge store.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from merlin.knowledge_graph import GraphEdge, GraphNode

PARSER_VERSION = "1.0"
MAX_ARCHIVE_BYTES = 50_000_000

_HEADER_RE = re.compile(
    r"^\s*Chat\s+(?P<ordinal>\d+)\s+[—–-]\s+"
    r"(?P<conversation_id>c_[0-9a-f]{8,64}):\s*"
    r"(?P<title>.*?)\s+\((?P<meta>[^)]*)\)\s*$"
)
_EXPECTED_COUNT_RE = re.compile(
    r"Detailed Full-Context Breakdown of All\s+(\d+)\s+Conversations",
    re.IGNORECASE,
)
_CONVERSATION_DETAIL_END_RE = re.compile(
    r"^\s*3\.\s+Master Chronological Ledger\b", re.IGNORECASE
)

_PROMPT_MARKER_RE = re.compile(
    r"^\*\s*(?:User Prompts?:|Turn\s+\d+\b)", re.IGNORECASE
)
_RESPONSE_MARKER_RE = re.compile(
    r"^\*\s*(?:Execution\s*&\s*Synthesis:|Deliverables Created:|"
    r"Technical\s*&\s*Mathematical Achievements:|"
    r"Key Restored Equations|Restored Equations|Experiment\s+\d+)",
    re.IGNORECASE,
)


APPENDIX_SPECS = {
    "milestone_ledger": {
        "title": "Master Chronological Ledger of Historical Milestones",
        "start": "3. Master Chronological Ledger of All Historical Milestones",
        "end": "4. Active Custom Skills, Long-Term Personalization Context & Google Drive Inventory",
    },
    "custom_skill_inventory": {
        "title": "Active Custom Skills Inventory",
        "start": "4.1 Complete Inventory of Your 7 Active Custom User Skills",
        "end": "4.2 Recovered Long-Term Personalization & Commercial/Personal Context",
    },
    "math_kung_fu_master_prompt": {
        "title": "Math Kung Fu Master Prompt",
        "start": "5.1 Ready-to-Use",
        "end": "5.2 Complete Adaptive Beginner-to-Master Freestyle Rap Training System & Toolbox",
    },
    "freestyle_rap_training_system": {
        "title": "Adaptive Beginner-to-Master Freestyle Rap Training System",
        "start": "5.2 Complete Adaptive Beginner-to-Master Freestyle Rap Training System & Toolbox",
        "end": "6. Next-Session Quick-Start Commands & Recommended Continuation Tracks",
    },
    "quick_start_merlin_studio": {
        "title": "Merlin Studio Quick Start",
        "start": "1. Launch M.E.R.L.I.N. × Sui × CACE-MCFC v34.0 Studio Locally:",
        "end": "2. Run the 20-Module M.E.R.L.I.N. v27 Self-Improving Engine",
    },
    "quick_start_self_improvement_engine": {
        "title": "Merlin Self-Improvement Engine Quick Start",
        "start": "2. Run the 20-Module M.E.R.L.I.N. v27 Self-Improving Engine",
        "end": "3. Launch Your Local Atrix Natal, Witch & Psychometric Suite",
    },
    "research_frontiers": {
        "title": "Prioritized Next Research and Engineering Frontiers",
        "start": "4. Prioritized Next Research & Engineering Frontiers:",
        "end": None,
    },
}


class GeminiHandoffError(ValueError):
    """The supplied Gemini handoff cannot be safely indexed or imported."""


class IncompleteGeminiHandoff(GeminiHandoffError):
    """The parsed conversation count does not match the handoff's declared count."""


@dataclass(frozen=True)
class GeminiHandoffConversation:
    ordinal: int
    conversation_id: str
    title: str
    header_metadata: str
    timestamp: str
    status: str
    status_details: str
    raw_text: str
    start_line: int
    end_line: int

    @property
    def raw_sha256(self) -> str:
        return hashlib.sha256(self.raw_text.encode("utf-8")).hexdigest()

    @property
    def prompt_excerpts(self) -> tuple[str, ...]:
        """Index hints only; raw_text remains the authoritative source."""
        return tuple(
            line.strip()
            for line in self.raw_text.splitlines()
            if _PROMPT_MARKER_RE.match(line.strip())
        )

    @property
    def response_markers(self) -> tuple[str, ...]:
        """Heading markers only; no response text is discarded or rewritten."""
        return tuple(
            line.strip()
            for line in self.raw_text.splitlines()
            if _RESPONSE_MARKER_RE.match(line.strip())
        )


@dataclass(frozen=True)
class GeminiHandoffAppendix:
    appendix_id: str
    title: str
    raw_text: str
    start_line: int
    end_line: int

    @property
    def raw_sha256(self) -> str:
        return hashlib.sha256(self.raw_text.encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _normalize_context_metadata(
    metadata: Mapping[str, Mapping[str, Any]] | None,
    allowed_ids: set[str],
    context_label: str,
) -> dict[str, dict[str, Any]]:
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise GeminiHandoffError(f"{context_label}_metadata must be a mapping")
    unknown_ids = sorted(set(metadata) - allowed_ids)
    if unknown_ids:
        raise GeminiHandoffError(f"{context_label} metadata references IDs outside its allowlist")
    normalized: dict[str, dict[str, Any]] = {}
    allowed = {"domain", "relevance", "merlin_capabilities", "evidence_handling"}
    for context_id, item in metadata.items():
        if not isinstance(item, Mapping) or set(item) - allowed:
            raise GeminiHandoffError(f"{context_label} metadata has an invalid shape")
        domain = item.get("domain")
        relevance = item.get("relevance", "supporting_research")
        capabilities = item.get("merlin_capabilities", [])
        evidence_handling = item.get("evidence_handling", "source_context_unverified")
        if not isinstance(domain, str) or not domain.strip() or len(domain) > 80:
            raise GeminiHandoffError(f"{context_label} metadata requires a short domain")
        if not isinstance(relevance, str) or not relevance.strip() or len(relevance) > 80:
            raise GeminiHandoffError(f"{context_label} metadata relevance must be a short string")
        if not isinstance(capabilities, (list, tuple)) or any(
            not isinstance(value, str) or not value.strip() or len(value) > 80
            for value in capabilities
        ):
            raise GeminiHandoffError("merlin_capabilities must be a list of short strings")
        if not isinstance(evidence_handling, str) or not evidence_handling.strip() or len(evidence_handling) > 120:
            raise GeminiHandoffError("evidence_handling must be a short string")
        normalized[context_id] = {
            "domain": domain.strip(),
            "relevance": relevance.strip(),
            "merlin_capabilities": list(capabilities),
            "evidence_handling": evidence_handling.strip(),
        }
    return dict(sorted(normalized.items()))


def _header_parts(metadata: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in metadata.split("·")]
    timestamp = parts[0] if parts else ""
    status_part = parts[1] if len(parts) > 1 else "UNKNOWN"
    status_tokens = status_part.split(maxsplit=1)
    status = status_tokens[0].upper() if status_tokens else "UNKNOWN"
    details = []
    if len(status_tokens) > 1:
        details.append(status_tokens[1])
    details.extend(parts[2:])
    return timestamp, status, " · ".join(details)


def parse_gemini_handoff(
    text: str,
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Parse the detailed Chat N — c_<id> sections without rewriting their text."""
    if not isinstance(text, str) or not text.strip():
        raise GeminiHandoffError("handoff text must be a non-empty UTF-8 string")

    lines = text.splitlines(keepends=True)
    headers: list[tuple[int, re.Match[str]]] = []
    for index, line in enumerate(lines):
        match = _HEADER_RE.match(line.rstrip("\r\n"))
        if match:
            headers.append((index, match))

    if not headers:
        raise GeminiHandoffError("no detailed 'Chat N — c_<id>' sections were found")

    expected_match = _EXPECTED_COUNT_RE.search(text)
    expected_count = int(expected_match.group(1)) if expected_match else None
    detail_end_index = next(
        (index for index, line in enumerate(lines)
         if _CONVERSATION_DETAIL_END_RE.match(line.rstrip("\r\n"))),
        len(lines),
    )

    conversations: list[GeminiHandoffConversation] = []
    seen_ids: set[str] = set()
    seen_ordinals: set[int] = set()
    for position, (start_index, match) in enumerate(headers):
        if position + 1 < len(headers):
            end_index = headers[position + 1][0]
        else:
            end_index = detail_end_index if detail_end_index > start_index else len(lines)
        conversation_id = match.group("conversation_id")
        ordinal = int(match.group("ordinal"))
        if conversation_id in seen_ids:
            raise GeminiHandoffError(f"duplicate conversation ID: {conversation_id}")
        if ordinal in seen_ordinals:
            raise GeminiHandoffError(f"duplicate conversation ordinal: {ordinal}")
        seen_ids.add(conversation_id)
        seen_ordinals.add(ordinal)

        raw_text = "".join(lines[start_index:end_index])
        timestamp, status, status_details = _header_parts(match.group("meta"))
        conversations.append(
            GeminiHandoffConversation(
                ordinal=ordinal,
                conversation_id=conversation_id,
                title=match.group("title").strip(),
                header_metadata=match.group("meta").strip(),
                timestamp=timestamp,
                status=status,
                status_details=status_details,
                raw_text=raw_text,
                start_line=start_index + 1,
                end_line=end_index,
            )
        )

    conversations.sort(key=lambda item: item.ordinal)
    if expected_count is not None and require_complete and len(conversations) != expected_count:
        raise IncompleteGeminiHandoff(
            f"handoff declares {expected_count} conversations but {len(conversations)} sections parsed"
        )

    return {
        "expected_count": expected_count,
        "parsed_count": len(conversations),
        "completeness": (
            "complete"
            if expected_count is None or expected_count == len(conversations)
            else "incomplete"
        ),
        "conversations": tuple(conversations),
    }


def extract_gemini_appendices(
    text: str,
    included_appendix_ids: Sequence[str],
) -> tuple[GeminiHandoffAppendix, ...]:
    """Extract only named technical appendices; personal-context sections are not allowlisted."""
    if not isinstance(text, str) or not text.strip():
        raise GeminiHandoffError("appendix source text must be non-empty")
    if not isinstance(included_appendix_ids, (list, tuple)):
        raise GeminiHandoffError("included_appendix_ids must be a list or tuple")
    if any(not isinstance(item, str) for item in included_appendix_ids):
        raise GeminiHandoffError("appendix IDs must be strings")
    if len(set(included_appendix_ids)) != len(included_appendix_ids):
        raise GeminiHandoffError("appendix allowlist contains duplicates")
    unknown = sorted(set(included_appendix_ids) - set(APPENDIX_SPECS))
    if unknown:
        raise GeminiHandoffError("appendix allowlist contains unsupported section IDs")

    lines = text.splitlines(keepends=True)

    def locate(marker: str, after: int = 0) -> int | None:
        for index in range(after, len(lines)):
            if lines[index].strip().startswith(marker):
                return index
        return None

    extracted = []
    for appendix_id in included_appendix_ids:
        spec = APPENDIX_SPECS[appendix_id]
        start_index = locate(spec["start"])
        if start_index is None:
            raise GeminiHandoffError(f"requested technical appendix is missing: {appendix_id}")
        end_marker = spec["end"]
        if end_marker is None:
            end_index = len(lines)
        else:
            end_index = locate(end_marker, start_index + 1)
            if end_index is None:
                raise GeminiHandoffError(f"technical appendix boundary is missing: {appendix_id}")
        if end_index <= start_index:
            raise GeminiHandoffError(f"technical appendix has an invalid range: {appendix_id}")
        raw_text = "".join(lines[start_index:end_index])
        extracted.append(
            GeminiHandoffAppendix(
                appendix_id=appendix_id,
                title=spec["title"],
                raw_text=raw_text,
                start_line=start_index + 1,
                end_line=end_index,
            )
        )
    extracted.sort(key=lambda item: item.start_line)
    return tuple(extracted)


def ingest_gemini_handoff(
    store: Any,
    project_id: str,
    archive_bytes: bytes,
    *,
    source_filename: str,
    included_conversation_ids: Sequence[str],
    conversation_metadata: Mapping[str, Mapping[str, Any]] | None = None,
    included_appendix_ids: Sequence[str] = (),
    appendix_metadata: Mapping[str, Mapping[str, Any]] | None = None,
    max_archive_bytes: int = MAX_ARCHIVE_BYTES,
) -> dict[str, Any]:
    """Import explicitly selected handoff sections into the canonical Merlin store.

    The full archive is hashed but not retained. Only allowlisted conversation
    sections and their derived index records are written to the project registry.
    """
    if not isinstance(archive_bytes, bytes) or not archive_bytes:
        raise GeminiHandoffError("archive_bytes must be non-empty bytes")
    if len(archive_bytes) > max_archive_bytes:
        raise GeminiHandoffError("handoff archive exceeds the configured byte limit")
    if not isinstance(source_filename, str) or not source_filename.strip():
        raise GeminiHandoffError("source_filename is required")
    if not isinstance(included_conversation_ids, (list, tuple)) or not included_conversation_ids:
        raise GeminiHandoffError("an explicit non-empty conversation allowlist is required")

    selected_ids = tuple(included_conversation_ids)
    if any(not isinstance(item, str) or not re.fullmatch(r"c_[0-9a-f]{8,64}", item) for item in selected_ids):
        raise GeminiHandoffError("allowlist entries must be Gemini conversation IDs")
    if len(set(selected_ids)) != len(selected_ids):
        raise GeminiHandoffError("conversation allowlist contains duplicates")

    try:
        text = archive_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise GeminiHandoffError("handoff archive must be valid UTF-8 text") from exc

    parsed = parse_gemini_handoff(text, require_complete=True)
    by_id = {item.conversation_id: item for item in parsed["conversations"]}
    unknown = sorted(set(selected_ids) - set(by_id))
    if unknown:
        raise GeminiHandoffError("allowlist contains IDs absent from the supplied handoff")
    normalized_metadata = _normalize_context_metadata(conversation_metadata, set(selected_ids), "conversation")
    if not isinstance(included_appendix_ids, (list, tuple)):
        raise GeminiHandoffError("included_appendix_ids must be a list or tuple")
    if any(not isinstance(item, str) for item in included_appendix_ids):
        raise GeminiHandoffError("appendix IDs must be strings")
    if len(set(included_appendix_ids)) != len(included_appendix_ids):
        raise GeminiHandoffError("appendix allowlist contains duplicates")
    appendices = extract_gemini_appendices(text, included_appendix_ids)
    normalized_appendix_metadata = _normalize_context_metadata(
        appendix_metadata, set(included_appendix_ids), "appendix"
    )

    # This lookup both validates the project and avoids guessing project ownership.
    inventory = store.registry.inventory(project_id)
    source_name = source_filename.replace(chr(92), "/").split("/")[-1][:255]
    archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    selected = [
        item for item in parsed["conversations"]
        if item.conversation_id in set(selected_ids)
    ]
    selected.sort(key=lambda item: item.ordinal)

    project_key = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:12]
    policy_payload = {
        "project_id": project_id,
        "source_filename": source_name,
        "mode": "explicit_allowlist_only",
        "included_conversation_ids": sorted(selected_ids),
        "conversation_metadata": normalized_metadata,
        "included_appendix_ids": sorted(included_appendix_ids),
        "appendix_metadata": normalized_appendix_metadata,
        "parser_version": PARSER_VERSION,
    }
    policy_sha256 = hashlib.sha256(_canonical_json(policy_payload)).hexdigest()
    intake_root = f"intake/gemini/{archive_sha256}/{policy_sha256[:12]}"
    source_node_id = f"source:gemini-handoff:{project_key}:{archive_sha256}:{policy_sha256[:12]}"

    source_payload = {
        "source_type": "gemini_master_handoff",
        "source_filename": source_name,
        "source_archive_sha256": archive_sha256,
        "source_archive_size_bytes": len(archive_bytes),
        "source_archive_bytes_retained": False,
        "source_granularity": "handoff_summary_and_selected_technical_appendices",
        "expected_conversation_count": parsed["expected_count"],
        "parsed_conversation_count": parsed["parsed_count"],
        "imported_conversation_count": len(selected),
        "excluded_conversation_count": parsed["parsed_count"] - len(selected),
        "available_appendix_count": len(APPENDIX_SPECS),
        "imported_appendix_count": len(appendices),
        "not_imported_appendix_count": len(APPENDIX_SPECS) - len(appendices),
        "policy_sha256": policy_sha256,
        "parser_version": PARSER_VERSION,
    }

    project_node_id = f"project:{project_id}"
    if store.graph.get_node(project_node_id) is None:
        store.graph.add_node(
            GraphNode(
                node_id=project_node_id,
                node_type="project",
                label=inventory["name"],
                payload={"version": inventory["version"]},
                evidence_class="registry",
            )
        )
    store.graph.add_node(
        GraphNode(
            node_id=source_node_id,
            node_type="source",
            label=source_name,
            payload=source_payload,
            evidence_class="unreviewed",
        )
    )
    store.graph.add_edge(
        GraphEdge(
            source_id=project_node_id,
            relation="contains",
            target_id=source_node_id,
            payload={"role": "gemini_handoff_source", "source_archive_sha256": archive_sha256},
        )
    )

    imported: list[dict[str, Any]] = []
    for section in selected:
        raw_bytes = section.raw_text.encode("utf-8")
        raw_digest = section.raw_sha256
        raw_path = f"{intake_root}/conversations/{section.conversation_id}.txt"
        stored_raw_digest = store.put_artifact(
            project_id,
            raw_path,
            raw_bytes,
            "text/plain; charset=utf-8",
            artifact_type="source",
            evidence_class="unreviewed",
            metadata={
                "source_type": "gemini_conversation_handoff_section",
                "source_archive_sha256": archive_sha256,
                "conversation_id": section.conversation_id,
                "section_sha256": raw_digest,
                "source_start_line": section.start_line,
                "source_end_line": section.end_line,
                "source_granularity": "handoff_summary_not_raw_transcript",
            },
        )
        if stored_raw_digest != raw_digest:
            raise RuntimeError("stored conversation section digest does not match its source bytes")

        session_id = (
            f"session:gemini:{project_key}:{section.conversation_id}:"
            f"{archive_sha256[:12]}:{policy_sha256[:12]}"
        )
        index_payload = {
            "schema": "merlin-gemini-conversation-index/1",
            "parser_version": PARSER_VERSION,
            "source_filename": source_name,
            "source_archive_sha256": archive_sha256,
            "source_granularity": "handoff_summary_not_raw_transcript",
            "conversation_id": section.conversation_id,
            "ordinal": section.ordinal,
            "title": section.title,
            "timestamp": section.timestamp,
            "status": section.status,
            "status_details": section.status_details,
            "source_start_line": section.start_line,
            "source_end_line": section.end_line,
            "raw_section_sha256": raw_digest,
            "raw_section_logical_path": raw_path,
            "prompt_excerpts": list(section.prompt_excerpts),
            "response_markers": list(section.response_markers),
            "classification": normalized_metadata.get(section.conversation_id, {}),
            "index_notice": "Excerpts are navigation hints; the complete raw section artifact is authoritative.",
        }
        index_bytes = _canonical_json(index_payload)
        index_path = f"{intake_root}/conversations/{section.conversation_id}.index.json"
        index_digest = store.put_artifact(
            project_id,
            index_path,
            index_bytes,
            "application/json",
            artifact_type="artifact",
            evidence_class="unreviewed",
            metadata={
                "source_type": "gemini_conversation_index",
                "source_archive_sha256": archive_sha256,
                "conversation_id": section.conversation_id,
            },
        )

        store.graph.add_node(
            GraphNode(
                node_id=session_id,
                node_type="session",
                label=section.title,
                payload={
                    "conversation_id": section.conversation_id,
                    "ordinal": section.ordinal,
                    "timestamp": section.timestamp,
                    "status": section.status,
                    "source_archive_sha256": archive_sha256,
                    "raw_section_sha256": raw_digest,
                    "index_artifact_sha256": index_digest,
                    "classification": normalized_metadata.get(section.conversation_id, {}),
                    "source_granularity": "handoff_summary_not_raw_transcript",
                },
                evidence_class="unreviewed",
                source_uri=f"artifact:sha256:{stored_raw_digest}",
            )
        )
        store.graph.add_edge(
            GraphEdge(source_node_id, "contains", session_id, {"conversation_id": section.conversation_id})
        )
        store.graph.add_edge(
            GraphEdge(session_id, "contains", f"artifact:sha256:{stored_raw_digest}", {"role": "raw_handoff_section"})
        )
        store.graph.add_edge(
            GraphEdge(session_id, "contains", f"artifact:sha256:{index_digest}", {"role": "conversation_index"})
        )

        imported.append(
            {
                "conversation_id": section.conversation_id,
                "session_node_id": session_id,
                "ordinal": section.ordinal,
                "title": section.title,
                "status": section.status,
                "classification": normalized_metadata.get(section.conversation_id, {}),
                "raw_section_sha256": raw_digest,
                "raw_section_logical_path": raw_path,
                "index_artifact_sha256": index_digest,
                "index_logical_path": index_path,
                "prompt_excerpt_count": len(section.prompt_excerpts),
                "source_start_line": section.start_line,
                "source_end_line": section.end_line,
            }
        )

    imported_appendices: list[dict[str, Any]] = []
    for appendix in appendices:
        classification = normalized_appendix_metadata.get(appendix.appendix_id, {})
        raw_bytes = appendix.raw_text.encode("utf-8")
        raw_digest = appendix.raw_sha256
        logical_path = f"{intake_root}/appendices/{appendix.appendix_id}.txt"
        stored_digest = store.put_artifact(
            project_id,
            logical_path,
            raw_bytes,
            "text/plain; charset=utf-8",
            artifact_type="source",
            evidence_class="unreviewed",
            metadata={
                "source_type": "gemini_handoff_technical_appendix",
                "source_archive_sha256": archive_sha256,
                "appendix_id": appendix.appendix_id,
                "section_sha256": raw_digest,
                "source_start_line": appendix.start_line,
                "source_end_line": appendix.end_line,
                "source_granularity": "technical_handoff_appendix",
            },
        )
        if stored_digest != raw_digest:
            raise RuntimeError("stored appendix digest does not match its source bytes")
        appendix_node_id = (
            f"source:gemini-appendix:{project_key}:{archive_sha256[:12]}:"
            f"{policy_sha256[:12]}:{appendix.appendix_id}"
        )
        store.graph.add_node(
            GraphNode(
                node_id=appendix_node_id,
                node_type="source",
                label=appendix.title,
                payload={
                    "appendix_id": appendix.appendix_id,
                    "title": appendix.title,
                    "source_archive_sha256": archive_sha256,
                    "raw_section_sha256": raw_digest,
                    "logical_path": logical_path,
                    "source_start_line": appendix.start_line,
                    "source_end_line": appendix.end_line,
                    "source_granularity": "technical_handoff_appendix",
                    "classification": classification,
                },
                evidence_class="unreviewed",
                source_uri=f"artifact:sha256:{stored_digest}",
            )
        )
        store.graph.add_edge(
            GraphEdge(source_node_id, "contains", appendix_node_id, {"appendix_id": appendix.appendix_id})
        )
        store.graph.add_edge(
            GraphEdge(
                appendix_node_id,
                "contains",
                f"artifact:sha256:{stored_digest}",
                {"role": "raw_handoff_appendix"},
            )
        )
        imported_appendices.append(
            {
                "appendix_id": appendix.appendix_id,
                "title": appendix.title,
                "appendix_node_id": appendix_node_id,
                "raw_section_sha256": raw_digest,
                "logical_path": logical_path,
                "source_start_line": appendix.start_line,
                "source_end_line": appendix.end_line,
                "classification": classification,
            }
        )

    manifest = {
        "schema": "merlin-gemini-handoff-intake/1",
        "parser_version": PARSER_VERSION,
        "project_id": project_id,
        "source_filename": source_name,
        "source_archive_sha256": archive_sha256,
        "source_archive_size_bytes": len(archive_bytes),
        "source_archive_bytes_retained": False,
        "source_granularity": "handoff_summary_and_selected_technical_appendices",
        "expected_conversation_count": parsed["expected_count"],
        "parsed_conversation_count": parsed["parsed_count"],
        "imported_conversation_count": len(imported),
        "excluded_conversation_count": parsed["parsed_count"] - len(imported),
        "available_appendix_count": len(APPENDIX_SPECS),
        "imported_appendix_count": len(imported_appendices),
        "not_imported_appendix_count": len(APPENDIX_SPECS) - len(imported_appendices),
        "imported_appendices": imported_appendices,
        "policy": policy_payload,
        "policy_sha256": policy_sha256,
        "imported_conversations": imported,
        "epistemic_notice": (
            "Imported text is source context, not verified truth. Historical claims, "
            "benchmarks, proofs, and implementation statuses require their own evidence."
        ),
    }
    manifest_bytes = _canonical_json(manifest)
    manifest_path = f"{intake_root}/manifest.json"
    manifest_digest = store.put_artifact(
        project_id,
        manifest_path,
        manifest_bytes,
        "application/json",
        artifact_type="artifact",
        evidence_class="unreviewed",
        metadata={
            "source_type": "gemini_handoff_intake_manifest",
            "source_archive_sha256": archive_sha256,
            "policy_sha256": policy_sha256,
        },
    )
    store.graph.add_edge(
        GraphEdge(source_node_id, "contains", f"artifact:sha256:{manifest_digest}", {"role": "intake_manifest"})
    )

    return {
        **manifest,
        "source_node_id": source_node_id,
        "manifest_artifact_sha256": manifest_digest,
        "manifest_logical_path": manifest_path,
        "imported_appendices": imported_appendices,
        "registry_reconciliation": store.reconcile_project(project_id),
    }
