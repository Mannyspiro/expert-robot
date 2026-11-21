"""Fixed stdin/stdout driver for the separately isolated solver research worker.

Generated Python is executed only in this worker process. The host coordinator
uses SystemdFixedPythonProcess with this exact file hash; importing this module
does not execute a candidate. Expected answers are never sent to the worker.
"""
from fractions import Fraction
import json
import sys
import time
from types import FunctionType


def _rational(value):
    if (not isinstance(value, list) or len(value) != 2
            or any(type(x) is not int for x in value)
            or abs(value[0]) > 10**12 or not 1 <= value[1] <= 10**12):
        raise ValueError("bounded rational pair required")
    return Fraction(*value)


def _error(exc):
    return {"status": "error", "error_class": type(exc).__name__[:80],
            "message": str(exc)[:160]}


def main():
    raw = sys.stdin.buffer.read(65537)
    if len(raw) > 65536:
        raise ValueError("fixed solver input exceeds 64 KiB")
    request = json.loads(raw)
    if (not isinstance(request, dict) or set(request) != {"schema", "program", "cases"}
            or request["schema"] != "merlin-solver-worker-input/1"
            or not isinstance(request["program"], str)
            or not 1 <= len(request["program"].encode("utf-8")) <= 8192
            or not isinstance(request["cases"], list) or not 1 <= len(request["cases"]) <= 12):
        raise ValueError("fixed solver input schema required")
    cases = []
    for case in request["cases"]:
        if (not isinstance(case, dict) or set(case) != {"case_id", "matrix", "right"}
                or not isinstance(case["case_id"], str) or not 1 <= len(case["case_id"]) <= 100
                or not isinstance(case["right"], list) or len(case["right"]) > 12
                or not isinstance(case["matrix"], list)
                or len(case["matrix"]) != len(case["right"])):
            raise ValueError("bounded solver case required")
        count = len(case["right"])
        if any(not isinstance(row, list) or len(row) != count for row in case["matrix"]):
            raise ValueError("square matrix required")
        cases.append((case["case_id"], [[_rational(x) for x in row] for row in case["matrix"]],
                      [_rational(x) for x in case["right"]]))
    if len({case[0] for case in cases}) != len(cases):
        raise ValueError("distinct case IDs required")
    namespace = {"Fraction": Fraction}
    compile_error = None
    try:
        # This operation must never move into the coordinator/web process.
        exec(compile(request["program"], "model-candidate", "exec"), namespace)
        solve = namespace.get("_solve")
        if not isinstance(solve, FunctionType):
            raise ValueError("candidate must define _solve")
    except BaseException as exc:
        compile_error = _error(exc)
    records = []
    for case_id, matrix, right in cases:
        before = ([list(row) for row in matrix], list(right))
        started = time.process_time_ns()
        outcome = compile_error
        if outcome is None:
            try:
                answer = solve(matrix, right)
                if (not isinstance(answer, list) or len(answer) != len(right)
                        or any(type(x) is not Fraction for x in answer)
                        or any(abs(x.numerator) > 10**12 or x.denominator > 10**12 for x in answer)):
                    raise ValueError("candidate returned an unsupported solution")
                outcome = {"status": "solved", "solution": [[x.numerator, x.denominator] for x in answer]}
            except BaseException as exc:
                outcome = _error(exc)
        records.append({"case_id": case_id, "outcome": outcome,
                        "inputs_unchanged": matrix == before[0] and right == before[1],
                        "cpu_nanoseconds": time.process_time_ns() - started})
    report = {"schema": "merlin-solver-worker-output/1", "cases": records}
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(encoded) > 7000:
        raise ValueError("fixed solver output exceeds receipt budget")
    sys.stdout.buffer.write(encoded + b"\n")


if __name__ == "__main__":
    main()
