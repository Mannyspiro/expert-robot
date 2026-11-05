#!/usr/bin/env python3
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
web=root/"apps/merlin-web"
data=json.loads((web/"science-map.json").read_text())
assert data["schema_version"]==1
assert len(data["domains"])>=10
assert len(data["historical_programs"])>=5
assert len(data["sources"])>=10
assert all(d.get("id") and d.get("name") and d.get("branches") for d in data["domains"])
assert all(s.get("id") and s.get("name") and s.get("url") for s in data["sources"])
for p in ("index.html","app.js","styles.css"):
 assert (web/p).is_file()
html=(web/"index.html").read_text()
assert 'science-map.json' in (web/"app.js").read_text()
assert 'id="disciplines"' in html and 'id="sources"' in html and 'id="history"' in html
contract=json.loads((root/"research/science/ingestion-contract.v1.json").read_text())
assert "rights_check" in contract["stages"]
assert "source_spans" in contract["claim_record_required"]
print(f"Merlin science atlas smoke passed: {len(data['domains'])} domains, {len(data['sources'])} sources.")
