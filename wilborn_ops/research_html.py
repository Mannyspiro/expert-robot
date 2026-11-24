"""Offline HTML-to-text extraction for approved public research evidence.

This parser never fetches URLs, executes scripts or interprets page text as
instructions. Source authenticity is not established by a URL alone.
"""
from dataclasses import dataclass
from html.parser import HTMLParser
from .research_ingest import Evidence, ingest_public_text, MAX_BYTES

MAX_TEXT_CHARS = 100_000
IGNORED = frozenset({"script", "style", "noscript", "template", "svg"})

class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored = []
        self.total = 0

    def handle_starttag(self, tag, attrs):
        if tag in IGNORED:
            self.ignored.append(tag)
        if tag in ("p", "div", "li", "h1", "h2", "h3", "tr", "br"):
            self._append(" ")

    def handle_endtag(self, tag):
        if tag in IGNORED and self.ignored and self.ignored[-1] == tag:
            self.ignored.pop()
        if tag in ("p", "div", "li", "h1", "h2", "h3", "tr"):
            self._append(" ")

    def handle_data(self, data):
        if not self.ignored:
            self._append(data)

    def _append(self, value):
        self.total += len(value)
        if self.total > MAX_TEXT_CHARS:
            raise ValueError("extracted text limit exceeded")
        self.parts.append(value)

@dataclass(frozen=True)
class ExtractedPage:
    source_sha256: str
    url: str
    text: str
    data_class: str = "public_research"
    verification: str = "unverified_source_content"
    untrusted_instructions: bool = True

def extract_html(evidence):
    if not isinstance(evidence, Evidence) or evidence.data_class != "public_research":
        raise PermissionError("public research evidence required")
    if evidence.bytes > MAX_BYTES:
        raise ValueError("document exceeds limit")
    parser = _TextParser()
    parser.feed(evidence.text)
    parser.close()
    cleaned = " ".join(" ".join(parser.parts).split())
    if not cleaned:
        raise ValueError("no extractable public text")
    return ExtractedPage(evidence.sha256, evidence.url, cleaned)

def ingest_html(url, raw_html):
    return extract_html(ingest_public_text(url, raw_html))
