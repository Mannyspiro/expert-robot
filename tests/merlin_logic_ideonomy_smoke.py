#!/usr/bin/env python3
import importlib.util
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,root/"scripts"/path); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
logic=load("logic","merlin_logic_lenses.py")
assert logic.fuzzy_ops(0.4,0.7)["godel_and"]==0.4
assert abs(logic.fuzzy_ops(0.4,0.7)["product_and"]-0.28)<1e-12
assert abs(logic.fuzzy_ops(0.4,0.7)["lukasiewicz_and"]-0.1)<1e-12
table=logic.finite_table(3,2)
assert table["row_count"]==9 and len(table["rows"])==9
try: logic.finite_table(10,4,4096)
except ValueError: pass
else: raise AssertionError("truth-table expansion cap was not enforced")
assert len(logic.rank_candidates("uncertain partial membership evidence"))>=10
composed=logic.compose_candidates("temporal topology and uncertain constraints",64)
assert composed["total_combinations"]==14*15*14
assert len(composed["ranked_compositions"])==64
assert all("not_useful_if" in x and "validation_obligation" in x for x in composed["ranked_compositions"])
ideas=load("ideas","merlin_ideonomy.py")
a=ideas.enumerate_space("graph topology dynamics",48)
b=ideas.enumerate_space("graph topology dynamics",48)
assert a["total_combinations"]==11*12*10*10
assert [x["idea_id"] for x in a["ideas"]]==[x["idea_id"] for x in b["ideas"]]
assert all(x["disconfirmation"] for x in a["ideas"])
packet=load("packet","merlin_math_research_packet.py")
p=packet.build("Investigate an invariant across algebraic and geometric representations",24,3,2)
assert p["logic_lenses"]["finite_logic"]["row_count"]==9
assert p["logic_lenses"]["ranked_compositions"]["total_combinations"]==14*15*14
assert len(p["ideonomy"]["ideas"])==24
assert p["lean_bridge"]["status"]=="candidate_generation_only"
assert len(p["engineering_plan"]["research_methods"]["ideonomy"]["ranked_candidates"])==24
assert len(p["engineering_plan"]["research_methods"]["logic_lenses"]["ranked_compositions"])==24
validator=load("validator","merlin_engineering_plan.py")
incomplete=p["engineering_plan"].copy()
incomplete["research_methods"]=dict(incomplete["research_methods"])
incomplete["research_methods"]["ideonomy"]=dict(incomplete["research_methods"]["ideonomy"])
incomplete["research_methods"]["ideonomy"].pop("ranked_candidates")
assert any("ranked ideonomy candidates" in e for e in validator.validate(incomplete))
print("Fuzzy operators, finite n-valued truth tables, ranked logic lenses, bounded ideonomy and Lean research packet smoke passed.")
