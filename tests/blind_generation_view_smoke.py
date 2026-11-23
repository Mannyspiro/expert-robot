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

# `end` closes mutual blocks before it closes the surrounding namespace.
mutual="""namespace Hidden
mutual
  def publicA : Nat := 1
  def publicB : Nat := 2
end
theorem secret : True := by
  have hiddenAfterMutual : True := by trivial
  exact hiddenAfterMutual
end Hidden
"""
clean=sanitize(mutual)
assert "def publicA" in clean and "def publicB" in clean
assert "theorem secret" not in clean and "hiddenAfterMutual" not in clean
assert clean.count("[blind-eval declaration redacted]") == 1
assert clean.rstrip().endswith("end Hidden")

# Declaration keyword/name line breaks and command wrappers do not reveal proofs.
for declaration in (
    "theorem\n  secret",
    "private theorem\n  secret",
    "set_option pp.universes true in theorem secret",
    "open Nat in theorem secret",
    "set_option pp.universes true in open Nat in theorem\n  secret",
    "set_option pp.universes true in\n@[simp]\ntheorem\n  secret",
):
    source=f"namespace Hidden\n{declaration} : True := by\n  have hiddenWrappedBody : True := by trivial\n  exact hiddenWrappedBody\nend Hidden\n"
    clean=sanitize(source)
    assert "hiddenWrappedBody" not in clean, (declaration,clean)
    assert clean.count("[blind-eval declaration redacted]") == 1, (declaration,clean)
    assert "pp.universes" not in clean and "open Nat" not in clean, clean
    assert clean.rstrip().endswith("end Hidden")

# Quoted ordinary identifiers denote the same namespace/declaration symbols.
for namespace,name in (("«Hidden»","secret"),("Hidden","«secret»"),("«Hidden»","«secret»")):
    clean=sanitize(f"namespace {namespace}\ntheorem {name} : True := by\n  have hiddenQuotedBody : True := by trivial\n  exact hiddenQuotedBody\nend {namespace}\n")
    assert "hiddenQuotedBody" not in clean and "theorem" not in clean
    assert clean.count("[blind-eval declaration redacted]") == 1
    assert clean.rstrip().endswith(f"end {namespace}")

# A quoted atom containing a dot is distinct from a hierarchical Lean name.
clean=sanitize("theorem «Hidden.secret» : True := by\n  have publicQuotedBody : True := by trivial\n  exact publicQuotedBody\n")
assert "publicQuotedBody" in clean
assert "[blind-eval declaration redacted]" not in clean
assert "theorem «[REDACTED_EVAL_SYMBOL]»" in clean

# A later named declaration is a new command even if it indents more deeply.
clean=sanitize("namespace Hidden\naxiom secret : True\n  axiom publicA : True\nend Hidden\n")
assert "axiom secret" not in clean
assert "  axiom publicA : True" in clean

# A declaration-looking syntax quotation remains part of the hidden proof.
quoted_proof="""import Mathlib
namespace Hidden
theorem secret : True := by
  run_tac do
    let _stx ← `(command|
      theorem publicLike : True := by trivial)
    pure ()
  have hiddenBodyAfterQuotation : True := by trivial
  exact hiddenBodyAfterQuotation
theorem actualPublic : True := by trivial
end Hidden
"""
clean=sanitize(quoted_proof)
assert "publicLike" not in clean and "hiddenBodyAfterQuotation" not in clean
assert "theorem actualPublic" in clean
assert clean.rstrip().endswith("end Hidden")
# Quoted punctuation, nested parentheses and nested quotes do not end masking.
quotation_code=list(generation_view.lean_code_lines("""let syntaxValue := `(command|
  def publicLike := ("(", `(term| (1)), «name(»)
)
theorem afterQuotation : True := by trivial
"""))
assert all(not line.strip() for line in quotation_code[1:3])
assert quotation_code[3].startswith("theorem afterQuotation")

# Quoted identifiers and Char literals shield punctuation from the lexer.
for public_declaration in (
    'def «"» : Nat := 0',
    'def «--/-"(» : Nat := 0',
    "def quoteCharacter : Char := '\"'",
    "def escapedQuote : Char := '\\\"'",
    "def apostropheCharacter : Char := '\\\''",
    "def public'a' : Nat := 0",
):
    clean=sanitize(f"namespace Hidden\n{public_declaration}\ntheorem secret : True := by\n  have hiddenBodyAfterPunctuation : True := by trivial\n  exact hiddenBodyAfterPunctuation\nend Hidden\n")
    assert public_declaration in clean
    assert "hiddenBodyAfterPunctuation" not in clean and "theorem secret" not in clean
    assert clean.rstrip().endswith("end Hidden")
quotation_code=list(generation_view.lean_code_lines('let value := `(command| def «"» := 0)\ntheorem afterQuotation : True := by trivial\n'))
assert quotation_code[1].startswith("theorem afterQuotation")
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
