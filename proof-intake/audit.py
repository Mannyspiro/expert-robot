import pathlib, re, sys
text = pathlib.Path(sys.argv[1]).read_text()
targets = ["residual_component_bound", "energy_error_bound", "linear_residual_certificate", "linear_residual_bound", "invalid_linear_upper_rejected", "exp_unit_certificate", "exp_unit_bound"]
allowed = {"propext", "Classical.choice", "Quot.sound"}
for suffix in targets:
    name = "CACEFormal.CertifiedIntervalBounds." + suffix
    reports = re.findall(re.escape(name) + r"['’]?\s+depends on axioms:\s*\[([^\]]*)\]", text, re.S)
    none = re.findall(re.escape(name) + r"['’]?\s+does not depend on any axioms", text)
    if len(reports) + len(none) != 1:
        raise SystemExit("FAIL: missing/duplicate target " + name)
    axioms = {a.strip() for a in reports[0].split(",") if a.strip()} if reports else set()
    if axioms - allowed:
        raise SystemExit("FAIL: unexpected axioms for " + name + ": " + str(sorted(axioms - allowed)))
    print("KERNEL_AXIOM_AUDIT", name, sorted(axioms))
if re.search(r"\berror:", text):
    raise SystemExit("FAIL: Lean error")
print("CACE_COMPATIBLE_PROOF_AXIOM_AUDIT_OK")
