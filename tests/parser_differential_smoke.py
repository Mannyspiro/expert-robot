import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from experiment_parser_differential import canonical, oracle, permitted, router, run, mismatch

for raw, expected in [("/", "/"), ("/%70ublic/x", "/public/x"), ("/private", "/private"), ("/public/a_b-9", "/public/a_b-9")]:
    assert canonical(raw) == oracle(raw) == expected
for raw in ["/public/../private", "/public/%2fprivate", "/public/%252e", "//public", "/public?x=1", "/%ff", "/%", "/public/", "/public\n"]:
    assert oracle(raw) is None
    try:
        canonical(raw)
    except (ValueError, UnicodeError):
        pass
    else:
        raise AssertionError(raw)
assert mismatch("/public/../private")
assert mismatch("/publicity")  # raw-prefix authorization mutation
assert oracle("/%70ublic") != "/%70ublic"  # identity-normalizer mutation
try:
    canonical("/public/%252e%252e/private")  # extra-decode consumer mutation is excluded at the boundary
except ValueError:
    pass
else:
    raise AssertionError("residual percent accepted")
report = run()
assert report["repair_violations"] == 0 and report["original_mismatches"] > 0
print("Differential parser witnesses, independent oracle, boundary regressions: PASS")
