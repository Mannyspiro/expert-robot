"""Bounded, deterministic XML extraction for GovInfo legal source fixtures.

This is a structural extractor, not an XSD validator or legal-authority classifier.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any
import xml.etree.ElementTree as ET


DEFAULT_MAX_XML_BYTES = 25 * 1024 * 1024
PARSER_VERSION = "merlin-govinfo-xml/0.1"


@dataclass(frozen=True)
class LegalXmlRecord:
    record_type: str
    collection: str
    package_id: str
    source_sha256: str
    parser_version: str
    title: str | None
    document_number: str | None
    publication_date: str | None
    effective_date: str | None
    agency: tuple[str, ...]
    citation: str | None
    section_id: str | None
    section_number: str | None
    heading: str | None
    text: str
    extraction_warnings: tuple[str, ...] = ()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1].lower()


def _text(node: ET.Element) -> str:
    return " ".join(" ".join(node.itertext()).split())


def _first_text(root: ET.Element, names: set[str]) -> str | None:
    for node in root.iter():
        if _local(node.tag) in names:
            value = _text(node)
            if value:
                return value
    return None


def _all_text(root: ET.Element, names: set[str]) -> tuple[str, ...]:
    values = []
    for node in root.iter():
        if _local(node.tag) in names:
            value = _text(node)
            if value and value not in values:
                values.append(value)
    return tuple(values)


def parse_govinfo_xml(
    body: bytes,
    *,
    collection: str,
    package_id: str,
    max_bytes: int = DEFAULT_MAX_XML_BYTES,
) -> tuple[LegalXmlRecord, ...]:
    """Extract FR document-level or USLM section-level records from bounded XML."""
    if not isinstance(body, bytes):
        raise TypeError("body must be bytes")
    if not body or len(body) > max_bytes:
        raise ValueError("XML payload is empty or exceeds configured size limit")
    if max_bytes < 1 or max_bytes > 100 * 1024 * 1024:
        raise ValueError("max_bytes must be between 1 byte and 100 MiB")
    upper = body.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("DTD and entity declarations are not accepted")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError(f"malformed XML: {exc}") from exc

    digest = sha256(body).hexdigest()
    agencies = _all_text(root, {"agencyname", "agency"})
    title = _first_text(root, {"doctitle", "title", "heading"})
    document_number = _first_text(root, {"documentnumber", "document_number"})
    publication_date = _first_text(root, {"publicationdate", "date"})
    effective_date = _first_text(root, {"effectivedate", "effective_date"})
    citation = _first_text(root, {"citation", "cfrcitation", "uscitation"})
    warnings: list[str] = []
    if title is None:
        warnings.append("title_not_found")
    if publication_date is None:
        warnings.append("publication_date_not_found")

    section_nodes = [
        node for node in root.iter()
        if _local(node.tag) in {"section", "regulation"}
    ]
    records: list[LegalXmlRecord] = []
    if collection.upper() in {"USCODE", "STATUTE", "PLAW"} and section_nodes:
        for node in section_nodes:
            section_id = node.attrib.get("id") or node.attrib.get("{http://www.w3.org/XML/1998/namespace}id")
            number = _first_text(node, {"num", "sectionnumber"})
            heading = _first_text(node, {"heading", "subject"})
            records.append(LegalXmlRecord(
                record_type="statutory_section", collection=collection, package_id=package_id,
                source_sha256=digest, parser_version=PARSER_VERSION, title=title,
                document_number=document_number, publication_date=publication_date,
                effective_date=effective_date, agency=agencies, citation=citation,
                section_id=section_id, section_number=number, heading=heading,
                text=_text(node), extraction_warnings=tuple(warnings),
            ))
    else:
        records.append(LegalXmlRecord(
            record_type="federal_register_document" if collection.upper() == "FR" else "xml_document",
            collection=collection, package_id=package_id, source_sha256=digest,
            parser_version=PARSER_VERSION, title=title, document_number=document_number,
            publication_date=publication_date, effective_date=effective_date,
            agency=agencies, citation=citation, section_id=None, section_number=None,
            heading=None, text=_text(root), extraction_warnings=tuple(warnings),
        ))
    return tuple(records)


def record_dict(record: LegalXmlRecord) -> dict[str, Any]:
    return asdict(record)


__all__ = ["DEFAULT_MAX_XML_BYTES", "PARSER_VERSION", "LegalXmlRecord", "parse_govinfo_xml", "record_dict"]
