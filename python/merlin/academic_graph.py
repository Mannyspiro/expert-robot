"""Normalized scholarly graph store for public OpenAlex metadata.

OpenAlex IDs define identity. Topic assignments are discovery classifications,
not verified claims. This module performs no network access.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from merlin.openalex_public import OpenAlexWork


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: str, field: str, limit: int = 1000) -> str:
    result = " ".join((value or "").split()).strip()
    if len(result) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    return result


@dataclass(frozen=True)
class GraphStats:
    works: int
    researchers: int
    institutions: int
    authorship_edges: int
    topics: int
    work_topic_edges: int


class AcademicGraphStore:
    """SQLite scholarly graph with idempotent upserts and provenance."""

    def __init__(self, database: str | Path):
        self.database = str(database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS researchers (
                    openalex_id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
                    orcid TEXT NOT NULL DEFAULT '', source TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS institutions (
                    display_name TEXT PRIMARY KEY, source TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS works (
                    openalex_id TEXT PRIMARY KEY, doi TEXT UNIQUE,
                    title TEXT NOT NULL, publication_year INTEGER,
                    work_type TEXT NOT NULL, landing_page_url TEXT NOT NULL,
                    is_oa INTEGER, cited_by_count INTEGER NOT NULL,
                    source TEXT NOT NULL, evidence_status TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS authorship_edges (
                    work_id TEXT NOT NULL REFERENCES works(openalex_id) ON DELETE CASCADE,
                    researcher_id TEXT NOT NULL REFERENCES researchers(openalex_id) ON DELETE CASCADE,
                    author_position TEXT NOT NULL,
                    PRIMARY KEY (work_id, researcher_id)
                );
                CREATE TABLE IF NOT EXISTS researcher_institutions (
                    researcher_id TEXT NOT NULL REFERENCES researchers(openalex_id) ON DELETE CASCADE,
                    institution_name TEXT NOT NULL REFERENCES institutions(display_name) ON DELETE CASCADE,
                    PRIMARY KEY (researcher_id, institution_name)
                );
                CREATE TABLE IF NOT EXISTS topics (
                    openalex_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    classification_kind TEXT NOT NULL DEFAULT 'OpenAlex assigned topic',
                    retrieved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS work_topics (
                    work_id TEXT NOT NULL REFERENCES works(openalex_id) ON DELETE CASCADE,
                    topic_id TEXT NOT NULL REFERENCES topics(openalex_id) ON DELETE CASCADE,
                    score REAL,
                    PRIMARY KEY (work_id, topic_id),
                    CHECK (score IS NULL OR (score >= 0 AND score <= 1))
                );
                CREATE INDEX IF NOT EXISTS idx_works_doi ON works(doi);
                CREATE INDEX IF NOT EXISTS idx_researchers_orcid ON researchers(orcid);
                CREATE INDEX IF NOT EXISTS idx_authorship_researcher ON authorship_edges(researcher_id);
                CREATE INDEX IF NOT EXISTS idx_work_topics_topic ON work_topics(topic_id);
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def ingest(self, work: OpenAlexWork) -> None:
        work_id = _text(work.openalex_id, "OpenAlex work ID", 200)
        if not work_id.startswith("https://openalex.org/W"):
            raise ValueError("work must have a canonical OpenAlex W identifier")
        doi = _text(work.doi, "DOI", 300) or None
        if doi and not doi.startswith("https://doi.org/"):
            raise ValueError("DOI must be a normalized https://doi.org/ URL")
        if work.publication_year is not None and not 1400 <= int(work.publication_year) <= 2200:
            raise ValueError("publication year is outside accepted range")
        if int(work.cited_by_count) < 0:
            raise ValueError("cited_by_count cannot be negative")
        title = _text(work.title, "title")
        if not title:
            raise ValueError("work title is required")
        timestamp = _now()
        source = _text(work.source, "source", 100)
        with self._connect() as db:
            try:
                db.execute("""
                    INSERT INTO works VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(openalex_id) DO UPDATE SET
                        doi=excluded.doi, title=excluded.title,
                        publication_year=excluded.publication_year,
                        work_type=excluded.work_type,
                        landing_page_url=excluded.landing_page_url,
                        is_oa=excluded.is_oa, cited_by_count=excluded.cited_by_count,
                        source=excluded.source, evidence_status=excluded.evidence_status,
                        retrieved_at=excluded.retrieved_at
                """, (work_id, doi, title, work.publication_year,
                      _text(work.work_type, "work_type", 100),
                      _text(work.landing_page_url, "landing_page_url", 2000),
                      None if work.is_oa is None else int(bool(work.is_oa)),
                      int(work.cited_by_count), source, "metadata_discovered", timestamp))
            except sqlite3.IntegrityError as exc:
                raise ValueError("DOI is already attached to a different OpenAlex work ID") from exc

            db.execute("DELETE FROM authorship_edges WHERE work_id = ?", (work_id,))
            for author in work.authors:
                author_id = _text(author.openalex_id, "OpenAlex author ID", 200)
                if not author_id.startswith("https://openalex.org/A"):
                    continue
                name = _text(author.display_name, "author display name", 300)
                if not name:
                    continue
                orcid = _text(author.orcid, "ORCID", 200)
                db.execute("""
                    INSERT INTO researchers VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(openalex_id) DO UPDATE SET
                        display_name=excluded.display_name,
                        orcid=CASE WHEN excluded.orcid='' THEN researchers.orcid ELSE excluded.orcid END,
                        source=excluded.source, retrieved_at=excluded.retrieved_at
                """, (author_id, name, orcid, source, timestamp))
                db.execute("INSERT INTO authorship_edges VALUES (?, ?, ?)",
                           (work_id, author_id, "unspecified"))
                for institution_name in dict.fromkeys(
                    _text(item, "institution name", 300)
                    for item in author.institutions if _text(item, "institution name", 300)
                ):
                    db.execute("""
                        INSERT INTO institutions VALUES (?, ?, ?)
                        ON CONFLICT(display_name) DO UPDATE SET
                            source=excluded.source, retrieved_at=excluded.retrieved_at
                    """, (institution_name, source, timestamp))
                    db.execute("INSERT OR IGNORE INTO researcher_institutions VALUES (?, ?)",
                               (author_id, institution_name))

            # Rebuild only this work's topic edges so stale classifications disappear.
            db.execute("DELETE FROM work_topics WHERE work_id = ?", (work_id,))
            for topic in work.topics:
                topic_id = _text(topic.openalex_id, "OpenAlex topic ID", 200)
                if not topic_id.startswith("https://openalex.org/T"):
                    continue
                label = _text(topic.display_name, "topic display name", 300)
                if not label:
                    continue
                score = topic.score
                if score is not None and not 0.0 <= float(score) <= 1.0:
                    raise ValueError("OpenAlex topic score must be between 0 and 1")
                db.execute("""
                    INSERT INTO topics VALUES (?, ?, ?, 'OpenAlex assigned topic', ?)
                    ON CONFLICT(openalex_id) DO UPDATE SET
                        display_name=excluded.display_name, source=excluded.source,
                        retrieved_at=excluded.retrieved_at
                """, (topic_id, label, source, timestamp))
                db.execute("INSERT INTO work_topics VALUES (?, ?, ?)",
                           (work_id, topic_id, score))

    def stats(self) -> GraphStats:
        tables = ("works", "researchers", "institutions", "authorship_edges",
                  "topics", "work_topics")
        with self._connect() as db:
            counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for table in tables}
        return GraphStats(
            works=counts["works"],
            researchers=counts["researchers"],
            institutions=counts["institutions"],
            authorship_edges=counts["authorship_edges"],
            topics=counts["topics"],
            work_topic_edges=counts["work_topics"],
        )

    def researcher_works(self, openalex_author_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("""
                SELECT w.openalex_id, w.doi, w.title, w.publication_year,
                       w.landing_page_url, w.cited_by_count, e.author_position
                FROM authorship_edges e JOIN works w ON w.openalex_id=e.work_id
                WHERE e.researcher_id=?
                ORDER BY w.publication_year DESC, w.title
            """, (openalex_author_id,)).fetchall()
        return [dict(row) for row in rows]

    def topic_works(self, openalex_topic_id: str) -> list[dict[str, Any]]:
        """Return works assigned to a topic; score is classification metadata."""
        with self._connect() as db:
            rows = db.execute("""
                SELECT w.openalex_id, w.title, w.publication_year,
                       w.landing_page_url, wt.score, t.display_name AS topic
                FROM work_topics wt
                JOIN works w ON w.openalex_id=wt.work_id
                JOIN topics t ON t.openalex_id=wt.topic_id
                WHERE wt.topic_id=?
                ORDER BY wt.score DESC, w.publication_year DESC, w.title
            """, (openalex_topic_id,)).fetchall()
        return [dict(row) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Merlin's local scholarly graph.")
    parser.add_argument("--db", default="data/merlin_academic_sources.sqlite3")
    args = parser.parse_args()
    print(json.dumps(asdict(AcademicGraphStore(args.db).stats()), indent=2))


if __name__ == "__main__":
    main()
