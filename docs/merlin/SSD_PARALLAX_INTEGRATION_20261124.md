# Combining SSD offloading with Parallax

## Implemented component

`python/merlin/ssd_parallax_reference.py` implements the actual mathematical
Parallax attention correction for one query, one head and its full visible KV
snapshot. It provides a resident comparison path and a file-backed path that
loads a bounded block at a time. Both correction branches consume the same
records; the reader does not scan KV twice for the two branches.

This is executable FP64 CPU code with generated tensor fixtures. It does not
replace a model's attention weights, supply the learned probe projection, run
the upstream optimized kernel, or install an inference provider. The older
scalar local-linear sketch and Mamba research remain separate historical work.

The fixed protocol is [SSD_PARALLAX_EXPERIMENT_PROTOCOL_20261124.md](SSD_PARALLAX_EXPERIMENT_PROTOCOL_20261124.md).
Exact final-source receipts are emitted by the existing offline CI, together with
a bounded Merlin `ResearchSubloops` evidence-review checkpoint.

## What the combination means

There are three distinct resources:

| Resource | Role | Effect of offloading |
| --- | --- | --- |
| Model weights and learned projections | Define the trained computation | A qualified engine can stream selected weights from SSD into a smaller working cache. |
| Attention KV history | Supplies the context for a new query | The new operator reads a file snapshot through a bounded buffer. It still visits the full visible history. |
| CPU/GPU arithmetic | Calculates projections, attention and other model layers | Real processors still execute the work. Storage capacity does not supply compute throughput. |

Weights and KV should reside on storage beside the compute host. A network client
can send requests and receive outputs without moving the complete model or every
intermediate tensor across Wi-Fi. There is no measured Wi-Fi or GPU path in this
component build.

## Relation to WiCi and InferSSD

The likely product in the user's request is [WiCi](https://wici.ai/technology).
Its published architecture uses a real GPU computer on the network. The driver
and SDK descriptions are preview interfaces; no reusable wireless-driver
implementation was verified here. The application-level API is the relevant
integration boundary for Merlin.

