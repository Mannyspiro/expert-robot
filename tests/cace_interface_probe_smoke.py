#!/usr/bin/env python3
import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "probe_cace_interfaces.py"

spec = importlib.util.spec_from_file_location("probe", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    path = root / "cace_studio" / "modules" / "fem.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "class Demo(Module):\n"
        "    def validate(self, inputs, params):\n"
        "        return None\n"
        "    def execute(self, inputs, params, ctx):\n"
        "        return {}\n"
        "    def verify(self, inputs, params, outputs, ctx):\n"
        "        return True\n",
        encoding="utf-8",
    )
    rows = module.python_interfaces(root)
    fem = next(x for x in rows if x["path"].endswith("fem.py"))
    assert fem["status"] == "OK"
    demo = next(x for x in fem["classes"] if x["name"] == "Demo")
    names = [m["name"] for m in demo["methods"]]
    assert names == ["validate", "execute", "verify"]

print("CACE interface probe: PASS")
