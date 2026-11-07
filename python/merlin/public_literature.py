"""No-credential public literature search for Merlin.

Uses only fixed public Crossref and arXiv endpoints. No account, API key,
project token, environment variable, or user-side service configuration is
required. Search results are untrusted observations, never verified claims.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from threading import Lock
from time import monotonic, sleep
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import re
import xml.etree.ElementTree as ET
from html import unescape


_ENDPOINTS = {
    "crossref": ("https://api.crossref.org/works", "api.crossref.org"),
    "arxiv": ("https://export.arxiv.org/api/query", "export.arxiv.org"),
}
_NS = {"atom": "http://www.w3.org/2005/Atom"}
_RATE_LOCK = Lock()
_NEXT_ALLOWED: dict[str, float] = {}
_CACHE_LOCK = Lock()
_CACHE: dict[tuple[str, str, int], tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 300
_MAX_RESPONSE_BYTES = 2_000_000


def _bounded_query(query: str) -> str:
    if not isinstance(query, str):
        raise ValueError("query must be text")
    query = " ".join(query.split())
    if not 2 <= len(query) <= 240:
        raise ValueError("query must contain 2 to 240 characters")
    if any(ord(ch) < 32 for ch in query):
        raise ValueError("query contains control characters")
    return query


def _request_json(
    url: str, host: str, opener: Callable[..., Any], timeout: float
) -> tuple[bytes, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "MerlinResearch/1.0 (public literature metadata client)",
        },
    )
    with opener(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise RuntimeError(f"{host} returned HTTP {status}")
        payload = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(payload) > _MAX_RESPONSE_BYTES:
        raise ValueError(f"{host} response exceeded size limit")
    return payload, json.loads(payload.decode("utf-8"))


def _request_xml(
    url: str, host: str, opener: Callable[..., Any], timeout: float
) -> tuple[bytes, ET.Element]:
    request = Request(
        url,
        headers={
            "Accept": "application/atom+xml, application/xml",
            "User-Agent": "MerlinResearch/1.0 (public literature metadata client)",
        },
    )
    with opener(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise RuntimeError(f"{host} returned HTTP {status}")
        payload = response.read(_MAX_RESPONSE_BYTES + 1)
    if len(payload) > _MAX_RESPONSE_BYTES:
        raise ValueError(f"{host} response exceeded size limit")
    root = ET.fromstring(payload)
    return payload, root


def _record(
    *, source: str, source_id: str, title: str, authors: list[str],
    published: str | None, abstract: str | None, url: str,
) -> dict[str, Any]:
    clean_abstract = re.sub(r"<[^>]*>", " ", abstract or "")
    clean_abstract = unescape(clean_abstract)
    return {
        "source": source,
        "source_id": source_id,
        "title": " ".join(title.split())[:1000],
        "authors": authors[:20],
        "published": published,
        "abstract": " ".join(clean_abstract.split())[:4000] or None,
        "url": url,
        "evidence_class": "OBSERVED_DOCUMENT",
        "claim_verification": "NOT_VERIFIED",
    }


def _crossref(query: str, limit: int, opener: Callable[..., Any], timeout: float):
    base, host = _ENDPOINTS["crossref"]
    url = base + "?" + urlencode({"query.bibliographic": query, "rows": limit})
    raw, data = _request_json(url, host, opener, timeout)
    message = data.get("message", {})
    items = message.get("items", []) if isinstance(message, dict) else []
    records = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or []
        doi = item.get("DOI")
        if not title or not isinstance(doi, str):
            continue
        doi = doi.strip()
        if not re.fullmatch(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", doi, re.IGNORECASE):
            continue
        authors = []
        for author in item.get("author", [])[:20]:
            if isinstance(author, dict):
                name = " ".join(str(author.get(k, "")) for k in ("given", "family")).strip()
                if name:
                    authors.append(name)
        date_parts = (
            item.get("published", {}).get("date-parts")
            or item.get("created", {}).get("date-parts")
            or []
        )
        published = "-".join(str(x) for x in date_parts[0]) if date_parts else None
        records.append(_record(
            source="crossref", source_id="doi:" + doi, title=str(title[0]),
            authors=authors, published=published, abstract=item.get("abstract"),
            url="https://doi.org/" + doi,
        ))
    return records, sha256(raw).hexdigest()


def _arxiv(query: str, limit: int, opener: Callable[..., Any], timeout: float):
    base, host = _ENDPOINTS["arxiv"]
    search = "all:" + query
    url = base + "?" + urlencode({
        "search_query": search, "start": 0, "max_results": limit,
        "sortBy": "relevance", "sortOrder": "descending",
    })
    raw, root = _request_xml(url, host, opener, timeout)
    records = []
    for entry in root.findall("atom:entry", _NS)[:limit]:
        ident = (entry.findtext("atom:id", default="", namespaces=_NS) or "").strip()
        title = entry.findtext("atom:title", default="", namespaces=_NS)
        if not ident or not title:
            continue
        parsed_id = urlsplit(ident)
        if parsed_id.scheme != "https" or parsed_id.hostname != "arxiv.org":
            continue
        source_id = ident.rstrip("/").split("/")[-1]
        if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z.-]+/\d{7})(?:v\d+)?", source_id, re.IGNORECASE):
            continue
        authors = [
            (node.findtext("atom:name", default="", namespaces=_NS) or "").strip()
            for node in entry.findall("atom:author", _NS)
        ]
        published = entry.findtext("atom:published", default=None, namespaces=_NS)
        records.append(_record(
            source="arxiv", source_id="arxiv:" + source_id, title=title,
            authors=[name for name in authors if name], published=published,
            abstract=entry.findtext("atom:summary", default=None, namespaces=_NS),
            url=ident,
        ))
    return records, sha256(raw).hexdigest()


class PublicLiteratureSearch:
    """Bounded, cached search against public APIs that need no credentials."""

    def __init__(
        self,
        *,
        opener: Callable[..., Any] = urlopen,
        timeout_seconds: float = 8.0,
        cache_ttl_seconds: int = _CACHE_TTL_SECONDS,
        clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
    ):
        if not 1 <= timeout_seconds <= 20:
            raise ValueError("timeout must be between 1 and 20 seconds")
        if not 0 <= cache_ttl_seconds <= 3600:
            raise ValueError("cache TTL must be between 0 and 3600 seconds")
        self.opener = opener
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self.clock = clock
        self.sleeper = sleeper

    def _rate_limit(self, source: str) -> None:
        interval = 1.0 if source == "crossref" else 3.0
        with _RATE_LOCK:
            now = self.clock()
            wait = max(0.0, _NEXT_ALLOWED.get(source, 0.0) - now)
            _NEXT_ALLOWED[source] = now + wait + interval
        if wait:
            self.sleeper(wait)

    def search(self, query: str, *, source: str = "all", limit: int = 10) -> dict[str, Any]:
        query = _bounded_query(query)
        if source not in {"all", "crossref", "arxiv"}:
            raise ValueError("source must be all, crossref, or arxiv")
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("limit must be an integer from 1 to 20")
        cache_key = (source, query.casefold(), limit)
        with _CACHE_LOCK:
            cached = _CACHE.get(cache_key)
            if cached and self.clock() - cached[0] <= self.cache_ttl_seconds:
                return {**cached[1], "cache": "HIT"}
        selected = ["crossref", "arxiv"] if source == "all" else [source]
        results, errors, hashes = [], [], {}
        for item in selected:
            try:
                self._rate_limit(item)
                fetch = _crossref if item == "crossref" else _arxiv
                rows, digest = fetch(query, limit, self.opener, self.timeout_seconds)
                results.extend(rows)
                hashes[item] = digest
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, RuntimeError, ET.ParseError) as exc:
                errors.append({"source": item, "error_class": type(exc).__name__})
        # De-duplicate by persistent DOI/arXiv identifier; preserve source provenance.
        seen: set[str] = set()
        unique = []
        for row in results:
            if row["source_id"] not in seen:
                seen.add(row["source_id"])
                unique.append(row)
        response = {
            "schema": "merlin-public-literature-search/1",
            "query": query,
            "sources_requested": selected,
            "results": unique[: limit * len(selected)],
            "source_response_sha256": hashes,
            "errors": errors,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "cache": "MISS",
            "credentials_required": False,
            "claim_verification": "NOT_VERIFIED",
        }
        with _CACHE_LOCK:
            _CACHE[cache_key] = (self.clock(), response)
        return response


__all__ = ["PublicLiteratureSearch"]
