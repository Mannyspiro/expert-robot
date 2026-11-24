# Merlin Parallax CPU disk profile

This profile runs the author's trained **YifeiZuo/Parallax-0.6B** checkpoint with
its learned R projections intact. Accelerate restores one module's weights from
the original BF16 safetensors file into FP32 CPU memory when that module runs,
then returns its parameters to `meta`. The direct loader starts from empty
parameters; it does not first construct a fully resident model and does not
create duplicate `.dat` weight files.

The executable path is a bounded, offline, plain-text continuation CLI. It is
an experimental model profile, separate from Merlin Studio's Qwen
assistant provider. It has no service listener, tool execution or chat-quality
qualification. KV cache and activations remain in RAM. Disk supplies model
storage; the CPU still performs all arithmetic.

## Fixed inputs

| Component | Exact input |
|---|---|
| Author checkpoint | `YifeiZuo/Parallax-0.6B` |
| Revision | `0cf73e2d49ea1a09a9ef85178b73ad68e019ae36` |
| Original weight file | 1,309,592,289 bytes; SHA-256 `2049f3dec8156649f1a3e2deed4decbe649cf0d7a8a9f9273453cbfa13aed2cf` |
| Runtime | CPython 3.11.18, Linux x86_64 GNU, standalone build 20261110 |
| CPU engine | Torch `2.9.1+cpu`, Transformers `5.6.2`, Accelerate `1.16.0` |
| Tokenizer | Tokenizers `0.22.2`, exact raw author `tokenizer.json` |
| Numerical mode | CPU FP32, eager attention, two Torch threads, one interop thread |
| CLI bounds | 4,096 UTF-8 prompt bytes, at most 64 prompt tokens and 16 new tokens |

All 50 original payloads are fixed by full byte count and SHA-256: one runtime
archive, 39 wheels and ten checkpoint/tokenizer files. Their total size is
1,612,635,334 bytes. Installation also needs space for the extracted runtime and
wheel contents. A complete offline ZIP adds another copy of the original
payloads while that ZIP is retained. The program currently supports Linux
x86_64 only. Bootstrap setup needs Python 3.10 or newer with its standard
library; model execution then uses the supplied CPython 3.11 runtime.
That bootstrap can be an existing Python installation or the independently
bundled and verified Merlin Studio Python runtime. Replace `python3` in the
setup command with that runtime's explicit executable path if needed; no
second network install is required.

## Use the assembled offline kit

Extract the reviewed `Merlin_Parallax_CPU` directory and open a terminal there.
Create a **new** local installation directory:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 \
  python3 -B profile/setup_cpu_candidate.py \
  --payload-root "$PWD/payloads" --destination "$PWD/installed"
```

Setup hashes every complete original payload before executing the supplied
interpreter or installing any wheel. It verifies the runtime archive, preserves
source and license notices, excludes the four declared bytecode cache files,
and installs the exact 39-wheel closure using offline pip with required hashes.
It writes a setup receipt and five explicit logs. It does not run the model.

Run a short continuation into a **new** result directory:

```bash
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  HOME="$PWD/installed/home" TMPDIR="$PWD/installed/tmp" \
  HF_HOME="$PWD/installed/hf-home" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
  HF_HUB_DISABLE_XET=1 TOKENIZERS_PARALLELISM=false CUDA_VISIBLE_DEVICES= \
  OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  "$PWD/installed/venv/bin/python" -B profile/parallax_disk_generate.py \
  --base "$PWD/payloads" --output "$PWD/answer-001" \
  --prompt 'The capital of France is' --max-new-tokens 4
```

The command writes `answer-001/receipt.json`, including the generated tokens,
text, actual weight/index hashes and post-forward parameter state. The raw
author tokenizer is loaded directly; no AutoTokenizer family heuristic or
regex replacement is applied. The loader imports only the two locally
verified author Python files. It does not request remote model code.

## Acquire the exact inputs from source

Network access is needed only for this acquisition step. From a checkout,
choose a new private payload directory and copy the three locks into it:

```bash
profile="$PWD/scripts/merlin/parallax_cpu_disk"
payloads="$PWD/parallax-payloads"
mkdir -m 700 "$payloads"
cp "$profile/"{runtime,wheel,checkpoint}-lock.json "$payloads/"
for kind in runtime wheel checkpoint; do
  python3 -B "$profile/acquire_locked.py" \
    --lock "$payloads/$kind-lock.json" --root "$payloads" \
    --receipt "$payloads/$kind-acquisition.json"
done
python3 -B "$profile/setup_cpu_candidate.py" \
  --payload-root "$payloads" --destination "$PWD/parallax-install"
```

Acquisition accepts fixed public HTTPS hosts, validates redirects and complete
payload bytes, publishes without replacing an existing file, and refuses a
corrupt cached payload. It never imports the acquired code. Failed partial
downloads remain available for diagnosis. Run each receipt path only once.

## Reproduce the fixed acceptance

```bash
python3 -B scripts/merlin/parallax_cpu_disk/run_replay.py \
  --python "$PWD/parallax-install/venv/bin/python" \
  --base "$PWD/parallax-payloads" --output "$PWD/parallax-replay"
