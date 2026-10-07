#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("bridge",ROOT/"scripts"/"compile_crl_to_cace_nd.py")
module=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

crl_path=ROOT/"config"/"examples"/"portal_p2_boundary_null.crl"
ir=module.crl.parse(crl_path.read_text(encoding="utf-8"),str(crl_path))
packet=module.build(ir,segments=32,source=1.0,theta=0.5)

assert packet["mesh"]["dimension"]==2
assert len(packet["mesh"]["vertices"])>0
assert len(packet["mesh"]["elements"])>0
assert packet["mesh"]["max_radial_chord_error"]>0
mods=[x["module"] for x in packet["routes"]["nd_poisson_adaptive"]["nodes"]]
assert mods==[
 "SimplexMeshND","P1SimplexSpaceND","SimplexQuadratureND","PoissonAssemblyND",
 "LinearSolverND","AlgebraicResidualND","ResidualEstimatorND","AdaptiveRefinement2D"
]
cert=[x["module"] for x in packet["routes"]["certified_algebraic"]["nodes"]]
assert "CertifiedPoissonAssembly" in cert
assert "IntervalAlgebraicResidual" in cert
assert "DiscreteEnergyErrorCertificate" in cert
assert packet["unresolved_certification"]

print("CRL -> CACE ND bridge: PASS")
