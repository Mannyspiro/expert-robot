# Merlin Runtime Telemetry and Independent Review Gate v1

## Runtime instrumentation contract

Every real component emits telemetry at its boundary, not from a dashboard simulation:
- HTTP API request lifecycle: started, completed, failed; duration measured with a monotonic clock.
- Model adapter: provider/model identifier, elapsed time, response byte count, streaming byte count, and measured resource samples where available. Never record prompts, completions, API keys, authorization headers, or audio.
- TTS adapter: model/voice identifier only when known, elapsed time, response bytes, and error category; never persist voice input or generated audio.
- Verifier: exact verifier identity/version, result, duration, evidence digest, and assumptions; no promotion decision.
- Module loader: artifact digest, bytes read, peak RSS delta where measured, load/unload duration, resident-set delta, and outcome.
- Orchestrator/agent: run/task IDs, lifecycle transitions, bounded progress counters, and explicit parent relationships.
- Operator actions: action identity and outcome; no secret-bearing request bodies.

Each event has an explicit source (runtime, model_output, verifier, operator, or simulation). A simulation event must never be relabeled as runtime. Events are append-only metadata and evidence digests; raw user content is excluded by default. Instrumentation failures must not silently fabricate success telemetry.

## Graph explorer contract

Graph levels are run → task → event → evidence. Edges represent only recorded containment and explicit evidence references. No inferred causal or dependency edges. Node expansion reveals source, timestamp, component, measured resource fields, safe payload metadata, adjacent nodes, and evidence digests. Evidence navigation opens only an explicitly registered local evidence resolver; arbitrary URLs and paths are not executable links. The graph is a projection, not an authority surface.

## Loader memory qualification

Measure cold and warm load separately over repeated trials. Capture process RSS before, peak during, and after load; artifact size; bytes read; resident module bytes; loader allocations if exposed; load/unload latency; and post-unload retained RSS. Include an artifact larger than the resident budget and concurrent activation attempts. Verify that memory accounting includes transient buffers and that the exact hashed bytes are the bytes passed to the loader. Use streaming hashing and descriptor-bound loading where the adapter supports it. If the runtime loader requires a full byte buffer, report the unavoidable peak rather than claiming bounded streaming behavior.

Qualification requires a declared memory ceiling, repeated successful trials, no budget overshoot beyond a predeclared measurement tolerance, no hash/load race, and successful unload/reload. A failure leaves the module unqualified and non-promotable.

## Stochastic paired experiments

A seed must control the generated workload, not merely be echoed in metadata. Run each candidate against the same seed/workload pair; randomize candidate execution order; separate development seeds from held-out seeds; record PRNG algorithm/version; and publish per-pair differences plus confidence intervals. Require a minimum trial count selected before looking at results. Report quality, verifier pass rate, p50/p95 latency, peak RSS, load/switch overhead, and failures. A result cannot authorize promotion.

## Independent code review

Coder A and Reviewer B must be distinct identities and separate execution contexts. Reviewer B receives the frozen spec, base commit, candidate diff, reproducible test command, and evidence bundle, but not Coder A's private reasoning or preferred conclusion. Reviewer B independently inspects changed code, writes adversarial tests, executes the bounded test suite, and returns a signed/hashed review packet containing commit SHA, test environment, commands, results, findings, unresolved risks, and explicit approval/rejection. A second persona or second prompt on the same model is not independent review. If a distinct reviewer identity/context is unavailable, status remains NOT_INDEPENDENTLY_REVIEWED.

## Authority invariant

Capability grows; authority never expands. These systems emit evidence and qualification results only. No telemetry, graph interaction, experiment result, reviewer recommendation, or model output can merge, deploy, promote, or grant permissions. Human approval and existing qualification gates remain mandatory.
