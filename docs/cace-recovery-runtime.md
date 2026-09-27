# Local CACE model recovery — 2026-09-27

This is a draft replacement experiment on a new branch from the integration branch. It does not alter the deployed Cace-app branch or grant the model any verification/promotion authority.

The previous backend was unreachable, not proven untrained. The first recovery baseline is the official Apache-2.0 Qwen2.5-0.5B-Instruct Q4_K_M GGUF. Its official LFS SHA-256 was checked before loading. The official llama.cpp b11146 Linux x86_64 CPU archive was independently checked against the GitHub release asset digest before extraction. The GGUF and runtime files are not committed.

Real local HTTP inference through `CACEHeadlessClient.chat` succeeded on three prompts, on a loopback server using four CPU threads and 2048 context tokens. The server was terminated after the test. This proves local model contact, not CACE API availability or deployment on the remote ARM64 host.

The 0.5B model answered 2+3 correctly, but replied 4 to the sequence 2,4,6,8 (expected 10). This is a recorded failure, not a benchmark success. Evaluate the official 1.5B version before accepting a replacement. These are development smoke cases, not hidden evaluation or evidence of RSI.

The pending replacement configuration preserves untrusted output, separate deterministic verification and external promotion. The CACE source revision in configuration records the existing API source pin; the new model payload has not yet been staged there. Restaging and recording the new CACE commit are prerequisites for a full integrated headless rollout.

Current checks: CACE client smoke and staged local-LLM contract pass; launcher syntax passes. Remote CACE API, runtime provisioning on ARM64, network isolation and end-to-end CACE execution remain unverified. No hosted jobs or service deployments have been started.
