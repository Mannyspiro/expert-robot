"""Offline bounded source-to-sink complete-mediation study; no networking."""
import ast
import argparse
import json
import hashlib

FIXTURES = {
    "safe": "def f(raw):\n p = canonical(raw)\n if permitted(p):\n  sink(p)\n",
    "raw_sink": "def f(raw):\n sink(raw)\n",
    "wrong_value": "def f(raw):\n p = canonical(raw)\n if permitted(p):\n  sink(raw)\n",
    "irrelevant_guard": "def f(raw):\n if permitted('/public'):\n  sink(raw)\n",
    "guard_too_late": "def f(raw):\n sink(raw)\n if permitted(raw):\n  return raw\n",
    "safe_nested": "def f(raw):\n p = canonical(raw)\n if permitted(p):\n  if logged_in():\n   sink(p)\n",
}
EXPECTED = {"safe": False, "raw_sink": True, "wrong_value": True,
            "irrelevant_guard": True, "guard_too_late": True, "safe_nested": False}

class Unsupported(Exception):
    pass

def value(node, names):
    if isinstance(node, ast.Name):
        return names.get(node.id, None)
    if isinstance(node, ast.Constant):
        return None
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "canonical" and len(node.args) == 1):
        origin = value(node.args[0], names)
        return ("canonical", origin) if origin is not None else None
    raise Unsupported("unsupported value expression")

def analyze(source):
    tree = ast.parse(source)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise Unsupported("one function required")
    fn = tree.body[0]
    if len(fn.args.args) != 1 or fn.args.args[0].arg != "raw":
        raise Unsupported("single raw argument required")
    paths = []

    def walk(nodes, names, guards, trace):
        for stmt in nodes:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                names = dict(names)
                names[stmt.targets[0].id] = value(stmt.value, names)
                trace = trace + ["assign:" + stmt.targets[0].id]
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call = stmt.value
                if not isinstance(call.func, ast.Name) or call.func.id != "sink" or len(call.args) != 1:
                    raise Unsupported("unknown side effect")
                v = value(call.args[0], names)
                paths.append({"trace": trace + ["sink"], "guarded": v is None or v in guards})
            elif isinstance(stmt, ast.If):
                cond = stmt.test
                if not isinstance(cond, ast.Call) or not isinstance(cond.func, ast.Name):
                    raise Unsupported("unknown conditional")
                if cond.func.id == "permitted" and len(cond.args) == 1:
                    g = value(cond.args[0], names)
                    walk(stmt.body, dict(names), guards | ({g} if g is not None else set()), trace + ["permit"])
                elif cond.func.id == "logged_in" and not cond.args:
                    walk(stmt.body, dict(names), guards, trace + ["login"])
                else:
                    raise Unsupported("unknown guard")
                walk(stmt.orelse, dict(names), guards, trace + ["else"])
                return
            elif isinstance(stmt, ast.Return):
                if stmt.value is not None:
                    value(stmt.value, names)
                return
            else:
                raise Unsupported("unsupported control flow")
    walk(fn.body, {"raw": ("raw",)}, set(), [])
    return {"sink_paths": paths, "unmediated": [p for p in paths if not p["guarded"]]}

def run():
    results = {k: analyze(v) for k, v in sorted(FIXTURES.items())}
    assert all(bool(results[k]["unmediated"]) == expected for k, expected in EXPECTED.items())
    try:
        analyze("def f(raw):\n while raw:\n  sink(raw)\n")
        raise AssertionError("unsupported syntax accepted")
    except Unsupported:
        pass
    return {"experiment": "security-flow-mediation-v1",
            "fixture_count": len(FIXTURES),
            "fixture_sha256": hashlib.sha256(json.dumps(FIXTURES, sort_keys=True).encode()).hexdigest(),
            "results": results, "all_expected_results_matched": True,
            "unsupported_syntax_fails_closed": True, "network_operations": 0,
            "real_project_audited": False, "formal_qualified": False, "authority_expanded": False}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", required=True)
    args = parser.parse_args()
    report = run()
    with open(args.o, "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}))
