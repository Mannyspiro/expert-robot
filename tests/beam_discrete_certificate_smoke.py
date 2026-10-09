#!/usr/bin/env python3
"""Exact references, ill conditioning, outward bounds, and tamper rejection."""
import copy
import json
import math
import sys
from fractions import Fraction as F
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from certify_beam_discrete import certify, verify_certificate, sqrt_upper, replay_certificate

a, b, u = [[2.,1.],[1.,2.]], [1.,0.], [.3,-.1]
c = certify(a,b,u)
assert verify_certificate(a,b,u,c)
assert verify_certificate(a,b,u,json.loads(json.dumps(c)))
assert replay_certificate(json.loads(json.dumps(c)))
assert replay_certificate(certify([[2.]],[-0.],[-0.]))
changed_input = copy.deepcopy(c)
changed_input["stored_binary64"]["solution"][0] = (0.).hex()
try:
    replay_certificate(changed_input)
except ValueError:
    pass
else:
    raise AssertionError("changed saved solution accepted")
exact = [F(2,3), F(-1,3)]
errors = [x-F.from_float(y) for x,y in zip(exact,u)]
assert F.from_float(c["scaled_dof_linf_error_upper_m"]) >= max(map(abs,errors))
energy2 = sum(errors[i]*F.from_float(a[i][j])*errors[j] for i in range(2) for j in range(2))
assert F.from_float(c["energy_error_sqrt_j_upper"])**2 >= energy2

# A tiny residual does not imply a tiny forward error.
eps = math.nextafter(1., math.inf)-1
ill = certify([[1.,1.],[1.,1.+eps]], [0.,eps], [0.,0.])
assert ill["scaled_dof_linf_error_upper_m"] == 1
assert ill["exact_residual_inf_upper_n"] == eps
assert verify_certificate([[1.,1.],[1.,1.+eps]], [0.,eps], [0.,0.], ill)
zero = certify([[2.]], [0.], [0.])
assert zero["energy_error_sqrt_j_upper"] == 0
assert zero["scaled_dof_linf_error_upper_m"] == 0
for x in [F(1,3), F(1,10**600), F(10**600), F(0)]:
    if x > F.from_float(sys.float_info.max)**2:
        continue
    bound = sqrt_upper(x)
    assert F.from_float(bound)**2 >= x

for mutate in [lambda c:c["correction"].__setitem__(0,["0","1"]),
               lambda c:c["diagonal"].__setitem__(0,["-1","1"]),
               lambda c:c.update(scaled_dof_linf_error_upper_m=0),
               lambda c:c.update(system_sha256="wrong"),
               lambda c:c["lower"].append([1,0,["1","2"]]),
               lambda c:c["lower"][0].__setitem__(2,["1","3"]),
               lambda c:c.update(continuum_error_certified=True)]:
    bad = copy.deepcopy(c)
    mutate(bad)
    try:
        verify_certificate(a,b,u,bad)
    except ValueError:
        pass
    else:
        raise AssertionError("tampered certificate accepted")
for matrix in [[[1.,2.],[2.,1.]], [[1.,1.],[1.,1.]], [[1.,2.],[0.,1.]], [[float('nan')]], [[1.]*33 for _ in range(33)]]:
    try:
        certify(matrix,[0.]*len(matrix),[0.]*len(matrix))
    except ValueError:
        pass
    else:
        raise AssertionError("invalid/non-SPD system accepted")
print("beam certificate: exact references, ill-conditioned residual, bounds and tamper checks passed")
