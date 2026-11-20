# Pinned NASA refine: local serial unit-square study

Research execution completed on 2026-11-18. Source: [nasa/refine at 1563f71f224d59c8712e2181369ff93440957b0f](https://github.com/nasa/refine/tree/1563f71f224d59c8712e2181369ff93440957b0f), Apache-2.0. This is the generic 2D mesh-adaptation tool, with no aircraft, vehicle or mission operation involved.

All **698 tracked source blobs** in the extracted archive matched the complete NASA Git-tree response at that commit. No missing, changed or extra files were found. The archive SHA-256 is:

`d96a133756331b2c57cbb22718a383decce8361b3602dad2376f540ce79fabcf`

The source was not edited. A separate serial Release build used project-only CMake 3.31.6 and GNU C/C++ 14.2.0. Optional MPI, CAD/geometry, partitioning and meshlink packages were disabled. No system installation or production dependency change occurred. The upstream unit/acceptance suite was disabled and is **not** claimed to pass.

## Actual first native result

| Item | Observed value |
|---|---|
| Input | Synthetic 8×8 unit-square grid: 81 vertices, 128 triangles, 32 boundary edges |
| Coordinates | [0,1]×[0,1], z=0; metres declared in the protocol, not encoded by the mesh file |
| Metric | hx=0.08/(1+7 exp(-((x−0.5)/0.12)²)), hy=0.08; diagonal metric (hx⁻², hy⁻²) |
| Selection | First native output retained; no tuning against held-out point locations |
| Native invocation | ref adapt input-bamg.msh -m metric.sol -x adapted.msh2 -s 12 |
| Bounds | One serial process; 30 s wall timeout, 25 s CPU, 512 MiB address space |
| Exit / wall time | 0 / 0.6167 s, one local observation |
| Output | 541 vertices, 986 triangles; native Gmsh 2.2 ASCII |
| Output SHA-256 | 34024df2a46e63dccce694cedcfa8b8a58b53292812536eaabda0ab6ece4e33a |
| Executable SHA-256 | 927d52dba1ebebb2dd1a0c04e47d03401f8f80c87618b55337262cb925ba231a |

The native file is `weave-ops/refine-study/run/adapted.msh2`. `$Nodes` rows contain 1-based ID, x, y and z. `$Elements` uses type 1 for boundary edges and type 2 for triangles, with tags and 1-based node IDs. No post-export coordinate or connectivity changes were applied. The independent evaluator handles the clockwise orientation convention explicitly before barycentric checks; its normalized evaluation copy is distinct from the preserved native output.

The pinned BAMG exporter writes x,z, whereas this 2D input uses x,y. The study therefore uses the native **Gmsh 2.2 exporter** rather than silently altering exported coordinates or patching upstream. A plain `.mesh` output suffix is not accepted by this source's extension dispatcher. `-bamg.msh` selects the BAMG exporter; `.msh2` selects Gmsh 2.2.

The full native receipt is `docs/evidence/refine-native-build-20261118.json`. It binds source verification, build flags, binary, input, metric, output, protocol and log hashes. Local raw evidence remains under `weave-ops/refine-study/`. Interpolation/geometry acceptance is recorded separately by the independent evaluator; a native exit code is not that acceptance result.

## Rebuild in an isolated project directory

Begin with the exact extracted source archive above. From the workspace containing `weave-ops/refine-study`, the following are the build commands used. The optional build tool is installed only into the study directory:

```sh
python -m pip install --only-binary=:all: --no-deps --no-compile --target weave-ops/refine-study/tools cmake==3.31.6

weave-ops/refine-study/tools/cmake/data/bin/cmake \
  -S weave-ops/refine-study/refine-1563f71f224d59c8712e2181369ff93440957b0f \
  -B weave-ops/refine-study/build \
  -DCMAKE_BUILD_TYPE=Release -Drefine_ENABLE_TESTS=OFF \
  -DENABLE_MPI=OFF -DENABLE_EGADS=OFF -DENABLE_OpenCASCADE=OFF \
  -DENABLE_ParMETIS=OFF -DENABLE_Zoltan=OFF -DENABLE_meshlink=OFF

weave-ops/refine-study/tools/cmake/data/bin/cmake \
  --build weave-ops/refine-study/build --target ref -j 2
```

No `install` build target is needed. Upstream CMake labels a non-git archive as version 3.0.0; that guessed display label is not a replacement for the exact source commit. The build emitted a CMake compatibility deprecation warning and completed without changing compiler-warning policy.

## Reproduce the fixed native input and command

This standalone Python command creates a **new** run directory, writes fixed ASCII input and metric data, then runs only the built serial executable. It does not fetch software, use solver data, or inspect evaluator point coordinates:

```sh
python - <<'PY'
from pathlib import Path
import math
import resource
import subprocess

base = Path('weave-ops/refine-study').resolve()
run = base / 'run-reproduction'
run.mkdir(mode=0o700)  # Refuse an existing directory.
n = 8
vertices = [(i/n, j/n) for j in range(n+1) for i in range(n+1)]
node = lambda i, j: j*(n+1)+i+1
triangles = []
for j in range(n):
    for i in range(n):
        a, b = node(i, j), node(i+1, j)
        c, d = node(i, j+1), node(i+1, j+1)
        triangles.extend([(a, b, d, 1), (a, d, c, 1)])
edges = [(node(i, 0), node(i+1, 0), 1) for i in range(n)]
edges += [(node(n, j), node(n, j+1), 2) for j in range(n)]
edges += [(node(i, n), node(i-1, n), 3) for i in range(n, 0, -1)]
edges += [(node(0, j), node(0, j-1), 4) for j in range(n, 0, -1)]
lines = ['MeshVersionFormatted 0', 'Dimension 2', 'Vertices', str(len(vertices))]
lines += ['%.17g %.17g 1' % v for v in vertices]
lines += ['Edges', str(len(edges))] + ['%d %d %d' % e for e in edges]
lines += ['Triangles', str(len(triangles))]
lines += ['%d %d %d %d' % t for t in triangles] + ['End']
(run / 'input-bamg.msh').write_text('\n'.join(lines) + '\n')
lines = ['MeshVersionFormatted 2', 'Dimension 2', 'SolAtVertices', str(len(vertices)), '1 3']
for x, y in vertices:
    hx = .08 / (1 + 7*math.exp(-((x-.5)/.12)**2))
    hy = .08
    lines.append('%.17g 0 %.17g' % (1/hx**2, 1/hy**2))
(run / 'metric.sol').write_text('\n'.join(lines + ['End']) + '\n')
def bounds():
    resource.setrlimit(resource.RLIMIT_AS, (536870912, 536870912))
    resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
command = [str(base / 'build/src/ref'), 'adapt', 'input-bamg.msh',
           '-m', 'metric.sol', '-x', 'adapted.msh2', '-s', '12']
with (run / 'adapt.log').open('wb') as log:
    result = subprocess.run(command, cwd=run, stdout=log,
                            stderr=subprocess.STDOUT, timeout=30,
                            preexec_fn=bounds)
if result.returncode:
    raise SystemExit(result.returncode)
print(run / 'adapted.msh2')
PY
```

The original input SHA-256 is `5a16d26d228318f9735d4dcd1fdf18afde1ec8195b4e1dc9ddba301e2be4529e`; the original metric SHA-256 is `8eaf45623f299f2a0a185a9477be9bce7220bef45cdadd255e9031e4a2e27ba9`. Confirm those before comparing a reproduction with the preserved first output. Exact native output bytes can depend on the build/platform; geometry and scientific acceptance must also be checked, not inferred from a filename.

## Scientific and integration limits

The metric is informed by the predeclared narrow-x manufactured field; this is not a blind design-discovery claim. Its performance against an equal-vertex uniform control is evaluated on separately frozen points. Keep the first result, including a negative comparison. The 10,000-vertex/20,000-triangle ceiling is an output acceptance bound, not a native allocation counter.

This study does not test a FreeCAD/STEP solid roundtrip, CAD associations, manufacturing suitability, a PDE solver, physical measurements, parallel execution or independent CACE verification. CPU/address-space/time bounds are not a qualified security sandbox. Any optional geometry or partition library would need a separately reviewed build and license profile.

Use the existing Merlin registry and engineering evidence links if the result is ingested. No second mesh/provenance database, automatic repair, promotion or deployment is introduced.
