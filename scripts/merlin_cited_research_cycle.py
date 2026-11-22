#!/usr/bin/env python3
"""Independent exact-byte check and evidence-cited primary-source observation.

The reported answer is deterministic source comparison, NOT AI generation and
NOT a claim of independent scientific truth or automated deployment authority.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable"))
from merlin_studio.public_web import _extract_text
from merlin_public_https_acceptance import SOURCES, TOKENS, MAX_BYTES, EXPECTED_BY_SOURCE


class CitedEvidenceError(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise CitedEvidenceError(reason)


def source_evidence(folder, record, name, url, index):
    require(isinstance(record, dict) and record.get("source_id") == name
            and record.get("requested_url") == url
            and record.get("status") == 200
            and isinstance(record.get("content_type"), str)
            and len(record["content_type"]) < 200
            and isinstance(record.get("final_url"), str)
            and record["final_url"].startswith("https://")
            and re.fullmatch(r"[0-9a-f]{64}", record.get("raw_sha256", "")) is not None,
            "source identity, transport or digest shape differs")
    basename = record.get("body_file")
    require(basename == "source-" + str(index) + ".bin",
            "source locator differs from the predeclared source identity")
    final = urlsplit(record["final_url"])
    expected = urlsplit(url)
    require(final.scheme == "https" and final.hostname == expected.hostname
            and final.port in (None, 443) and final.username is None
            and final.password is None,
            "source URL origin differs from the predeclared primary publisher")
    path = folder / basename
    try:
        info = path.lstat()
    except OSError as exc:
        raise CitedEvidenceError("source receipt byte file unavailable") from exc
    require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= MAX_BYTES,
            "source must be a bounded regular file, not a symlink or device")
    raw = path.read_bytes()
    require(len(raw) == record.get("body_bytes")
            and hashlib.sha256(raw).hexdigest() == record["raw_sha256"],
            "source byte digest or byte count changed")
    text = _extract_text(raw, record["content_type"])
    require(isinstance(text, str), "source decoding failed")
    observed = {token: token in text.lower() for token in TOKENS}
    require(observed == record.get("literal_token_presence"),
            "reported primary-source token presence differs from verified bytes")
    require(all(observed[token] for token in EXPECTED_BY_SOURCE[name]),
            "original primary source did not contain its predeclared reference tokens")
    return {"source_id": name, "source_url": record["final_url"],
            "original_url": url, "body_sha256": record["raw_sha256"],
            "body_bytes": len(raw), "literal_token_presence": observed,
            "content_type": record["content_type"],
            "observational_scope": "exact public source text, not independent factual certification"}


def assess(source_dir):
    folder = Path(source_dir)
    require(folder.is_dir() and not folder.is_symlink(), "source evidence folder missing")
    raw = folder / "report.json"
    require(raw.is_file() and not raw.is_symlink() and raw.stat().st_size <= 131072,
            "bounded source report required")
    try:
        doc = json.loads(raw.read_bytes())
    except (OSError, ValueError) as exc:
        raise CitedEvidenceError("source report is not valid JSON") from exc
    require(isinstance(doc, dict)
            and doc.get("schema") == "merlin-real-public-primary-sources/1"
            and doc.get("status") == "passed"
            and doc.get("source_class") == "live_primary_source_http_bytes"
            and doc.get("model_calls") == 0 and doc.get("browser_render_calls") == 0
            and doc.get("production_qualified") is False
            and doc.get("promotion_authority") is False
            and doc.get("sources_predeclared") == [
                {"id": name, "requested_url": url} for name, url in SOURCES]
            and doc.get("expected_strings") == list(TOKENS)
            and doc.get("expected_by_source") == {
                name: list(tokens) for name, tokens in EXPECTED_BY_SOURCE.items()}
            and doc.get("method_revision") ==
                "post-failure source-specific expectation after 3099787345 reference_disagrees",
            "report is not an accepted, predeclared two-source capture")
    records = doc.get("records")
    require(isinstance(records, list) and len(records) == len(SOURCES),
            "both live primary sources required")
    sources = [source_evidence(folder, record, name, url, index)
               for index, (record, (name, url)) in enumerate(zip(records, SOURCES), 1)]
    require(all(all(entry["literal_token_presence"][token] for token in EXPECTED_BY_SOURCE[entry["source_id"]])
                for entry in sources),
            "independent primary-source text does not contain the source-specific reference tokens")
    require(len({record["body_sha256"] for record in sources}) == 2,
            "independent source files must not reuse identical bytes")
    return {
        "schema": "merlin-research-source-comparison/1",
        "status": "passed",
        "question": "Does IANA name example.com and example.org while RFC2606 lists all three example domains?",
        "answer": ("IANA names example.com and example.org; RFC2606 lists "
                   "example.com, example.net and example.org."),
        "answer_scope": "literal text corroboration only; no model reasoning, website truth or release qualification",
        "sources": sources,
        "predeclared_reference": {
            name: list(tokens) for name, tokens in EXPECTED_BY_SOURCE.items()},
        "method_revision": "explicit revised hypothesis after prior failed live reference",
        "method": "independently rehash raw files, re-extract text, compare exact source token presence",
        "model_calls": 0,
        "browser_render_calls": 0,
        "native_browser_qualified": False,
        "production_qualified": False,
        "promotion_authority": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        data = assess(args.source_dir)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "report.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        summary = data["answer"] + "\n\nSources:\n"
        for record in data["sources"]:
            summary += "- " + record["source_url"] + " (SHA-256 " + record["body_sha256"] + ")\n"
        summary += "\nThis is deterministic source verification, not an AI-generated response.\n"
        (args.output / "source-observation.md").write_text(summary)
        print(json.dumps({"status": "passed", "source_count": len(data["sources"]),
                          "model_calls": 0, "browser_render_calls": 0,
                          "production_qualified": False}))
        return 0
    except (CitedEvidenceError, OSError, ValueError) as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "blocked.json").write_text(json.dumps(
            {"status": "blocked", "error_type": type(exc).__name__,
             "error": str(exc)[:250], "production_qualified": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
