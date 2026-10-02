#!/usr/bin/env python3
import json
import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
policy=json.loads((ROOT/"config/blind_evaluation_policy.json").read_text())
spec=importlib.util.spec_from_file_location("generation_view",ROOT/"scripts/build_generation_view.py")
generation_view=importlib.util.module_from_spec(spec)
spec.loader.exec_module(generation_view)

# Every trusted hidden witness must remain covered if the witness suite changes.
witness_text=(ROOT/"tests/lean/hard_math_v2_witnesses.lean").read_text()
witness_namespace=re.search(r"^namespace\s+(\S+)",witness_text,re.MULTILINE).group(1)
witness_symbols={
    f"{witness_namespace}.{name}"
    for name in re.findall(r"^theorem\s+((?:validation|holdout)\d+)\b",witness_text,re.MULTILINE)
}
assert len(witness_symbols) == 12
assert {
    token for token in policy["hidden_identifiers"]
    if token.startswith(witness_namespace+".")
} == witness_symbols

def sanitize(text):
    return generation_view.sanitize_lean(text,["Hidden.secret","Hidden.finalSecret"])

final_hidden="""import Public
namespace Hidden
theorem publicSecret : True := by trivial
theorem secret : True := by
  have secretProofBody : True := by trivial
  exact secretProofBody
"""
clean=sanitize(final_hidden)
assert "theorem publicSecret" in clean
assert "theorem secret" not in clean
assert "secretProofBody" not in clean
assert clean.count("[blind-eval declaration redacted]") == 1

# Closing scopes and later commands must survive a hidden final declaration.
commands="""namespace Hidden
section Internal
  theorem finalSecret : True := by
    have finalProofBody : True := by trivial
    exact finalProofBody
end Internal
end Hidden
import PublicAfter
namespace Public
theorem secret : True := by trivial
end Public
"""
clean=sanitize(commands)
assert "finalProofBody" not in clean
assert "end Internal\nend Hidden\nimport PublicAfter\nnamespace Public" in clean
assert "theorem secret : True := by trivial" in clean
assert clean.rstrip().endswith("end Public")
clean=sanitize("namespace Hidden\ntheorem secret : True := by trivial\nimport PublicAfter\nend Hidden\n")
assert "import PublicAfter\nend Hidden" in clean

# Match complete names in their namespace, including common declaration prefixes.
prefixed="""namespace Hidden
@[simp]
private
theorem secret : True := by trivial
@[simp] protected theorem finalSecret : True := by trivial
@[simp] theorem secret_extra : True := by trivial
private theorem finalSecret_extra : True := by trivial
end Hidden
namespace Public
@[simp] theorem secret : True := by trivial
end Public
"""
clean=sanitize(prefixed)
assert clean.count("[blind-eval declaration redacted]") == 2
assert "private\n" not in clean
assert "@[simp]\n" not in clean
assert "@[simp] theorem secret_extra" in clean
assert "private theorem finalSecret_extra" in clean
assert "@[simp] theorem secret : True" in clean
clean=sanitize("namespace Public\ntheorem Hidden.secret : True := by trivial\nend Public\n")
assert "[blind-eval declaration redacted]" not in clean
assert "theorem [REDACTED_EVAL_SYMBOL] : True := by trivial" in clean

# Comment/string text must not end redaction and expose the rest of its proof.
commented="""namespace Hidden
theorem secret : True := by
/-
theorem apparentPublic : True := by trivial
/- nested comment -/
-/
  have hiddenBodyAfterComment : True := by trivial
  exact hiddenBodyAfterComment
theorem actualPublic : String :=
  "theorem secret : True"
end Hidden
"""
clean=sanitize(commented)
assert "apparentPublic" not in clean
assert "hiddenBodyAfterComment" not in clean
assert '"theorem secret : True"' in clean
assert "theorem actualPublic" in clean

# A root-qualified declaration is hidden even from another namespace.
clean=sanitize("namespace Public\nprivate theorem _root_.Hidden.secret : True := by trivial\nend Public\n")
assert "_root_.Hidden.secret" not in clean
assert clean.rstrip().endswith("end Public")

with tempfile.TemporaryDirectory() as td:
    out=Path(td)/"view"
    subprocess.run([
        sys.executable,str(ROOT/"scripts/build_generation_view.py"),
        str(ROOT),str(out),"--policy",str(ROOT/"config/blind_evaluation_policy.json")
    ],check=True,capture_output=True,text=True)

    assert not (out/"config/benchmarks").exists()
    assert not (out/"tests").exists()
    assert not (out/".github").exists()
    assert (out/"GENERATION_VIEW_MANIFEST.json").exists()
    # The real final hidden theorem formerly swallowed the namespace closure.
    derived=(out/"formal/MathAI/Geometry/Derived.lean").read_text()
    assert derived.rstrip().endswith("end MathAI.Geometry")
    assert "theorem squaredDistance_eq_radius_of_pointOnSphere" not in derived
    assert "theorem squaredDistance_self" in derived
    for item in out.rglob("*"):
        if not item.is_file():
            continue
        try:
            text=item.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for token in policy["hidden_identifiers"]:
            assert token not in text, (item,token)

print("blind generation view smoke: PASS")
