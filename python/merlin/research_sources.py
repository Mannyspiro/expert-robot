"""Free, cached metadata retrieval for Crossref and arXiv.

The module uses only Python's standard library. Network access is injectable so
research workflows can test parsing, caching, and rate limits without live APIs.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping


class MetadataFetchError(RuntimeError):
    """Raised when a provider response cannot be retrieved or parsed."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True)
class ResearchMetadata:
    source: str
    identifier: str
    title: str
    authors: tuple[str, ...]
    published: str
    abstract: str
    doi: str
    url: str
    raw_sha256: str
    metadata_sha256: str
    retrieved_at: float

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["authors"] = list(self.authors)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ResearchMetadata":
        return cls(
            source=str(value["source"]),
            identifier=str(value["identifier"]),
            title=str(value["title"]),
            authors=tuple(str(x) for x in value["authors"]),  # type: ignore[arg-type]
            published=str(value["published"]),
            abstract=str(value["abstract"]),
            doi=str(value["doi"]),
            url=str(value["url"]),
            raw_sha256=str(value["raw_sha256"]),
            metadata_sha256=str(value["metadata_sha256"]),
            retrieved_at=float(value["retrieved_at"]),
        )


class SQLiteMetadataCache:
    """Persistent TTL cache; expired rows are refreshed, never treated as hits."""

    def __init__(self, path: str | Path, now: Callable[[], float] = time.time):
        self._path = str(path)
        parent = Path(self._path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        self._now = now
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self._path, check_same_thread=False)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS research_metadata_cache (
                cache_key TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                fetched_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        self._db.commit()

    def get(self, cache_key: str) -> ResearchMetadata | None:
        with self._lock:
            row = self._db.execute(
                "SELECT payload_json, expires_at FROM research_metadata_cache WHERE cache_key=?",
                (cache_key,),
            ).fetchone()
            if row is None or float(row[1]) <= self._now():
                return None
            try:
                return ResearchMetadata.from_dict(json.loads(row[0]))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                self._db.execute(
                    "DELETE FROM research_metadata_cache WHERE cache_key=?",
                    (cache_key,),
                )
                self._db.commit()
                return None

    def put(self, cache_key: str, value: ResearchMetadata, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            raise ValueError("cache TTL must be positive")
        payload = json.dumps(value.to_dict(), sort_keys=True, separators=(",", ":"))
        now = self._now()
        with self._lock:
            self._db.execute(
                """
                INSERT INTO research_metadata_cache(cache_key,payload_json,fetched_at,expires_at)
                VALUES(?,?,?,?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    fetched_at=excluded.fetched_at,
                    expires_at=excluded.expires_at
                """,
                (cache_key, payload, now, now + ttl_seconds),
            )
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()


class ProviderRateLimiter:
    """Thread-safe per-provider minimum request interval."""

    def __init__(
        self,
        intervals: Mapping[str, float] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._intervals = dict(intervals or {"crossref": 1.0, "arxiv": 3.0})
        if any(value < 0 for value in self._intervals.values()):
            raise ValueError("provider intervals must be nonnegative")
        self._monotonic = monotonic
        self._sleep = sleep
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, provider: str) -> None:
        with self._lock:
            now = self._monotonic()
            interval = self._intervals.get(provider, 1.0)
            previous = self._last.get(provider)
            if previous is not None:
                delay = interval - (now - previous)
                if delay > 0:
                    self._sleep(delay)
            self._last[provider] = self._monotonic()


class UrllibTransport:
    def __call__(self, url: str, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        request = urllib.request.Request(url, headers=dict(headers))
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return HttpResponse(
                    status=int(response.status),
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except urllib.error.HTTPError as error:
            return HttpResponse(
                status=int(error.code),
                headers=dict(error.headers.items()) if error.headers else {},
                body=error.read(),
            )


def _clean_abstract(value: str) -> str:
    value = re.sub(r"<[^>]*>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _crossref_date(message: Mapping[str, object]) -> str:
    for key in ("published-print", "published-online", "published", "created"):
        part = message.get(key)
        if isinstance(part, dict):
            date_parts = part.get("date-parts")
            if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list):
                return "-".join(f"{int(x):02d}" if i > 0 else str(int(x))
                                for i, x in enumerate(date_parts[0]))
    return ""


def _metadata_digest(fields: Mapping[str, object]) -> str:
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ResearchMetadataClient:
    def __init__(
        self,
        cache_path: str | Path,
        *,
        mailto: str = "",
        user_agent: str = "MerlinResearch/0.1",
        cache_ttl_seconds: float = 7 * 24 * 60 * 60,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
        max_response_bytes: int = 5 * 1024 * 1024,
        transport: Callable[[str, Mapping[str, str], float], HttpResponse] | None = None,
        limiter: ProviderRateLimiter | None = None,
        now: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if (cache_ttl_seconds <= 0 or timeout_seconds <= 0 or
                max_retries < 0 or max_response_bytes <= 0):
            raise ValueError("TTL/timeout/response limit must be positive and retries nonnegative")
        self._now = now
        self._sleep = sleep
        self._ttl = cache_ttl_seconds
        self._timeout = timeout_seconds
        self._retries = max_retries
        self._max_response_bytes = max_response_bytes
        self._transport = transport or UrllibTransport()
        self._limiter = limiter or ProviderRateLimiter()
        self._cache = SQLiteMetadataCache(cache_path, now=now)
        self._headers = {
            "User-Agent": f"{user_agent} (mailto:{mailto})" if mailto else user_agent,
            "Accept": "application/json, application/atom+xml",
        }

    def close(self) -> None:
        self._cache.close()

    def __enter__(self) -> "ResearchMetadataClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def get_by_doi(self, doi: str) -> ResearchMetadata:
        normalized = doi.strip()
        normalized = re.sub(r"^https?://(dx\.)?doi\.org/", "", normalized, flags=re.I)
        normalized = re.sub(r"^doi:\s*", "", normalized, flags=re.I)
        if not re.fullmatch(r"10\.\d{4,9}/[^\s]+", normalized, flags=re.I):
            raise ValueError("invalid DOI")
        normalized = normalized.lower()
        key = f"crossref:doi:{normalized}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        url = "https://api.crossref.org/works/" + urllib.parse.quote(normalized, safe="/")
        response = self._request("crossref", url)
        try:
            payload = json.loads(response.body.decode("utf-8"))
            message = payload["message"]
            title_values = message.get("title") or []
            title = str(title_values[0]) if title_values else ""
            authors = tuple(
                " ".join(part for part in (str(a.get("given", "")).strip(),
                                           str(a.get("family", "")).strip()) if part)
                for a in message.get("author", [])
            )
            doi_value = str(message.get("DOI", normalized)).lower()
            abstract = _clean_abstract(str(message.get("abstract", "")))
            published = _crossref_date(message)
            record_url = str(message.get("URL", url))
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, AttributeError, ValueError) as error:
            raise MetadataFetchError("invalid Crossref response") from error
        return self._store(
            key, "crossref", normalized, title, authors, published,
            abstract, doi_value, record_url, response.body,
        )

    def get_by_arxiv(self, identifier: str) -> ResearchMetadata:
        normalized = identifier.strip()
        normalized = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", normalized, flags=re.I)
        normalized = re.sub(r"^arxiv:\s*", "", normalized, flags=re.I)
        normalized = re.sub(r"\.pdf$", "", normalized, flags=re.I)
        if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?", normalized):
            raise ValueError("invalid arXiv identifier")
        key = f"arxiv:{normalized.lower()}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        url = "https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(normalized, safe="./")
        response = self._request("arxiv", url)
        try:
            root = ET.fromstring(response.body)
            ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
            entry = root.find("atom:entry", ns)
            if entry is None:
                raise MetadataFetchError("arXiv returned no matching entry")
            title = " ".join((entry.findtext("atom:title", default="", namespaces=ns)).split())
            abstract = " ".join((entry.findtext("atom:summary", default="", namespaces=ns)).split())
            authors = tuple(
                " ".join((author.findtext("atom:name", default="", namespaces=ns)).split())
                for author in entry.findall("atom:author", ns)
            )
            published = entry.findtext("atom:published", default="", namespaces=ns)[:10]
            record_url = entry.findtext("atom:id", default=url, namespaces=ns)
            doi = entry.findtext("arxiv:doi", default="", namespaces=ns).lower()
        except ET.ParseError as error:
            raise MetadataFetchError("invalid arXiv Atom response") from error
        return self._store(
            key, "arxiv", normalized, title, authors, published,
            abstract, doi, record_url, response.body,
        )

    def _request(self, provider: str, url: str) -> HttpResponse:
        for attempt in range(self._retries + 1):
            self._limiter.wait(provider)
            try:
                response = self._transport(url, self._headers, self._timeout)
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                if attempt >= self._retries:
                    raise MetadataFetchError(f"{provider} request failed") from error
                self._sleep(min(2 ** attempt, 8))
                continue
            if response.status == 200:
                if len(response.body) > self._max_response_bytes:
                    raise MetadataFetchError(
                        f"{provider} response exceeded the configured size limit"
                    )
                return response
            if response.status in (429, 503) and attempt < self._retries:
                retry_after = next(
                    (v for k, v in response.headers.items() if k.lower() == "retry-after"),
                    "",
                )
                try:
                    delay = max(0.0, min(float(retry_after), 60.0))
                except ValueError:
                    delay = min(2 ** attempt, 8)
                self._sleep(delay)
                continue
            raise MetadataFetchError(f"{provider} returned HTTP {response.status}")
        raise MetadataFetchError(f"{provider} request retries exhausted")

    def _store(
        self, key: str, source: str, identifier: str, title: str,
        authors: tuple[str, ...], published: str, abstract: str,
        doi: str, url: str, raw: bytes,
    ) -> ResearchMetadata:
        if not title.strip():
            raise MetadataFetchError(f"{source} response did not contain a title")
        fields: dict[str, object] = {
            "source": source, "identifier": identifier, "title": title,
            "authors": list(authors), "published": published,
            "abstract": abstract, "doi": doi, "url": url,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        record = ResearchMetadata(
            source=source,
            identifier=identifier,
            title=title,
            authors=authors,
            published=published,
            abstract=abstract,
            doi=doi,
            url=url,
            raw_sha256=str(fields["raw_sha256"]),
            metadata_sha256=_metadata_digest(fields),
            retrieved_at=self._now(),
        )
        self._cache.put(key, record, self._ttl)
        return record
