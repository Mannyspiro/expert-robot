"""Policy-bound legal source ingestion primitives.

This module creates auditable capture manifests. It does not bypass source terms,
authenticate a publisher, or decide whether a legal proposition is correct.
Network execution belongs in isolated Avrea jobs using explicit allowlists.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Iterable
from urllib.parse import urlsplit


ALLOWED_HOSTS = frozenset({
    "www.govinfo.gov", "api.govinfo.gov", "govinfo.gov",
    "www.azleg.gov", "azleg.gov",
    "azsos.gov", "www.azsos.gov", "apps.azsos.gov",
    "www.azcourts.gov", "azcourts.gov",
    "www.supremecourt.gov", "supremecourt.gov",
    "www.federalregister.gov", "federalregister.gov",
})
DEFAULT_MAX_CAPTURE_BYTES = 25 * 1024 * 1024

GOVINFO_COLLECTIONS = {
    "federal_register": "FR",
    "code_federal_regulations": "CFR",
    "united_states_code": "USCODE",
    "statutes_at_large": "STATUTE",
    "public_laws": "PLAW",
    "congressional_bill_status": "BILLSTATUS",
    "congressional_bills": "BILLS",
}


@dataclass(frozen=True)
class IngestionPolicy:
    max_capture_bytes: int = DEFAULT_MAX_CAPTURE_BYTES
    timeout_seconds: int = 20
    allowed_hosts: frozenset[str] = ALLOWED_HOSTS
    retain_content: bool = False
    require_human_license_review: bool = True

    def validate(self) -> None:
        if self.max_capture_bytes < 1 or self.max_capture_bytes > 100 * 1024 * 1024:
            raise ValueError("max_capture_bytes must be between 1 byte and 100 MiB")
        if not 1 <= self.timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be between 1 and 120")
        if not self.allowed_hosts:
            raise ValueError("at least one allowed host is required")


@dataclass(frozen=True)
class SourceCandidate:
    candidate_id: str
    jurisdiction_id: str
    collection: str
    title: str
    url: str
    source_type: str
    acquisition_mode: str
    notes: str = ""

    def validate(self, policy: IngestionPolicy = IngestionPolicy()) -> None:
        validate_source_url(self.url, policy.allowed_hosts)
        if not all(x.strip() for x in (self.candidate_id, self.jurisdiction_id, self.collection, self.title)):
            raise ValueError("candidate identity, jurisdiction, collection and title are required")
        if self.acquisition_mode not in {"api", "bulk_xml", "official_html", "official_pdf", "manual_review"}:
            raise ValueError("unsupported acquisition mode")


@dataclass(frozen=True)
class CaptureManifest:
    artifact_id: str
    source_candidate_id: str
    canonical_url: str
    final_url: str
    jurisdiction_id: str
    collection: str
    retrieved_at: str
    content_type: str
    byte_length: int
    sha256: str
    parser_version: str
    permitted_use: str
    retention_decision: str
    capture_status: str = "captured_unverified"

    def validate(self) -> None:
        validate_source_url(self.canonical_url)
        validate_source_url(self.final_url)
        timestamp = datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("retrieved_at must include a timezone")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError("invalid content SHA-256")
        if self.byte_length < 0:
            raise ValueError("byte_length cannot be negative")
        if self.capture_status not in {"captured_unverified", "metadata_only", "rejected"}:
            raise ValueError("unsupported capture status")


def validate_source_url(url: str, allowed_hosts: Iterable[str] = ALLOWED_HOSTS) -> None:
    parsed = urlsplit(url)
    hosts = set(allowed_hosts)
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in hosts:
        raise ValueError("source URL must use HTTPS and an explicitly allowed official host")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("embedded credentials and nonstandard ports are not permitted")
    if parsed.fragment:
        raise ValueError("source URL fragments are not accepted as canonical source locations")


def govinfo_bulk_index_urls(year: int | None = None) -> tuple[SourceCandidate, ...]:
    """Return public bulk index locations; no content is downloaded by this function."""
    if year is not None and not 1789 <= year <= 2200:
        raise ValueError("year is outside supported range")
    candidates = []
    for slug, collection in GOVINFO_COLLECTIONS.items():
        if collection in {"FR", "CFR"} and year is None:
            path = f"/bulkdata/{collection}"
        elif collection in {"FR", "CFR", "BILLSTATUS", "BILLS"}:
            path = f"/bulkdata/{collection}/{year or 2026}"
        else:
            path = f"/bulkdata/{collection}"
        candidates.append(SourceCandidate(
            candidate_id=f"govinfo:{slug}:{year or 'index'}",
            jurisdiction_id="US-FEDERAL",
            collection=collection,
            title=f"GovInfo {slug.replace('_', ' ').title()} bulk data",
            url="https://www.govinfo.gov" + path,
            source_type=("regulation" if collection in {"FR", "CFR"} else
                         "legislative_history" if collection in {"BILLSTATUS", "BILLS"} else "statute"),
            acquisition_mode="bulk_xml",
            notes="Discovery index only; select packages after metadata and licensing review.",
        ))
    return tuple(candidates)


def arizona_register_index(year: int) -> SourceCandidate:
    if not 1976 <= year <= 2200:
        raise ValueError("Arizona Register year is outside supported range")
    return SourceCandidate(
        candidate_id=f"azsos:register:{year}",
        jurisdiction_id="US-AZ",
        collection="Arizona Administrative Register",
        title=f"Arizona Administrative Register {year}",
        url=f"https://apps.azsos.gov/public_services/register/{year}/contents.htm",
        source_type="regulation",
        acquisition_mode="official_html",
        notes="Secretary of State identifies authenticated electronic Register as official; assess commercial-use terms before retaining/reusing content.",
    )


def build_capture_manifest(
    *,
    candidate: SourceCandidate,
    final_url: str,
    body: bytes,
    content_type: str,
    retrieved_at: str | None = None,
    parser_version: str = "merlin-legal-capture/0.1",
    permitted_use: str = "review_required",
    policy: IngestionPolicy = IngestionPolicy(),
) -> CaptureManifest:
    policy.validate()
    candidate.validate(policy)
    validate_source_url(final_url, policy.allowed_hosts)
    if len(body) > policy.max_capture_bytes:
        raise ValueError("capture exceeds configured maximum size")
    if permitted_use not in {"public_link_only", "retain_allowed", "licensed", "review_required", "restricted"}:
        raise ValueError("unsupported permitted_use")
    if not content_type.strip():
        raise ValueError("content_type is required")
    timestamp = retrieved_at or datetime.now(timezone.utc).isoformat()
    manifest = CaptureManifest(
        artifact_id=f"sha256:{sha256(body).hexdigest()}",
        source_candidate_id=candidate.candidate_id,
        canonical_url=candidate.url,
        final_url=final_url,
        jurisdiction_id=candidate.jurisdiction_id,
        collection=candidate.collection,
        retrieved_at=timestamp,
        content_type=content_type.split(";", 1)[0].strip().lower(),
        byte_length=len(body),
        sha256=sha256(body).hexdigest(),
        parser_version=parser_version,
        permitted_use=permitted_use,
        retention_decision="retain" if policy.retain_content and permitted_use in {"retain_allowed", "licensed"} else "metadata_only",
    )
    manifest.validate()
    return manifest


def manifest_dict(manifest: CaptureManifest) -> dict:
    manifest.validate()
    return asdict(manifest)


__all__ = [
    "ALLOWED_HOSTS", "DEFAULT_MAX_CAPTURE_BYTES", "GOVINFO_COLLECTIONS",
    "CaptureManifest", "IngestionPolicy", "SourceCandidate", "arizona_register_index",
    "build_capture_manifest", "govinfo_bulk_index_urls", "manifest_dict",
    "validate_source_url",
]
