"""Bounded offline source-to-sink experiment on a deliberately restricted Python AST.

This is NOT a general Python static analyzer, application audit, or a security proof.
Unsupported syntax raises Unsupported; no sockets, subprocesses or user code execution.
"""
import argparse
import ast
import hashlib
import json

FIXTURES = {
    "safe": "def f(raw):\n p = canonical(raw)\n if permitted(p):\n  sink(p)\n",
    "safe_alias": "def f(raw):\n p = canonical(raw)\n q = p\n if permitted(q):\n  sink(p)\n",
    "safe_nested": "def f(raw):\n p = canonical(raw)\n if permitted(p):\n  if logged_in():\n   sink(p)\n",
    "safe_early_exit": "def f(raw):\n p = canonical(raw)\n if permitted(p):\n  pass\n else:\n  return\n sink(p)\n",
    "raw_sink": "def f(raw):\n sink(raw)\n",
    "wrong_value": "def f(raw):\n p = canonical(raw)\n if permitted(p):\n  sink(raw)\n",
    "irrelevant_guard": "def f(raw):\n if permitted('/public'):\n  sink(raw)\n",
    "guard_too_late": "def f(raw):\n sink(raw)\n if permitted(raw):\n  return raw\n",
    "unguarded_suffix": "def f(raw):\n p = canonical(raw)\n if permitted(p):\n  pass\n sink(p)\n",
    "unchecked_else": "def f(raw):\n p = canonical(raw)\n if permitted(p):\n  pass\n else:\n  sink(p)\n",
    "stale_guard": "def f(raw):\n p = canonical(raw)\n if permitted(p):\n  p = canonical('/private')\n  sink(p)\n",
    "login_only": "def f(raw):\n p = canonical(raw)\n if logged_in():\n  sink(p)\n",
    "raw_guard_is_not_canonical": "def f(raw):\n if permitted(raw):\n  sink(raw)\n",
    "safe_branch_paths": "def f(raw):\n p = canonical(raw)\n if permitted(p):\n  sink(p)\n else:\n  return\n",
}
EXPECTED_UNMEDIATED = {
    "safe": False, "safe_alias": False, "safe_nested": False,
    "safe_early_exit": False, "safe_branch_paths": False,
    "raw_sink": True, "wrong_value": True, "irrelevant_guard": True,
    "guard_too_late": True, "unguarded_suffix": True, "unchecked_else": True,
    "stale_guard": True, "login_only": True, "raw_guard_is_not_canonical": True,
}

class Unsupported(ValueError):
    """An unmodeled construct cannot count as a verified safe path."""


def value(node, names):
    if isinstance(node, ast.Name):
        if node.id not in names:
            raise Unsupported("unknown variable")
        return names[node.id]
    if isinstance(node, ast.Constant) and type(node.value) is str:
        return ("literal", node.value)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "canonical" and len(node.args) == 1
            and not node.keywords):
        return ("canonical", value(node.args[0], names))
    raise Unsupported("unsupported value expression")


def analyze(source):
    tree = ast.parse(source)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise Unsupported("exactly one function required")
    fn = tree.body[0]
    if fn.decorator_list or fn.returns or fn.args.defaults or fn.args.kwonlyargs or fn.args.posonlyargs or fn.args.vararg or fn.args.kwarg:
        raise Unsupported("unsupported function signature")
    if len(fn.args.args) != 1 or fn.args.args[0].arg != "raw":
        raise Unsupported("single raw argument required")
    observed = []
    # State: (name -> symbolic value, positively verified values, trace)
    states = [({"raw": ("raw",)}, frozenset(), ())]
    for stmt in fn.body:
        states = step(stmt, states, observed)
    return {"sink_paths": observed,
            "unmediated": [p for p in observed if not p["guarded"]],
            "exit_states": len(states)}


def step(stmt, states, observed):
    outgoing = []
    for names, guards, trace in states:
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                raise Unsupported("assignment shape")
            name = stmt.targets[0].id
            if name == "raw":
                raise Unsupported("raw input reassignment not modeled")
            assigned = dict(names)
            assigned[name] = value(stmt.value, names)
            outgoing.append((assigned, guards, trace + ("assign:" + name,)))
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if (not isinstance(call.func, ast.Name) or call.func.id != "sink"
                    or len(call.args) != 1 or call.keywords):
                raise Unsupported("unsupported side effect")
            v = value(call.args[0], names)
            guarded = v[0] == "canonical" and v in guards
            observed.append({"trace": list(trace + ("sink",)),
                             "value": repr(v), "guarded": guarded})
            outgoing.append((names, guards, trace + ("sink",)))
        elif isinstance(stmt, ast.If):
            call = stmt.test
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.keywords:
                raise Unsupported("unknown conditional")
            if call.func.id == "permitted" and len(call.args) == 1:
                checked = value(call.args[0], names)
                true_guards = guards | {checked}
                kind = "permitted"
            elif call.func.id == "logged_in" and not call.args:
                true_guards = guards
                kind = "logged_in"
            else:
                raise Unsupported("unrecognized guard")
            outgoing.extend(block(stmt.body, [(dict(names), true_guards, trace + (kind + ":true",))], observed))
            outgoing.extend(block(stmt.orelse, [(dict(names), guards, trace + (kind + ":false",))], observed))
        elif isinstance(stmt, ast.Return):
            if stmt.value is not None:
                value(stmt.value, names)
            # Terminated branch must not reach subsequent statements.
        elif isinstance(stmt, ast.Pass):
            outgoing.append((names, guards, trace + ("pass",)))
        else:
            raise Unsupported("unmodeled statement: " + type(stmt).__name__)
        if len(outgoing) > 256:
            raise Unsupported("symbolic path budget exceeded")
    return outgoing


def block(statements, states, observed):
    for stmt in statements:
        states = step(stmt, states, observed)
    return states


def run():
    cases = {name: analyze(src) for name, src in sorted(FIXTURES.items())}
    assert all(bool(cases[name]["unmediated"]) == unsafe
               for name, unsafe in EXPECTED_UNMEDIATED.items())
    rejected = []
    for name, source in {
        "loop": "def f(raw):\n while raw:\n  sink(raw)\n",
        "unmodeled_call": "def f(raw):\n sink(transform(raw))\n",
        "unknown_sink": "def f(raw):\n send(raw)\n",
        "mutate_raw": "def f(raw):\n raw = '/public'\n sink(raw)\n",
    }.items():
        try:
            analyze(source)
        except Unsupported:
            rejected.append(name)
        else:
            raise AssertionError("unmodeled syntax accepted: " + name)
    return {
        "experiment": "security-flow-mediation-v2",
        "fixture_count": len(cases),
        "fixture_sha256": hashlib.sha256(json.dumps(FIXTURES, sort_keys=True).encode()).hexdigest(),
        "cases": cases,
        "safe_fixtures": sum(not EXPECTED_UNMEDIATED[name] for name in cases),
        "unmediated_fixtures": sum(EXPECTED_UNMEDIATED.values()),
        "unsupported_fixtures_rejected": rejected,
        "all_expected_results_matched": True,
        "network_operations": 0,
        "arbitrary_code_executed": False,
        "real_project_audited": False,
        "general_python_soundness_claimed": False,
        "formal_qualified": False,
        "authority_expanded": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", required=True)
    args = parser.parse_args()
    report = run()
    with open(args.o, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}))
