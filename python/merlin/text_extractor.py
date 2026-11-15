"""Strict UTF-8 text/Markdown extraction with exact source byte and line locators."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from merlin.artifact_ref import ArtifactRef
from merlin.knowledge_compression import canonical_json, store_knowledge_representation
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import ArtifactSizeLimitError, MAX_ARTIFACT_READ_BYTES, MerlinRegistry


EXTRACTION_SCHEMA = "merlin-text-extraction/1"
EXTRACTOR_ID = "merlin.utf8-text-markdown"
EXTRACTOR_VERSION = "1.0.0"
MAX_TEXT_SEGMENTS = 5_000

_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^ {0,3}([\x60]{3,}|~{3,})(.*)$")
_LIST_RE = re.compile(r"^ {0,3}(?:[-+*]|[0-9]{1,9}[.)])\s+")
_QUOTE_RE = re.compile(r"^ {0,3}>\s?")


def _split_utf8_lines(raw: bytes) -> list[dict[str, Any]]:
    """Split bytes without normalizing line endings or losing byte offsets."""
    result: list[dict[str, Any]] = []
    offset = 0
    for number, chunk in enumerate(raw.splitlines(keepends=True), start=1):
        if chunk.endswith(b"\r\n"):
            body, ending = chunk[:-2], "\r\n"
        elif chunk.endswith(b"\n"):
            body, ending = chunk[:-1], "\n"
        elif chunk.endswith(b"\r"):
            body, ending = chunk[:-1], "\r"
        else:
            body, ending = chunk, ""
        result.append({
            "number": number,
            "start": offset,
            "end": offset + len(chunk),
            "text": body.decode("utf-8", errors="strict"),
            "ending": ending,
            "raw": chunk,
        })
        offset += len(chunk)
    return result


def _resolve_format(logical_path: str, requested: str) -> str:
    if requested not in {"auto", "plain_text", "markdown"}:
        raise ValueError("format must be auto, plain_text, or markdown")
    if requested != "auto":
        return requested
    return "markdown" if logical_path.lower().endswith((".md", ".markdown", ".mdown")) else "plain_text"


def extract_text_artifact(
    registry: MerlinRegistry,
    source_ref: Mapping[str, Any],
    *,
    format: str = "auto",
    max_bytes: int = MAX_ARTIFACT_READ_BYTES,
    max_segments: int = MAX_TEXT_SEGMENTS,
) -> dict[str, Any]:
    """Extract UTF-8 text into source-bound segments without altering source bytes.

    Markdown recognition is limited to ATX headings, fenced code, contiguous
    list items, blockquotes and paragraphs. Each segment retains an exact
    half-open UTF-8 byte range and a one-based inclusive line range.
    """
    if (isinstance(max_bytes, bool) or not isinstance(max_bytes, int)
            or not 1 <= max_bytes <= MAX_ARTIFACT_READ_BYTES):
        raise ValueError("max_bytes must be between 1 and 25 MiB")
    if (isinstance(max_segments, bool) or not isinstance(max_segments, int)
            or not 1 <= max_segments <= MAX_TEXT_SEGMENTS):
        raise ValueError("max_segments must be between 1 and 5,000")

    ref = ArtifactRef.from_mapping(source_ref)
    selected_format = _resolve_format(ref.logical_path, format)
    try:
        stored = registry.read_artifact_ref(ref.to_dict(), max_bytes=max_bytes)
    except ArtifactSizeLimitError as exc:
        raise ValueError("source artifact exceeds the configured text extraction byte limit") from exc

    raw = stored["content"]
    raw.decode("utf-8", errors="strict")
    lines = _split_utf8_lines(raw)
    segments: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = [{
        "artifact_ref": ref.to_dict(),
        "locator_type": "whole_artifact",
        "locator": "complete original UTF-8 source",
    }]

    def add_segment(kind: str, first: int, last: int, **metadata: Any) -> None:
        if len(segments) >= max_segments:
            raise ValueError("text extraction exceeds the configured segment limit")
        start = lines[first]["start"]
        end = lines[last]["end"]
        segment_bytes = raw[start:end]
        byte_locator = {"start": start, "end_exclusive": end}
        line_locator = {"start": first + 1, "end": last + 1}
        segment_id = hashlib.sha256(canonical_json({
            "source_artifact_ref": ref.to_dict(),
            "kind": kind,
            "byte_range": byte_locator,
        })).hexdigest()
        segments.append({
            "segment_id": segment_id,
            "kind": kind,
            "text": segment_bytes.decode("utf-8", errors="strict"),
            "content_sha256": hashlib.sha256(segment_bytes).hexdigest(),
            "byte_range": byte_locator,
            "line_range": line_locator,
            **metadata,
        })
        bindings.append({
            "artifact_ref": ref.to_dict(),
            "locator_type": "byte_range",
            "locator": byte_locator,
        })

    i = 0
    paragraph_start: int | None = None

    def flush_paragraph(last_index: int) -> None:
        nonlocal paragraph_start
        if paragraph_start is not None:
            add_segment("paragraph", paragraph_start, last_index)
            paragraph_start = None

    while i < len(lines):
        line_text = lines[i]["text"]
        if not line_text.strip():
            if paragraph_start is not None:
                flush_paragraph(i - 1)
            i += 1
            continue

        if selected_format == "markdown":
            heading = _HEADING_RE.match(line_text)
            if heading:
                if paragraph_start is not None:
                    flush_paragraph(i - 1)
                add_segment("heading", i, i, level=len(heading.group(1)))
                i += 1
                continue

            fence = _FENCE_RE.match(line_text)
            if fence:
                if paragraph_start is not None:
                    flush_paragraph(i - 1)
                marker = fence.group(1)
                marker_char = marker[0]
                close_re = re.compile(rf"^ {{0,3}}{re.escape(marker_char)}{{{len(marker)},}}\s*$")
                end_index = i
                closed = False
                for candidate in range(i + 1, len(lines)):
                    if close_re.match(lines[candidate]["text"]):
                        end_index = candidate
                        closed = True
                        break
                if not closed:
                    end_index = len(lines) - 1
                add_segment("code_block", i, end_index, closed=closed, fence=marker)
                i = end_index + 1
                continue

            if _LIST_RE.match(line_text):
                if paragraph_start is not None:
                    flush_paragraph(i - 1)
                end_index = i
                while end_index + 1 < len(lines) and _LIST_RE.match(lines[end_index + 1]["text"]):
                    end_index += 1
                add_segment("list", i, end_index)
                i = end_index + 1
                continue

            if _QUOTE_RE.match(line_text):
                if paragraph_start is not None:
                    flush_paragraph(i - 1)
                end_index = i
                while end_index + 1 < len(lines) and _QUOTE_RE.match(lines[end_index + 1]["text"]):
                    end_index += 1
                add_segment("blockquote", i, end_index)
                i = end_index + 1
                continue

        if paragraph_start is None:
            paragraph_start = i
        i += 1

    if paragraph_start is not None:
        flush_paragraph(len(lines) - 1)

    extraction_body = {
        "schema": EXTRACTION_SCHEMA,
        "source_artifact_ref": ref.to_dict(),
        "source_media_type": stored["resolution"].get("media_type"),
        "source_bytes": len(raw),
        "source_sha256": ref.sha256,
        "encoding": "utf-8",
        "format": selected_format,
        "extractor": {"id": EXTRACTOR_ID, "version": EXTRACTOR_VERSION},
        "segment_count": len(segments),
        "segments": segments,
        "source_bindings": bindings,
        "warnings": [
            "UTF-8 text only; no fallback decoding or Unicode normalization.",
            "Markdown recognition is structural and limited to ATX headings and fenced blocks.",
            "Original source bytes remain authoritative; extracted text is a derived view.",
        ],
    }
    extraction_id = hashlib.sha256(canonical_json(extraction_body)).hexdigest()
    return {**extraction_body, "extraction_id": extraction_id}


def store_text_extraction(
    registry: MerlinRegistry,
    graph: MerlinKnowledgeGraph,
    source_ref: Mapping[str, Any],
    *,
    project_id: str,
    source_repo: str,
    source_commit: str,
    format: str = "auto",
    max_bytes: int = MAX_ARTIFACT_READ_BYTES,
    max_segments: int = MAX_TEXT_SEGMENTS,
) -> dict[str, Any]:
    """Persist the extraction as a derived representation in canonical stores."""
    extraction = extract_text_artifact(
        registry, source_ref, format=format,
        max_bytes=max_bytes, max_segments=max_segments,
    )
    stored = store_knowledge_representation(
        registry,
        graph,
        project_id=project_id,
        representation_type="text_extraction",
        payload=extraction,
        source_refs=[ArtifactRef.from_mapping(source_ref).to_dict()],
        source_bindings=extraction["source_bindings"],
        tool_id=EXTRACTOR_ID,
        tool_version=EXTRACTOR_VERSION,
        loss_character="unknown",
        source_repo=source_repo,
        source_commit=source_commit,
    )
    return {"extraction": extraction, "stored_representation": stored}


__all__ = [
    "EXTRACTION_SCHEMA", "EXTRACTOR_ID", "EXTRACTOR_VERSION",
    "MAX_TEXT_SEGMENTS", "extract_text_artifact", "store_text_extraction",
]
