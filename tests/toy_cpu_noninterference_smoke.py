#!/usr/bin/env python3
"""Pure Python, no external packages, no live security testing."""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from experiment_toy_cpu_noninterference import (cpu_run, independent_oracle,
                                                evaluate, enumerate_cache_states, MODES)

r = evaluate()
assert r["total_secret_pairs_checked"] == 192
assert r["modes"]["leaky"]["cache_counterexample_count"] == 24
for name in ("squash", "constant_line"):
    assert r["modes"][name]["cache_observation_noninterference"]
    assert r["modes"][name]["cache_counterexample_count"] == 0
for name in MODES:
    assert r["modes"][name]["architectural_noninterference"]
assert r["oracle_agreement"] is True and r["formal_kernel_checked"] is False
assert r["cpu_hardware_tested"] is False and r["rsi_promotion_authorized"] is False
for pub in (0, 1):
    for cache in enumerate_cache_states():
        for predicted in (False, True):
            for secret in (0, 1):
                for mode in MODES:
                    assert cpu_run(secret, pub, predicted, cache, mode) == independent_oracle(
                        secret, pub, predicted, cache, mode)
for args in ((True, 0, False, frozenset(), "leaky"),
             (0, 2, False, frozenset(), "leaky"),
             (0, 0, 0, frozenset(), "leaky"),
             (0, 0, False, {0}, "leaky"),
             (0, 0, False, frozenset((99,)), "leaky"),
             (0, 0, False, frozenset(), "unknown")):
    try:
        cpu_run(*args)
    except ValueError:
        pass
    else:
        raise AssertionError("malformed model input accepted: " + str(args))
# Red team the observation: architectural outputs agree, cache sets differ.
a = cpu_run(0, 0, True, frozenset(), "leaky")
b = cpu_run(1, 0, True, frozenset(), "leaky")
assert a[0] == b[0] == 0 and a[1] != b[1]
assert cpu_run(0, 0, True, frozenset(), "squash") == cpu_run(1, 0, True, frozenset(), "squash")
assert cpu_run(0, 0, True, frozenset(), "constant_line") == cpu_run(1, 0, True, frozenset(), "constant_line")
assert r == evaluate(), "non-deterministic evidence"
hash_field=r.pop("model_report_sha256")
canonical=json.dumps(r,sort_keys=True,separators=(",",":"),ensure_ascii=True)
assert hashlib.sha256(canonical.encode("utf-8")).hexdigest()==hash_field
print("Toy CPU hyperproperty and counterexample regression: PASS (192 pairs; 24 leaky pairs)")
