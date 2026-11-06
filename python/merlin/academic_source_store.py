"""Merlin AcademicSpider v0.2: provenance-backed public URL intake.

No network fetching occurs here. URLs are submitted after human review of public
search results. The official discovery page is retained as provenance; linked
professor homepages may live on another public domain.
"""
from __future__ import annotations

from contextlib import closing

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
TRACKING_PREFIXES = ("utm_",)


@dataclass(frozen=True)
class AcademicSource:
    source_url: str
    canonical_url: str
    institution: str
    institution_domain: str
    source_type: str
    discovered_from: str
    title: str = ""
    researcher_name: str = ""
    topics: tuple[str, ...] = ()
    evidence_status: str = "discovered"
    captured_at: str = ""


def _host(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("only public HTTP(S) URLs are accepted")
    if not parts.hostname or parts.username or parts.password:
        raise ValueError("URL must have a hostname and no embedded credentials")
    return parts.hostname.lower().rstrip(".")


def _valid_domain(domain: str) -> str:
    value = domain.strip().lower().rstrip(".")
    if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", value):
        raise ValueError(f"invalid institution domain: {domain!r}")
    return value


def _within_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def canonicalize_url(url: str) -> str:
    """Normalize a public URL while preserving meaningful path/query semantics."""
    value = url.strip()
    parts = urlsplit(value)
    host = _host(value)
    scheme = parts.scheme.lower()
    port = parts.port
    netloc = host
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = [
        (key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_KEYS
        and not any(key.lower().startswith(prefix) for prefix in TRACKING_PREFIXES)
    ]
    query.sort()
    return urlunsplit((scheme, netloc, path, urlencode(query, doseq=True), ""))


def _clean_text(value: str, field: str, limit: int = 500) -> str:
    result = " ".join((value or "").split()).strip()
    if len(result) > limit:
        raise ValueError(f"{field} must be at most {limit} characters")
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AcademicSourceStore:
    """Small SQLite provenance store; repeated canonical URLs update one record."""

    def __init__(self, database: str | Path):
        self.database = str(database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS academic_sources (
                    canonical_url TEXT PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    institution TEXT NOT NULL,
                    institution_domain TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    discovered_from TEXT NOT NULL,
                    title TEXT NOT NULL,
                    researcher_name TEXT NOT NULL,
                    topics_json TEXT NOT NULL,
                    evidence_status TEXT NOT NULL,
                    captured_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_academic_sources_institution
                ON academic_sources(institution_domain)
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        return db

    def add(
        self,
        *,
        source_url: str,
        institution: str,
        institution_domain: str,
        source_type: str,
        discovered_from: str,
        title: str = "",
        researcher_name: str = "",
        topics: Iterable[str] = (),
        evidence_status: str = "discovered",
    ) -> AcademicSource:
        domain = _valid_domain(institution_domain)
        canonical = canonicalize_url(source_url)
        provenance = canonicalize_url(discovered_from)
        if not _within_domain(_host(provenance), domain):
            raise ValueError("discovered_from must be on the registered institution domain")
        kind = _clean_text(source_type, "source_type", 60).lower()
        if kind not in {"faculty_profile", "personal_homepage", "research_group",
                        "publication", "preprint", "lecture_notes", "project"}:
            raise ValueError("unsupported source_type")
        status = _clean_text(evidence_status, "evidence_status", 40).lower()
        if status not in {"discovered", "reviewed", "verified_official", "rejected"}:
            raise ValueError("unsupported evidence_status")
        clean_topics = tuple(dict.fromkeys(
            _clean_text(topic, "topic", 100) for topic in topics if _clean_text(topic, "topic", 100)
        ))
        record = AcademicSource(
            source_url=source_url.strip(),
            canonical_url=canonical,
            institution=_clean_text(institution, "institution", 160),
            institution_domain=domain,
            source_type=kind,
            discovered_from=provenance,
            title=_clean_text(title, "title"),
            researcher_name=_clean_text(researcher_name, "researcher_name", 160),
            topics=clean_topics,
            evidence_status=status,
            captured_at=_utc_now(),
        )
        with closing(self._connect()) as db, db:
            db.execute("""
                INSERT INTO academic_sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_url) DO UPDATE SET
                    source_url=excluded.source_url,
                    institution=excluded.institution,
                    institution_domain=excluded.institution_domain,
                    source_type=excluded.source_type,
                    discovered_from=excluded.discovered_from,
                    title=CASE WHEN excluded.title='' THEN academic_sources.title ELSE excluded.title END,
                    researcher_name=CASE WHEN excluded.researcher_name='' THEN academic_sources.researcher_name ELSE excluded.researcher_name END,
                    topics_json=excluded.topics_json,
                    evidence_status=excluded.evidence_status,
                    captured_at=excluded.captured_at
            """, (
                record.canonical_url, record.source_url, record.institution,
                record.institution_domain, record.source_type, record.discovered_from,
                record.title, record.researcher_name, json.dumps(record.topics),
                record.evidence_status, record.captured_at,
            ))
        return record

    def list(self, institution_domain: str | None = None) -> list[AcademicSource]:
        sql = "SELECT * FROM academic_sources"
        args: tuple[str, ...] = ()
        if institution_domain:
            sql += " WHERE institution_domain = ?"
            args = (_valid_domain(institution_domain),)
        sql += " ORDER BY institution_domain, researcher_name, canonical_url"
        with closing(self._connect()) as db, db:
            rows = db.execute(sql, args).fetchall()
        return [
            AcademicSource(
                source_url=row["source_url"], canonical_url=row["canonical_url"],
                institution=row["institution"], institution_domain=row["institution_domain"],
                source_type=row["source_type"], discovered_from=row["discovered_from"],
                title=row["title"], researcher_name=row["researcher_name"],
                topics=tuple(json.loads(row["topics_json"])),
                evidence_status=row["evidence_status"], captured_at=row["captured_at"],
            )
            for row in rows
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Merlin's public academic URL intake.")
    parser.add_argument("--db", default="data/merlin_academic_sources.sqlite3")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("--url", required=True)
    add.add_argument("--institution", required=True)
    add.add_argument("--domain", required=True)
    add.add_argument("--type", required=True, dest="source_type")
    add.add_argument("--discovered-from", required=True)
    add.add_argument("--title", default="")
    add.add_argument("--researcher", default="")
    add.add_argument("--topic", action="append", default=[])
    add.add_argument("--status", default="discovered")
    listing = sub.add_parser("list")
    listing.add_argument("--domain")
    args = parser.parse_args()
    store = AcademicSourceStore(args.db)
    if args.command == "add":
        result = store.add(
            source_url=args.url, institution=args.institution,
            institution_domain=args.domain, source_type=args.source_type,
            discovered_from=args.discovered_from, title=args.title,
            researcher_name=args.researcher, topics=args.topic,
            evidence_status=args.status,
        )
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print(json.dumps([asdict(item) for item in store.list(args.domain)],
                         ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
