#!/usr/bin/env python3
"""Metadata-only YouTube discovery and rights-gated VTT/SRT transcript intake."""
import argparse, hashlib, json, os, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

API="https://www.googleapis.com/youtube/v3/search"


def discover(query, limit=10, api_key=None):
    key=api_key or os.environ.get("YOUTUBE_DATA_API_KEY")
    base={"schema_version":1,"source":"YouTube Data API v3","query":query,
          "retrieved_at":datetime.now(timezone.utc).isoformat(),"transcript_text_fetched":False}
    if not key:
        return {**base,"status":"metadata_discovery_not_run","reason":"YOUTUBE_DATA_API_KEY not configured; no network request made","items":[]}
    params=urllib.parse.urlencode({"part":"snippet","type":"video","q":query,"maxResults":max(1,min(limit,25)),"key":key})
    req=urllib.request.Request(API+"?"+params,headers={"User-Agent":"MerlinResearchAtlas/0.1"})
    try:
        with urllib.request.urlopen(req,timeout=15) as response: payload=json.load(response)
    except urllib.error.HTTPError as e:
        return {**base,"status":"temporarily_unavailable","http_status":e.code,"items":[]}
    items=[]
    for row in payload.get("items",[]):
        sn=row.get("snippet",{}); vid=row.get("id",{}).get("videoId")
        items.append({"video_id":vid,"title":sn.get("title"),"channel":sn.get("channelTitle"),
          "published_at":sn.get("publishedAt"),"description":sn.get("description"),
          "url":"https://www.youtube.com/watch?v="+str(vid),"transcript_status":"not_checked",
          "rights_status":"unknown","media_downloaded":False})
    return {**base,"status":"ok","items":items,
            "limitations":["Metadata only; public listing does not grant transcript reuse rights.",
             "The official captions API requires OAuth and permission for the video; it is not assumed to expose arbitrary public transcripts."]}


def validate_transcript(path, rights_status, license_id=None, use_context="unknown"):
    allowed=("creator_authorized","user_supplied_with_rights","public_domain_verified","open_license_verified")
    if rights_status not in allowed:
        raise ValueError("transcript requires creator authorization, user-supplied rights, verified public domain, or a verified open license")
    if rights_status=="open_license_verified" and not license_id:
        raise ValueError("open-licensed transcript requires an explicit license identifier")
    if license_id=="CC-BY-NC-SA-4.0" and use_context!="noncommercial":
        raise ValueError("CC BY-NC-SA transcript intake requires explicit noncommercial use; commercial or unknown use is blocked")
    if path.suffix.lower() not in (".vtt",".srt"): raise ValueError("only VTT and SRT caption exports are accepted")
    raw=path.read_bytes()
    if len(raw)>2097152: raise ValueError("transcript exceeds 2 MiB limit")
    decoded=raw.decode("utf-8-sig")
    if not decoded.strip() or len(decoded)>2000000: raise ValueError("empty or oversized transcript")
    return {"transcript_sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),
            "format":path.suffix.lower()[1:],"rights_status":rights_status,
            "license_id":license_id,"use_context":use_context,"media_downloaded":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--query",default=""); p.add_argument("--limit",type=int,default=10)
    p.add_argument("--transcript",type=Path); p.add_argument("--rights-status")
    p.add_argument("--license-id"); p.add_argument("--use-context",choices=("noncommercial","commercial","unknown"),default="unknown")
    a=p.parse_args()
    if a.transcript:
        try:
            result=validate_transcript(a.transcript,a.rights_status,a.license_id,a.use_context)
            print(json.dumps({"ok":True,**result},indent=2)); return 0
        except Exception as e:
            print(json.dumps({"ok":False,"error":str(e)},indent=2)); return 2
    if not a.query: p.error("--query is required for metadata discovery")
    print(json.dumps(discover(a.query,a.limit),indent=2)); return 0


if __name__=="__main__": raise SystemExit(main())
