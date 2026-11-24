#!/usr/bin/env python3
"""Discover public-domain full-view books via the public Google Books API.

This tool retrieves bibliographic metadata only. It does not scrape previews or
download book content. Public-domain/full-view flags are recorded as Google's
catalog claims and must be cross-checked against the source edition and local law.
"""
from __future__ import annotations
import argparse, json, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone

API="https://www.googleapis.com/books/v1/volumes"
def discover(query: str, max_results: int=10) -> dict:
    params=urllib.parse.urlencode({"q":query,"maxResults":max(1,min(max_results,40)),"printType":"books"})
    req=urllib.request.Request(API+"?"+params,headers={"User-Agent":"MerlinResearchAtlas/0.1 (public catalog discovery)"})
    payload=None
    last_error=None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=20) as response:
                payload=json.load(response)
            break
        except urllib.error.HTTPError as exc:
            last_error={"http_status":exc.code,"reason":str(exc.reason)}
            if exc.code not in (429,500,502,503,504):
                break
            time.sleep(min(2 ** attempt, 4))
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error={"network_error":str(exc)}
            time.sleep(min(2 ** attempt, 4))
    if payload is None:
        return {
            "schema_version":1,
            "source":"Google Books API",
            "query":query,
            "retrieved_at":datetime.now(timezone.utc).isoformat(),
            "discovery_status":"temporarily_unavailable",
            "error":last_error,
            "total_items":0,
            "items":[],
            "limitations":["The public API request did not return data during this run. Retry later; no book text was fetched or inferred."]
        }
    items=[]
    for item in payload.get("items",[]):
        info=item.get("volumeInfo",{})
        access=item.get("accessInfo",{})
        items.append({
            "google_volume_id":item.get("id"),
            "title":info.get("title"),
            "subtitle":info.get("subtitle"),
            "authors":info.get("authors",[]),
            "published_date":info.get("publishedDate"),
            "language":info.get("language"),
            "publisher":info.get("publisher"),
            "description":info.get("description"),
            "categories":info.get("categories",[]),
            "identifiers":info.get("industryIdentifiers",[]),
            "info_link":info.get("infoLink"),
            "preview_link":info.get("previewLink"),
            "web_reader_link":info.get("webReaderLink"),
            "viewability":access.get("viewability"),
            "public_domain_flag":access.get("publicDomain"),
            "pdf_available":access.get("pdf",{}).get("isAvailable",False),
            "epub_available":access.get("epub",{}).get("isAvailable",False),
            "candidate_full_view_public_domain":access.get("viewability")=="ALL_PAGES" and access.get("publicDomain") is True
        })
    return {
        "schema_version":1,
        "source":"Google Books API",
        "query":query,
        "retrieved_at":datetime.now(timezone.utc).isoformat(),
        "discovery_status":"ok",
        "total_items":payload.get("totalItems",0),
        "items":items,
        "limitations":[
            "Google Books catalog flags are discovery metadata, not a legal opinion.",
            "Cross-check the exact edition, jurisdiction, item-level rights and source repository before ingesting text.",
            "Preview-only and copyrighted records are metadata/link-only; this script never extracts their text.",
            "No API key or paid service is required for this basic public catalog request, subject to Google's current terms and rate limits."
        ]
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query",required=True)
    p.add_argument("--max-results",type=int,default=10)
    p.add_argument("--delay",type=float,default=0.0)
    a=p.parse_args()
    if a.delay>0: time.sleep(min(a.delay,5))
    print(json.dumps(discover(a.query,a.max_results),ensure_ascii=False,indent=2,sort_keys=True))
if __name__=="__main__": main()
