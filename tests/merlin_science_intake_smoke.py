#!/usr/bin/env python3
import importlib.util
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("science_intake",root/"scripts/merlin_science_intake.py")
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
import gzip, json, subprocess, sys, tempfile
with tempfile.TemporaryDirectory() as td:
    root=Path(td)/"staging"; root.mkdir()
    record=Path(td)/"record.json"; record.write_text(json.dumps(base))
    content=Path(td)/"source.txt"; content.write_bytes(b"small public domain source text")
    out=root/"book.json"
    cmd=[sys.executable,str(root_repo/"scripts/merlin_science_intake.py")] if False else None
    cmd=[sys.executable,str(root.parents[1]/"scripts/merlin_science_intake.py"),"--record",str(record),"--content",str(content),"--out",str(out),"--staging-root",str(root),"--free-disk-reserve-bytes","0"]
    done=subprocess.run(cmd,capture_output=True,text=True)
    assert done.returncode==0, done.stderr
    staged=json.loads(out.read_text())
    stored=root/staged["content_storage"]["path"]
    assert stored.exists() and gzip.decompress(stored.read_bytes())==content.read_bytes()
    assert staged["content_storage"]["compression"]=="gzip"
    blocked=subprocess.run(cmd+["--max-staging-bytes","1"],capture_output=True,text=True)
    assert blocked.returncode==2
print("Merlin rights-aware source intake and bounded compressed storage smoke passed.")
