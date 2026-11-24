"""Fixed-source public HTTPS retrieval, no credentials or redirects.
Requires independent deployment egress controls; not production qualified.
"""
import http.client
import ssl
from .research_ingest import MAX_BYTES
from .research_html import ingest_html

HOST = "www.sba.gov"
PATH = "/"
URL = "https://" + HOST + PATH

def fetch_sba_homepage(*, snapshot_path=None):
    connection = http.client.HTTPSConnection(HOST, 443, timeout=10,
                                             context=ssl.create_default_context())
    try:
        connection.request("GET", PATH, headers={"User-Agent":"MerlinResearch/0.1",
                            "Accept":"text/html", "Accept-Encoding":"identity"})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("public source did not return HTTP 200")
        if response.headers.get_content_type() != "text/html":
            raise ValueError("unexpected content type")
        if response.headers.get("Content-Encoding","identity").lower() != "identity":
            raise ValueError("unsupported content encoding")
        body = response.read(MAX_BYTES+1)
        page = ingest_html(URL, body)
        if snapshot_path is not None:
            import json
            from pathlib import Path
            from .research_snapshot import snapshot, replay
            record = snapshot(URL, body)
            if replay(record).text != page.text:
                raise ValueError('snapshot replay mismatch')
            with Path(snapshot_path).open('x', encoding='utf-8') as output:
                json.dump(record, output, sort_keys=True)
        return {"source_url":page.url,"source_sha256":page.source_sha256,
                "extracted_characters":len(page.text),"claims_verified":0,
                "data_class":page.data_class,"source_authenticity_verified":False,"untrusted_content":True,
                "egress_policy":"not_independently_verified"}
    finally:
        connection.close()
