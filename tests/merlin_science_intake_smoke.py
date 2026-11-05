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
print("Merlin rights-aware source intake smoke passed.")
