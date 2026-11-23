# Merlin optional AirLLM and OpenBot reuse (2026-11-22)

Status: SOURCE-PINNED, OPT-IN DEVELOPMENT CANDIDATE. Not a production release.
Based on the Merlin Studio PR #194 branch. The existing Studio inference
adapter, canonical ArtifactRef storage and approval gates remain unchanged.

## Exact source inputs

| Source | Pinned commit | License | Integration |
| --- | --- | --- | --- |
| [AirLLM](https://github.com/lyogavin/airllm) | 7e2e8cfe2810dc0559461504f6ba5c0ece960ba8 | Apache-2.0 | Optional local model sidecar |
| [OpenBot](https://github.com/pmwasim/OpenBot) | 019b4c65f488af06ce1a1cfb741cd825129a4c1a | MIT | Optional local-first agent dashboard |

The .gitmodules file contains full public upstream URLs and Git submodule
gitlinks pin the source trees. The component manifest at
config/merlin/third-party-sources.json records their original identity and
license. A distinct CopilotKit/OpenBot MIT application was reviewed but not
vendored: full deployment depends on separately licensed Intelligence services.
Do not confuse the two projects, and do not confuse source access with
qualification or a dependency audit.

## Retrieve the full pinned source

From the integration branch on a network-connected machine, run:

    git submodule update --init third_party/airllm third_party/openbot
    python3 scripts/merlin/verify_third_party_sources.py

This downloads the source at the exact recorded commits. The verifier checks
Git HEAD, modified tracked files, submodule URLs and license notices.
Preserve the upstream license and NOTICE requirements when distributing code;
model weights and model/checkpoint licenses are separate.

The development container could not download Git repositories because GitHub
DNS is unavailable. The new CI workflow performs checkout and verification
on the connected CI runner. Before CI completes, do not claim source checkout
or OpenBot native tests have been executed.

## AirLLM backend (opt in)

Use a dedicated environment; dependencies and model code must be reviewed.

    python3 -m venv .venv-airllm
    . .venv-airllm/bin/activate
    python -m pip install ./third_party/airllm/air_llm
    python portable/merlin_studio/airllm_sidecar.py --model-path /absolute/local/trusted/model --port 8772

The local model directory must already contain config.json. The adapter
does not download models, exposes only /v1/models and /v1/chat/completions
on loopback, enforces bounded text inputs and token budgets, and does
not synthesize native tool calls. It serializes inference. It does NOT
provide hard cancellation of a hung model generation process.

Run Merlin Studio separately and configure its existing Settings panel:

    python3 portable/merlin_studio/server.py --port 8771
    model URL: http://127.0.0.1:8772/v1/chat/completions
    model ID: merlin-airllm

The optional read_only_json compatibility mode only interprets a tightly
limited text envelope for read-only tools. Tool execution and any approval
remain Studio's responsibility. Do not run two servers on port 8772.
Large models may require significant disk and be slower due to I/O even when
their peak GPU VRAM is lower. Actual target-host benchmark is missing.

## OpenBot companion (opt in)

Requires Node.js 20+, the pinned source checkout, and a compatible model
already listening on local port 8772. The launcher does not install Node,
download models or start Merlin itself.

    python3 scripts/merlin/run_openbot_companion.py --dry-run
    python3 scripts/merlin/run_openbot_companion.py --model-port 8772 --port 4178

The OpenBot dashboard appears at http://127.0.0.1:4178. Studio remains at
http://127.0.0.1:8771/studio/. OpenBot uses its own local state directory
(.local-merlin/openbot), policies and approvals. The launcher explicitly
pins loopback bindings, disables remote provider settings and sets a limited
resource profile. OpenBot and Studio are NOT the same agent, do not share
their registry, and do not confer authorization on one another. The
OpenBot process is not by itself an OS sandbox.

## Verification and production gates

Focused fixture tests are in tests/test_airllm_openbot_integration.py.
They check fake-model completion, token slicing, HTTP framing, bad requests,
loopback Host controls, fail-closed source verification and separate
OpenBot configuration. A five-test draft subset passed locally; the extended
tests and upstream OpenBot check await CI confirmation.

Run local protocol tests (no GPU or model weights necessary):

    python3 -m unittest discover -s tests -p test_airllm_openbot_integration.py -v
    python3 -m py_compile portable/merlin_studio/airllm_sidecar.py

The dedicated GitHub Actions CI workflow also clones pinned source and
runs the OpenBot upstream test harness with read-only repository permissions.
CI tests are not actual AirLLM inference or Merlin production deployment.

Ranked next independent acceptance checks:
1. Inspect CI results, source commits and license notices.
2. Run real-model inference and verify an independent reference answer.
3. Compare AirLLM with llama.cpp on the same model, host and workload using
   peak VRAM/RSS, throughput, wall-time, disk bytes and quality measurements.
4. Exercise model-selected tools, cancellation, restart, Studio UI and
   OpenBot agent work while preserving source/approval boundaries.
5. Reconcile original PR #194 and release/plan gates before any merge.

## Skeptical-scientist decision frame

- Observed: interface/wire-level and false-request fixture success. Models
  and upstream code not executed locally.
- Hypothesis: AirLLM can lower memory enough to use otherwise unavailable
  local models on the target computer.
- Alternative: disk and serialization overhead make latency unacceptable.
- Falsifier: measurements against the existing backend show no usable
  memory/throughput/quality advantage at the target load.
- N-ality applied: keep integrity, correctness, compute, authority, and
  deployment as distinct axes.
- Simplex and continuum deferred until resources have calibrated samples.
- Fuzzy authorization not applicable: licenses, source pins, approvals and
  release qualification remain strict Boolean gates.
