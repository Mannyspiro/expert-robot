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

def fetch_sba_homepage():
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
        return {"source_url":page.url,"source_sha256":page.source_sha256,
                "extracted_characters":len(page.text),"claims_verified":0,
                "data_class":"public_research","untrusted_content":True,
                "egress_policy":"not_independently_verified"}
    finally:
        connection.close()
