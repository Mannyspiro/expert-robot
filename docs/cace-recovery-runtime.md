# Local CACE model recovery — 2026-09-27

This is a draft replacement experiment on a new branch from the integration branch. It does not alter the deployed Cace-app branch or grant the model any verification/promotion authority.

The previous backend was unreachable, not proven untrained. The first recovery baseline is the official Apache-2.0 Qwen2.5-0.5B-Instruct Q4_K_M GGUF. Its official LFS SHA-256 was checked before loading. The official llama.cpp b11146 Linux x86_64 CPU archive was independently checked against the GitHub release asset digest before extraction. The GGUF and runtime files are not committed.

Real local HTTP inference through `CACEHeadlessClient.chat` succeeded on three prompts, on a loopback server using four CPU threads and 2048 context tokens. The server was terminated after the test. This proves local model contact, not CACE API availability or deployment on the remote ARM64 host.

The 0.5B model answered 2+3 correctly, but replied 4 to the sequence 2,4,6,8 (expected 10). This is a recorded failure, not a benchmark success. Evaluate the official 1.5B version before accepting a replacement. These are development smoke cases, not hidden evaluation or evidence of RSI.

The pending replacement configuration preserves untrusted output, separate deterministic verification and external promotion. The CACE source revision in configuration records the existing API source pin; the new model payload has not yet been staged there. Restaging and recording the new CACE commit are prerequisites for a full integrated headless rollout.

## Selected recovery candidate: official Qwen2.5-1.5B-Instruct

The 1.5B Q4_K_M model returned exactly 5 and 10 on the two development checks, in 0.650 and 0.197 seconds respectively. Both responses came through the actual CACE client and a checksum-verified llama.cpp process, not mocks. The 0.5B failure remains in `evidence/recovery-live-inference-20260927.json`; the selected candidate's evidence is `evidence/recovery-1.5b-live-20260927.json`. These few disclosed cases establish only a useful smoke baseline, not broad math competence or recursive improvement. The arithmetic wording differed between the initial 0.5B exploratory prompt and the later exact-output 1.5B smoke; this is not a controlled comparative benchmark.

The replacement defaults now select 1.5B, its official GGUF repository revision and b11146 runtime. Its GGUF is 1,117,320,736 bytes. The artifact lock records the independently obtained upstream model and release archive digests, along with the extracted server digest. Runtime binaries and shared libraries must remain together. This lock is Linux x86_64 only; the existing ARM64 CACE runner requires a separately qualified runtime build.

Explicit preparation (downloads only; no inference or paid API):

```sh
python3 scripts/prepare_cace_recovery.py --directory /absolute/external/model-cache
```

Use the returned model and server paths in the bounded offline smoke:

```sh
python3 scripts/smoke_cace_recovery.py --model /returned/model.gguf \
  --server /returned/llama-server --output /absolute/evidence.json
```

The smoke verifies both files, starts a private loopback CPU server on an available port, queries it through the CACE client, writes real responses and timing, then terminates its child process. It does not install or start the CACE API. Use an outer process/job timeout in unattended operation. Loopback binding and no API downloads do not constitute an OS-enforced network sandbox.

For the full staged CACE launcher, supply the same prepared model/binary paths and the two expected SHA-256 values printed by preparation. Restage the reviewed payload to Cace-app, record its new source pin, and run full CACE health/e2e qualification before deployment acceptance. That remote staging is not claimed by this PR.

Checks passed: real 1.5B inference; artifact preparation with checksum reuse and fresh extraction; CACE client smoke; staged local-LLM contract; orchestrator admission smoke; staging secret-separation smoke; launcher syntax and new Python syntax. Remote CACE API, runtime provisioning on ARM64, network isolation and end-to-end CACE execution remain unverified. No hosted jobs or service deployments have been started.

Next iteration: qualify the actual target host and CACE API; then run fresh, held-out tasks with deterministic/Lean verification before any generation promotion. Use the recorded small-model failure as a regression case, never as hidden evaluation.