```

`run_replay.py` verifies the frozen source hashes and launches four sequential,
separate subprocesses under an explicitly constructed offline environment:

1. A resident FP32 reference: one five-token prefill and three cached decode
   steps, plus a separate R-zero control.
2. A fresh direct-file loader using the same prompt, source, precision and
   teacher-forced resident continuation. Every full logit is checked at
   `atol=1e-5`, `rtol=1e-5`, and the actual greedy tokens must also match.
3. The bounded generation CLI, checked against both the fixed token oracle and
   the actual resident sequence.
4. An oversized-token request that must fail before an offload index is made.

All 56 R/Rnorm tensors are compared with their source values in the resident
reference. Zeroing the 28 Rnorm outputs must change the prefill output. Direct
execution observes all 56 R modules restored on CPU in each of four forwards,
all 367 parameter paths restored to `meta` afterward, and all 28 K/V layers
with the expected CPU FP32 finite values, shapes and sequence lengths.

The current frozen direct protocol is `direct-protocol-recovery2.json`, SHA-256
`ea1af729e1c8c602e8bf817d03d7cc9be0494bed973df23a0ce71dad3e65803d`.
The generation protocol is `generation-protocol-recovery2.json`, SHA-256
`5c48b2972ebd0d0e30e88f1bba2a53d5a52463b692407b6a41335a8fa36ecf16`.
Earlier recovery1 protocols are retained as provenance; current corrected
source intentionally no longer satisfies their older source hashes.

The fresh recovery2 replay passed and was independently checked from actual
saved arrays. All 1,215,488 logits were finite and bitwise equal. The greedy
sequence was `[12095, 11, 323, 279]`, decoded as ` Paris, and the`. Zeroing Rnorm
changed a logit by a maximum of 12.764103889465332. This establishes execution
of the learned attention path and resident/disk numerical equivalence for
this fixed short input; it does not establish broader model quality.

Observed full-process peak RSS was 4,293,300,224 bytes for the resident process
and 1,445,707,776 bytes for the direct process. The resident also ran the R-zero
control, while the direct process retained comparison arrays. These are
descriptive process measurements with warmed files; they are not equal-workload
speed, total-system RAM or cold-storage measurements. The 91,524-byte index in
this replay contained 367 entries referencing the original weight file. Index
size varies with the absolute local path. The tied output head points to the
same source embedding tensor. No `.dat` weight files were created.

## Build a complete offline ZIP

After committing the reviewed profile and using a clean checkout:

```bash
python3 -B scripts/merlin/parallax_cpu_disk/assemble_offline_kit.py \
  --payload-root "$PWD/parallax-payloads" \
  --source-commit "$(git rev-parse HEAD)" \
  --output "$PWD/Merlin_Parallax_CPU.zip"
```

The assembler binds the exact source commit/tree, collects only tracked
regular profile files, includes all 50 original payloads and the three locks,
hashes every byte as it copies, then rereads and hashes every written ZIP
member. It publishes without overwriting another kit and writes an outer ZIP
receipt. It includes neither the installed venv nor experiment output. Root
project publication owns the final artifact and its external checksum.

## Source, licenses and remaining scope

The author checkpoint card declares Apache 2.0. `notices/author/` retains the
exact card, config and both reviewed author source files plus the standard
Apache license text. `notices/inventory.json` binds the original wheel bytes,
declared license metadata and extracted license notices for all 39 distributions.
Standalone contributor contact lists are not copied into this source package;
the locked upstream wheels retain their original files unchanged.
The Tokenizers wheel lacks a physical license file; its pinned upstream
license is supplied and its exact source commit is recorded in that inventory.
The original runtime archive retains its bundled notices. This collection
records supplied terms; it is not a complete legal or dependency-source audit.

The complete 13,484 bytes of author configuration/model code were read. They
contain the attention math and Qwen3-derived module construction, with no
subprocess, shell, file-download or dynamic evaluation routine. Imports rely
on the pinned Torch/Transformers closure. Their pure-Torch attention kernel
uses learned R, Q/K normalization, rotary embeddings and ordinary K/V cache.
Eager attention and unpadded inputs are deliberate constraints: the adapter
expects an additive mask and forms quadratic prefill score tensors. This
profile caps context well below the checkpoint's declared 4,096-token limit.

The separate Merlin FP64 file-backed K/V research operator is not inserted
into this full trained model. This executable profile offloads **weights**;
integrating bounded disk K/V, longer contexts, multi-sequence serving, model
quality qualification and packaging for other operating systems remain
separate acceptance work.

Primary sources: [pinned checkpoint](https://huggingface.co/YifeiZuo/Parallax-0.6B/tree/0cf73e2d49ea1a09a9ef85178b73ad68e019ae36),
[Parallax paper](https://arxiv.org/abs/2605.29157),
[author attention repository](https://github.com/Yifei-Zuo/Parallax/tree/987102538da4c831a0b6f2dde03ce3251182a7cf),
[Accelerate offload implementation](https://github.com/huggingface/accelerate/blob/f938aab2a89a8822101937446057211b8059527b/src/accelerate/utils/offload.py),
[Accelerate dispatch implementation](https://github.com/huggingface/accelerate/blob/f938aab2a89a8822101937446057211b8059527b/src/accelerate/big_modeling.py).
