"""Merlin AcademicSpider: focused Google-dork planning for public academic research."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
from typing import Iterable
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Institution:
    name: str
    domain: str
    kind: str = "university"


@dataclass(frozen=True)
class DiscoveryQuery:
    institution: str
    domain: str
    category: str
    query: str
    search_url: str


# Curated for overlap with Merlin's math, geometry, combinatorics, and formal-proof work.
DEFAULT_INSTITUTIONS = (
    Institution("Stanford University", "stanford.edu"),
    Institution("Massachusetts Institute of Technology", "mit.edu"),
    Institution("Princeton University", "princeton.edu"),
    Institution("Harvard University", "harvard.edu"),
    Institution("ETH Zurich", "ethz.ch"),
    Institution("Zuse Institute Berlin", "zib.de", "research_institute"),
)

DEFAULT_TOPICS = (
    "combinatorics",
    "graph theory",
    "geometric combinatorics",
    "differential geometry",
    "algebraic geometry",
    "topology",
    "category theory",
    "mathematical physics",
    "information theory",
    "formal verification",
    "Lean theorem proving",
    "computational mathematics",
)


def _valid_domain(domain: str) -> str:
    value = domain.strip().lower().rstrip(".")
    if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", value):
        raise ValueError(f"invalid institution domain: {domain!r}")
    return value


def _clean_topic(topic: str) -> str:
    value = " ".join(topic.split()).strip()
    if not value or len(value) > 100 or "\n" in topic or "\r" in topic:
        raise ValueError("topics must be non-empty single-line strings of at most 100 characters")
    return value


def build_queries(
    institution: Institution,
    topics: Iterable[str] = DEFAULT_TOPICS,
) -> list[DiscoveryQuery]:
    """Build a compact, repeatable set of Google queries for public academic pages."""
    domain = _valid_domain(institution.domain)
    cleaned = tuple(dict.fromkeys(_clean_topic(topic) for topic in topics))
    if not cleaned:
        raise ValueError("at least one topic is required")

    specs = [
        ("faculty_profiles", f'site:{domain} "research interests" professor mathematics'),
        ("faculty_directories", f'site:{domain} faculty mathematics professor'),
        ("personal_homepages", f'site:{domain}/~ professor mathematics research'),
        ("publications", f'site:{domain} publications mathematics researcher'),
        ("preprints", f'site:{domain} filetype:pdf preprint mathematics'),
        ("research_groups", f'site:{domain} mathematics research group'),
    ]
    for topic in cleaned:
        specs.append((f"topic:{topic}", f'site:{domain} "{topic}" professor research'))
    return [
        DiscoveryQuery(
            institution.name,
            domain,
            category,
            query,
            "https://www.google.com/search?q=" + quote_plus(query),
        )
        for category, query in specs
    ]


def build_registry_queries(
    institutions: Iterable[Institution] = DEFAULT_INSTITUTIONS,
    topics: Iterable[str] = DEFAULT_TOPICS,
) -> list[DiscoveryQuery]:
    topic_list = tuple(topics)
    results: list[DiscoveryQuery] = []
    seen: set[str] = set()
    for institution in institutions:
        domain = _valid_domain(institution.domain)
        if domain not in seen:
            seen.add(domain)
            results.extend(build_queries(institution, topic_list))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate focused Google dorks for public university research pages."
    )
    parser.add_argument("--domain", help="one university/research institute domain")
    parser.add_argument("--name", default="Custom institution")
    parser.add_argument("--topic", action="append", dest="topics")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    topics = tuple(args.topics) if args.topics else DEFAULT_TOPICS
    rows = (
        build_queries(Institution(args.name, args.domain), topics)
        if args.domain
        else build_registry_queries(DEFAULT_INSTITUTIONS, topics)
    )
    print(json.dumps(
        [asdict(row) for row in rows],
        ensure_ascii=False,
        indent=2 if args.pretty else None,
    ))


if __name__ == "__main__":
    main()
