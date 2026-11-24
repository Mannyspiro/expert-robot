#!/usr/bin/env python3
import importlib.util
from pathlib import Path
repo_root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("science_intake",repo_root/"scripts/merlin_science_intake.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
base={"source_id":"book:newton-principia","title":"Principia","creator":"Isaac Newton","repository":"Project Gutenberg","canonical_url":"https://www.gutenberg.org/ebooks/76404","rights_status":"public_domain_verified","provenance":{"edition":"1846","catalog":"PG"}}
metadata=mod.stage(base)
assert metadata["content_ingested"] is False and metadata["canonical_research_graph_write"] is False
full=mod.stage(base,b"public-domain sample")
assert full["content_sha256"] and full["content_ingested"] is True
bad=dict(base,rights_status="preview_only")
try: mod.stage(bad,b"must not ingest")
except mod.IntakeError: pass
else: raise AssertionError("preview-only content must be rejected")
open_license=dict(base,rights_status="open_license_verified",license_uri=None)
try: mod.stage(open_license,b"no license URI")
except mod.IntakeError: pass
else: raise AssertionError("open license must have license URI")
nc=dict(base,rights_status="open_license_verified",license_uri="https://creativecommons.org/licenses/by-nc-sa/4.0/",license_id="CC-BY-NC-SA-4.0")
try: mod.stage(nc,b"NC-SA source")
except mod.IntakeError: pass
else: raise AssertionError("NC-SA source accepted without noncommercial context")
nc["use_context"]="noncommercial"
assert mod.stage(nc,b"NC-SA source")["use_context"]=="noncommercial"
import gzip, json, subprocess, sys, tempfile
with tempfile.TemporaryDirectory() as td:
    staging_root=Path(td)/"staging"; staging_root.mkdir()
    record=Path(td)/"record.json"; record.write_text(json.dumps(base))
    content=Path(td)/"source.txt"; content.write_bytes(b"small public domain source text")
    out=staging_root/"book.json"
    cmd=[sys.executable,str(repo_root/"scripts/merlin_science_intake.py"),"--record",str(record),"--content",str(content),"--out",str(out),"--staging-root",str(staging_root),"--free-disk-reserve-bytes","0"]
    done=subprocess.run(cmd,capture_output=True,text=True)
    assert done.returncode==0, done.stderr
    staged=json.loads(out.read_text())
    stored=staging_root/staged["content_storage"]["path"]
    assert stored.exists() and gzip.decompress(stored.read_bytes())==content.read_bytes()
    assert staged["content_storage"]["compression"]=="gzip"
    blocked_record=Path(td)/"blocked.json"
    blocked_record.write_text(json.dumps(dict(base,source_id="book:blocked",canonical_url="https://example.org/blocked")))
    blocked_cmd=[sys.executable,str(repo_root/"scripts/merlin_science_intake.py"),"--record",str(blocked_record),"--content",str(content),"--out",str(staging_root/"blocked.json"),"--staging-root",str(staging_root),"--free-disk-reserve-bytes","0","--max-staging-bytes","1"]
    blocked=subprocess.run(blocked_cmd,capture_output=True,text=True)
    assert blocked.returncode==2
print("Merlin rights-aware source intake and bounded compressed storage smoke passed.")
