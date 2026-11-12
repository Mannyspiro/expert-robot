"""Seeded, bounded benchmark harness for Merlin CPU fabric."""
import json, random, time
from .kernels import tiled_matmul

def run_suite(size=48, tile=16, seed=17):
    if not 8 <= size <= 192 or not 1 <= tile <= 96:
        raise ValueError("benchmark dimensions exceed safe bounds")
    rng=random.Random(seed)
    a=[[rng.random() for _ in range(size)] for _ in range(size)]
    b=[[rng.random() for _ in range(size)] for _ in range(size)]
    start=time.perf_counter(); c=tiled_matmul(a,b,tile); elapsed=time.perf_counter()-start
    observed=sum(sum(row) for row in c)
    expected=sum(a[i][k]*b[k][j] for i in range(size) for k in range(size) for j in range(size))
    error=abs(observed-expected)
    return {"schema_version":"1.0","workload":"dense_f64_tiled_matmul","size":size,
      "tile":tile,"seed":seed,"elapsed_seconds":elapsed,"flops_estimate":2*size**3,
      "gflops_estimate":(2*size**3/elapsed/1e9) if elapsed else None,
      "checksum":observed,"reference_checksum":expected,"absolute_error":error,
      "verified":error <= max(1e-8,abs(expected)*1e-12)}

if __name__ == "__main__": print(json.dumps(run_suite(),indent=2))
