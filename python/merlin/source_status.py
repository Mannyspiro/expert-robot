"""Authority-aware source status resolution for opportunity records."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

VALID_ROLES = {"issuing_authority", "secondary"}
VALID_STATUSES = {"open", "closed", "not_listed", "unknown"}


@dataclass(frozen=True)
class SourceObservation:
    role: str
    status: str
    source_url: str
    source_name: str
    observed_on: str

    def __post_init__(self) -> None:
        if self.role not in VALID_ROLES:
            raise ValueError("unsupported source role")
        if self.status not in VALID_STATUSES:
            raise ValueError("unsupported observed status")
        parsed = urlparse(self.source_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("source_url must be an absolute HTTPS URL")
        date.fromisoformat(self.observed_on)


@dataclass(frozen=True)
class SourceResolution:
    status: str
    verified_open: bool
    reasons: tuple[str, ...]


def resolve_opportunity_status(
    observations: tuple[SourceObservation, ...],
) -> SourceResolution:
    """Only an issuing-authority observation can establish verified open/closed."""
    authority = [x for x in observations if x.role == "issuing_authority"]
    secondary = [x for x in observations if x.role == "secondary"]

    if not authority:
        if any(x.status == "open" for x in secondary):
            return SourceResolution(
                "unverified", False,
                ("secondary listing reports open; issuing-authority confirmation is absent",),
            )
        return SourceResolution(
            "unknown", False,
            ("no issuing-authority status observation is available",),
        )

    latest = max(authority, key=lambda x: x.observed_on)
    secondary_open = any(x.status == "open" for x in secondary)
    if latest.status == "open":
        return SourceResolution(
            "verified_open", True,
            ("issuing-authority source explicitly reports the solicitation open",),
        )
    if latest.status == "closed":
        return SourceResolution(
            "closed", False,
            ("issuing-authority source explicitly reports the solicitation closed",),
        )
    if latest.status == "not_listed" and secondary_open:
        return SourceResolution(
            "conflicting", False,
            ("secondary listing reports open but issuing-authority page does not list it; verify directly",),
        )
    if latest.status == "not_listed":
        return SourceResolution(
            "not_listed", False,
            ("issuing-authority page does not list the solicitation",),
        )
    return SourceResolution(
        "unknown", False,
        ("issuing-authority status is inconclusive",),
    )
