# Actual Parallax CPU disk model: recovery and acceptance

Parent: [SSD and Parallax integration](SSD_PARALLAX_INTEGRATION_20261124.md).
Executable profile: [source and instructions](../../scripts/merlin/parallax_cpu_disk/README.md).

## Delivered scope

The pinned author checkpoint `YifeiZuo/Parallax-0.6B` at
`0cf73e2d49ea1a09a9ef85178b73ad68e019ae36` now has an executable bounded CPU
weight-offload path. It retains all learned R tensors, initializes empty
parameters, and uses Accelerate's direct-safetensors index to restore each
module's BF16 source weights as FP32 CPU values during execution. This advances
the parent plan's trained-checkpoint integration requirement. It does not
replace Studio's native Qwen assistant or integrate the separate FP64 K/V
snapshot operator into the trained model.

## Evidence recovery boundary

A workspace rollback removed an earlier unpushed candidate and its receipts.
Those missing receipts were not recreated from summaries. The downloader,
runtime lock and checkpoint lock were recovered byte-exactly. The offline
installer was recovered, then its wheel-lock constant was updated to a newly
recovered lock with the same 39 exact distribution versions and byte sizes.
The unavailable old pip-resolution-report hash was not invented. New wheel
hashes and URLs were checked against the exact public distribution metadata
and actual downloaded bytes. Model support/direct loader/probes were
reconstructed as new source and received new frozen protocols and real runs.

All 50 payloads were freshly acquired and hashed. The actual offline setup
used source SHA-256
`89abe174a99ed0c4bba9fbea06e542f7d36d318226b96641d97169fa93d819e3`
and produced setup receipt
`e9c19c2c4f94faed0701891da72faa4d09163f964c8129ac902849a6126cf5d2`.
The runtime inventory preserves 3,896 files and 1,049 contained symlinks, with
only four source-archive bytecode cache files excluded. Offline installation,
pip consistency and actual CPU import checks passed. The installer receipt
binds the five retained setup logs.

Recovery1 passed the fixed numerical experiment. Independent review found a
reusable-helper path-binding gap: a caller could ask to import a sibling
checkpoint directory after the canonical directory's files had been hashed.
The actual canonical-path runs were valid. Recovery1 source and evidence were
preserved, and recovery2 added a canonical nonsymlink checkpoint-directory
guard and an exact 367-parameter-path check. Twelve focused boundary tests
passed. Numerical settings, prompt, trained weights and tolerances did not
change. Recovery2 was frozen before its fresh model runs.

## Recovery2 actual result

| Check | Actual result |
|---|---|
| Inputs | Five-token unpadded prompt `The capital of France is`; one prefill and three cached decode steps |
| Precision and attention | CPU FP32, explicit eager attention, two Torch threads |
| Full logits | 1,215,488 finite elements; resident/direct bitwise equality; maximum absolute error 0 |
| Declared acceptance tolerance | `atol=1e-5`, `rtol=1e-5`; exact greedy sequence also required |
| Greedy sequence and CLI | `[12095, 11, 323, 279]`; ` Paris, and the` |
| Learned R loading | All 56 R/Rnorm tensors exact source-to-FP32 matches, finite and nonzero |
| R use control | 28 Rnorm-zero hooks; maximum prefill logit change 12.764103889465332 |
| Direct execution | All 56 R modules observed on CPU four times; all 367 parameter paths meta after every forward |
| Cache | All 28 layers CPU FP32 finite, shapes `[1,8,L,128]`, lengths 5,6,7,8 |
| Disk index | 91,524 bytes in this location, 367 mappings, only output-head/embedding alias; zero `.dat` copies |
| Bound negative | More than 64 prompt tokens rejected before index creation |

Full-process peak RSS was 4,293,300,224 bytes resident and 1,445,707,776 bytes
direct. A launch receipt records four real distinct PIDs, sequential launch
times, the constructed environment, exit codes `0,0,0,1`, and output/log
hashes. The resident additionally ran the R-zero control; the direct retained
reference arrays. These process measurements are descriptive and use warmed
files. They do not measure equal-workload speed, physical SSD performance,
cold-cache behavior or total-system RAM.

## Exact retained identities

| Artifact | SHA-256 |
|---|---|
| Direct recovery2 protocol | `ea1af729e1c8c602e8bf817d03d7cc9be0494bed973df23a0ce71dad3e65803d` |
| Generation recovery2 protocol | `5c48b2972ebd0d0e30e88f1bba2a53d5a52463b692407b6a41335a8fa36ecf16` |
| Separate-process launch receipt | `21477fd4fa930ff3b9d0ceb4430d360832c2a5aef603fffdb8f6062ae45ac90d` |
| Resident receipt | `03dc41ca7fae2fea3a179d977384057cb4eefa059f2dca32ec01e521ef3bc456` |
| Direct receipt | `ef0823cd7fb1c1dd4144fad04d42b2d7b206b56701312d4a668e12112fb1d4c0` |
| CLI receipt | `d5d7d18b4b652003709ef2b0bb7d014d0e301290c01ea1c73463c92f98487fae` |
| Independent recovery2 review | `27e3af76eefb7cc16cac2dacf456ed23c7199fd760947004a4c83c91e42ea051` |

Actual evidence is retained under `parallax-recovery-evidence/replay2/`, with
frozen source under `parallax-recovery-evidence/recovery2-sources/`. Independent
review is under `parallax-recovery-independent-review/`. These are new replay
artifacts, separate from lost historical evidence. The root publisher owns
their final durable package and exact source publication.

## Reproducibility and remaining gates

The new standard Ubuntu 24.04 workflow checks out the exact PR head with
read-only repository permissions and no persisted credentials. It acquires
the fixed 50 payloads, creates a fresh offline installation and repeats the
resident/direct/CLI/bound negative protocol. Its always-retained artifact is
limited to known logs, source SHA/tree/hash inventory, receipts and actual
logit arrays. Model weights, wheels, installed environments and arbitrary
host logs are excluded. The workflow has a 30-minute job limit and a
25-minute driver deadline. This workflow must run on the final published
source before claiming clean-runner acceptance; the local replay alone does
not establish that gate.

`assemble_offline_kit.py` provides a concrete full-payload kit build, bound to
an explicit clean source commit. The final kit must actually be assembled
and its ZIP receipt retained by the publisher. All wheel notices, the author
card/source/config and the pinned Tokenizers upstream license are present in
the profile. This is supplied-license accounting, not a full legal or
transitive dependency-source audit. Broader context, K/V disk integration,
assistant quality, serving and non-Linux packaging remain separate work.