The inspected InferSSD release is
[`261122.341`](https://github.com/wici-ai/inferssd/releases/tag/261122.341), commit
`4cb86d291ae7a4ac494489f1b3f071e3bfce9942`. It supports selected MoE expert
offloading and dense-layer streaming. The development source additionally inspected
was `76515a50a90ba9611d72f657f5f848403f14e518`.

That later development source contains `kv.spill_directory`; the release's exact
configuration does not. The development feature requires an existing local
directory, a supported growable attention cache, one sequence, sufficient storage
and device staging capacity. Dense decode may reread the active cache per token.
Do not describe it as a qualified multi-user service or a feature of the older
release. See the pinned
[configuration](https://github.com/wici-ai/inferssd/blob/76515a50a90ba9611d72f657f5f848403f14e518/docs/configuration.md)
and [release configuration](https://github.com/wici-ai/inferssd/blob/4cb86d291ae7a4ac494489f1b3f071e3bfce9942/docs/configuration.md).

Merlin Studio already has a loopback OpenAI-compatible provider in
`portable/merlin_studio/model.py`. A separately installed and qualified InferSSD
server could use that boundary. Current Studio requests are non-streaming and
the client rejects LAN/Wi-Fi endpoint addresses. The existing bundled llama.cpp
launcher is not interchangeable with InferSSD's launch contract. No endpoint
permission, provider launch or installed runtime was changed here.

InferSSD's quickstart says its non-loopback API is unauthenticated. Any future
remote access therefore needs the project's reviewed authenticated ingress;
this work does not expose a service. InferSSD additions are Apache-2.0 with
component notices, and models retain their publisher licenses. No InferSSD code
or weights are bundled by this change.

## Mathematical implementation

For one query, let `s_i = scale * q dot k_i`, `t_i = r dot k_i`, and let `p_i`
be the normalized exponential weights of `s_i`. The implemented expression is:

`output = E_p[V] - Cov_p(t, V)`.

The file path maintains the unnormalized denominator, probe moment, value moment
and probe/value moment. When its running logit maximum changes, it rescales all
four accumulators. The signed probe branch is not multiplied by QK scale.
Subtracting the first key and value before accumulation uses exact translation
identities and reduces large common-offset cancellation. Finite-precision
cancellation can still occur outside the tested domain; overflowing arithmetic
is refused. Values can legitimately leave the convex hull of the input values.

The official source is Yifei Zuo et al., *Parallax: Parameterized Local Linear
Attention for Language Modeling*, [arXiv:2605.29157v1](https://arxiv.org/abs/2605.29157v1),
with `parallax/reference.py` at
`987102538da4c831a0b6f2dde03ce3251182a7cf`. Its MIT attribution is retained in
`third_party/parallax/`. This implementation permits a separate value dimension,
the same mathematical operation's rectangular-value generalization. It has no
GQA, training/backward kernel, sliding window, batched query or mutable append API.

## Storage contract

- A fixed 56-byte header binds format version, row count, key/value dimensions
  and payload SHA-256. Rows store little-endian FP64 keys followed by values.
- The caller supplies a separate whole-file SHA-256. An embedded checksum alone
  is not an authenticated expected identity.
- Writer publication is atomic and refuses overwrite. Its temporary file has
  private permissions and is made owner-read-only after syncing. This does not
  promise crash-durable directory-entry persistence.
- The reader opens one regular-file descriptor, rejects final symlinks/special
  files, checks shape/length before allocation, and hashes exactly the payload
  it uses. The final file-state and both hashes must pass before an output returns.
- Configured limits are 65,536 rows, dimensions 1–128, a 128 MiB payload cap and
  a read buffer between 56 bytes and 8 MiB. A block larger than its configured
  budget is refused. These bounds do not make the process a filesystem sandbox.

For `N` records, key dimension `d_k` and value dimension `d_v`, payload size is
`N * (d_k + d_v) * 8` bytes. A block contains
`block_records * (d_k + d_v) * 8` raw bytes, plus bounded arithmetic state and
Python overhead. One arbitrary query still costs an `O(N)` full-context scan.
The cache's capacity and the speed of that scan are separate properties.

## Running the component

From the repository root, the full fixed experiment is:

```sh
python3 -B scripts/merlin_ssd_parallax_benchmark.py --output /tmp/merlin-ssd-parallax-new.json
```

The output path must be new. There are no third-party runtime dependencies,
downloads, remote calls or model calls in this benchmark. For API use:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from merlin.ssd_parallax_reference import write_kv_store, parallax_attention_file

with TemporaryDirectory() as directory:
    path = Path(directory) / "context.kv"
    identity = write_kv_store(path, [[1.0, 0.0], [0.0, 1.0]],
                             [[0.2, 0.7], [0.9, -0.1]])
    result = parallax_attention_file(
        path, [0.3, -0.5], [0.1, 0.2],
        expected_sha256=identity["sha256"], block_records=1,
        max_buffer_bytes=64,
    )
    print(result["output"], result["io"])
```

Set `PYTHONPATH=python` when using this import directly from the checkout.

## Evidence and repaired defects

Thirty tests cover an independent 70-digit Decimal covariance oracle, softmax
and translation identities, signed probe behavior, different block partitions,
large logits, invalid dimensions/numbers, corruption, file mutation, regular-file
requirements, no-overwrite behavior, read budgets and evidence provenance.

Independent review found a header-accounting error: a 16-byte configured buffer
could previously read a 56-byte header. The implementation now enforces the
header minimum before opening the file and includes it in the reported peak.
The benchmark also now times resident load-plus-compute, records generation,
checks source identity before and after measurement, and preserves old reports.

The preliminary report is retained under `evidence/20261124-ssd-parallax-initial.json`.
It predates those repairs and had an unbound commit; it is not the final acceptance
receipt. The final offline workflow reruns the fixed protocol on its exact source.
Read the actual checkout SHA and tree, not only the pull-request head label.

`tracemalloc` measures new Python allocations during an operation. The resident
fixture remains live while streamed trials run, so these peaks do not measure
total process RAM saved. Files were just written and warmed; no physical SSD,
cold-cache, VRAM, network or trained-model performance is established. Timing is
descriptive, and the resident expression allocates different working objects
from the online implementation.

Merlin's native `merlin_research_browser.retrieve` was attempted with a 1 MB and
8-second bound per source. All three attempts failed DNS resolution. Connected
web/GitHub retrieval supplied the source review; the failed native attempts remain
in the appended source ledger. No fixed OCI metadata operation was repurposed.

## Remaining production acceptance

1. Bind a compatible licensed model, learned Parallax projection, engine commit
   and device backend. Existing Qwen GGUF weights are not Parallax weights.
2. Add and verify the actual model-engine attention adapter; this Python component
   is not automatically selected by an InferSSD or llama.cpp setting.
3. Run the declared model-level baseline/SSD/Parallax/combined comparison with
   equivalent tasks and quality checks. An unavailable arm stays unavailable.
4. Measure target-device cold bytes/token, memory, latency, thermal behavior and
   failures. For measured useful bandwidth `R` and required cold bytes/token `B`,
   `R/B` is only an I/O ceiling; compute and other transfers can lower it.
5. Qualify provider lifecycle, recovery, authentication and multi-user resource
   accounting on the real deployment profile before enabling that provider.

No global production-completion percentage, physical acceleration, model-quality
gain or deployment qualification is inferred from this component result.
