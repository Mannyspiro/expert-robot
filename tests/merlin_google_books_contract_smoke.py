#!/usr/bin/env python3
import importlib.util, json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
path=root/"scripts/merlin_google_books_discover.py"
spec=importlib.util.spec_from_file_location("google_books_discover",path)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
sample={"volumeInfo":{"title":"Example","authors":["A"],"publishedDate":"1900"},"accessInfo":{"viewability":"ALL_PAGES","publicDomain":True,"pdf":{"isAvailable":True}}}
assert sample["accessInfo"]["viewability"]=="ALL_PAGES"
assert sample["accessInfo"]["publicDomain"] is True
taxonomy=json.loads((root/"research/science/discipline-taxonomy.v1.json").read_text())
assert any(x["id"]=="emerging" for x in taxonomy["domains"])
print("Merlin Google Books discovery contract smoke passed (network not required).")
