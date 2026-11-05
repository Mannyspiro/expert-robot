#!/usr/bin/env python3
import importlib.util, json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("science_ideonomy_bridge",root/"scripts/merlin_science_ideonomy_packet.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
d=json.loads((root/"research/science/reading-notes/newton-principia-reading.json").read_text())
prompt,digest=mod.build_packet(d)
assert len(digest)==64
assert "historical_science_ideonomy_analysis" in prompt
assert "authority_delta" in prompt and "0" in prompt
assert d["citations"][0]["url"] in prompt
assert "candidate_only" in prompt
plan=mod.build_engineering_plan(d)
validator_spec=importlib.util.spec_from_file_location("engineering_plan",root/"scripts/merlin_engineering_plan.py")
validator=importlib.util.module_from_spec(validator_spec);validator_spec.loader.exec_module(validator)
assert validator.validate(plan)==[]
assert plan["reasoning_plan"]["inductive"] and plan["reasoning_plan"]["deductive"]
assert plan["domain_scope"]["primary_domain"]=="humanities-philosophy"
try: mod.build_packet({"work":{},"citations":[]})
except ValueError: pass
else: raise AssertionError("missing citations must be rejected")
print("Merlin runtime ideonomy bridge contract smoke passed.")
