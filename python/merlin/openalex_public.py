"""Public OpenAlex enrichment for Merlin.

Only calls the documented public OpenAlex API over HTTPS. No institutional
login, paywall bypass, private endpoint, bulk dump, or full-text harvesting.
A small page size and sequential requests keep the default workflow conservative.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.openalex.org"
DEFAULT_FIELDS = (
    "id", "doi", "title", "publication_year", "type", "authorships",
    "primary_location", "open_access", "cited_by_count",
)


@dataclass(frozen=True)
class OpenAlexAuthor:
    openalex_id: str
    display_name: str
    orcid: str
    institutions: tuple[str, ...]


@dataclass(frozen=True)
class OpenAlexWork:
    openalex_id: str
    doi: str
    title: str
    publication_year: int | None
    work_type: str
    landing_page_url: str
    is_oa: bool | None
    cited_by_count: int
    authors: tuple[OpenAlexAuthor, ...]
    source: str = "OpenAlex public API"
    evidence_status: str = "metadata_discovered"


def _abstract_free_record(raw: dict[str, Any]) -> OpenAlexWork:
    authors: list[OpenAlexAuthor] = []
    for authorship in raw.get("authorships") or []:
        author = authorship.get("author") or {}
        institutions = tuple(
            item.get("display_name", "")
            for item in (authorship.get("institutions") or [])
            if item.get("display_name")
        )
        authors.append(OpenAlexAuthor(
            openalex_id=author.get("id", ""),
            display_name=author.get("display_name", ""),
            orcid=author.get("orcid") or "",
            institutions=institutions,
        ))
    location = raw.get("primary_location") or {}
    landing = location.get("landing_page_url") or ""
    oa = raw.get("open_access") or {}
    return OpenAlexWork(
        openalex_id=raw.get("id", ""),
        doi=raw.get("doi") or "",
        title=raw.get("title") or "",
        publication_year=raw.get("publication_year"),
        work_type=raw.get("type") or "",
        landing_page_url=landing,
        is_oa=oa.get("is_oa"),
        cited_by_count=int(raw.get("cited_by_count") or 0),
        authors=tuple(authors),
    )


class OpenAlexClient:
    """Small public API client; caller controls whether a search is initiated."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        mailto: str | None = None,
        timeout: float = 15.0,
        min_interval_seconds: float = 1.0,
        opener: Callable[..., Any] | None = None,
    ):
        if timeout <= 0 or min_interval_seconds < 0:
            raise ValueError("timeout must be positive and interval non-negative")
        self.api_key = api_key or os.getenv("OPENALEX_API_KEY")
        self.mailto = mailto or os.getenv("OPENALEX_MAILTO")
        self.timeout = timeout
        self.min_interval_seconds = min_interval_seconds
        self._opener = opener or urlopen
        self._last_request = 0.0

    def _get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        query = dict(params)
        if self.api_key:
            query["api_key"] = self.api_key
        if self.mailto:
            query["mailto"] = self.mailto
        url = API_ROOT + path + "?" + urlencode(query)
        elapsed = time.monotonic() - self._last_request
        if self._last_request and elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        request = Request(url, headers={"Accept": "application/json",
                                        "User-Agent": "MerlinAcademicResearch/0.3"})
        try:
            with self._opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429:
                raise RuntimeError("OpenAlex rate limit reached; pause and retry later") from exc
            raise RuntimeError(f"OpenAlex returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("OpenAlex request failed; check connectivity and retry later") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("OpenAlex returned an invalid JSON response") from exc
        self._last_request = time.monotonic()
        if not isinstance(payload, dict):
            raise RuntimeError("OpenAlex response was not a JSON object")
        return payload

    def search_works(self, query: str, *, per_page: int = 10) -> list[OpenAlexWork]:
        text = " ".join(query.split()).strip()
        if not text or len(text) > 300:
            raise ValueError("query must be a non-empty string of at most 300 characters")
        if not 1 <= per_page <= 25:
            raise ValueError("per_page must be between 1 and 25 for conservative discovery")
        payload = self._get_json("/works", {
            "search": text,
            "per_page": str(per_page),
            "select": ",".join(DEFAULT_FIELDS),
        })
        results = payload.get("results")
        if not isinstance(results, list):
            raise RuntimeError("OpenAlex response did not contain a results list")
        return [_abstract_free_record(item) for item in results if isinstance(item, dict)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Search public OpenAlex scholarly metadata.")
    parser.add_argument("--query", required=True, help="research topic or phrase")
    parser.add_argument("--per-page", type=int, default=10)
    parser.add_argument("--mailto", help="optional contact email for OpenAlex polite pool")
    args = parser.parse_args()
    client = OpenAlexClient(mailto=args.mailto)
    works = client.search_works(args.query, per_page=args.per_page)
    print(json.dumps([asdict(work) for work in works], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
