# Merlin Studio controlled model-selected tool and human approval episode

Date: 2026-11-22 (UTC 2026-11-23)
Status: Synthetic model protocol / real Studio HTTP and host worker verified. **No real model weights or production host qualification.**

## Why this test exists

Earlier Studio unit tests established that the model HTTP adapter can receive tool-call JSON and return a tool result. The production acceptance gap was an independently replayable real HTTP conversation that forces a *model-selected* Python action across the actual human approval and canonical ArtifactRef boundaries, and proves that refusing the same kind of proposed action prevents execution.

## Exact measured evidence

- [Draft PR #220](https://github.com/Mannyspiro/expert-robot/pull/220), source SHA 935eddc29cb1529105c8a1283d6ba921676503fd.
- [CI run 45103273568](https://github.com/Mannyspiro/expert-robot/actions/runs/45103273568): **success**, ephemeral GitHub Ubuntu 24.04 / Python 3.11.
- [Machine-readable episode and SHA-256 receipt artifact #14786735318](https://github.com/Mannyspiro/expert-robot/actions/runs/45103273568/artifacts/14786735318), expires 2026-12-07.
- The complete original portable Studio test suite passed **36/36** tests.
- The controlled loopback model service made **four chat-completion HTTP calls** total: a tool proposal and a follow-up response for each of two cases.
- Approved case: model proposed run_python for an exact workspace path, Studio bound the script SHA-256 in a real pending human approval, a wrong approval ID was rejected, a correct approval started the real host Python worker, and the returned stdout marker appeared in a single canonical tool_result event with a stable ArtifactRef SHA-256. The model's second HTTP turn consumed that actual stdout before replying with the verified answer.
- Declined case: model proposed another source-bound Python script, the human-approval HTTP action declined it, no tool_result event or marker file was created, and the model's second HTTP turn explicitly observed the refusal.
- Both cases used only synthesized fixture content. No real user messages, hosted API, extra privileges, downloaded weights or third-party vendor requests were involved.

## Evidence class and limitations

The model was a **deterministic synthetic OpenAI-compatible HTTP fixture**, not a trained or weighted model. This validates protocol integration, authorization, tool identity and evidence propagation, not model reasoning, coding quality, creativity, or scientifically correct inference. The Python worker was the original **host** backend in a disposable CI runner; it was not executed in OpenSandbox in this workflow. OpenSandbox native execution, owner reconciliation and controller outage were independently verified by earlier draft PR #216. The rendered UI with human clicks (on synthetic host scripts, not model-selected inference) was independently verified in draft PR #217.

The test used real HTTP approval decisions rather than human clicking the browser. Both paths must be run together on an approved production host with actual model weights before release.

## Next ranked acceptance tests

1. Select a carefully licensed, bounded **real local model checkpoint** and run an independent evaluation across one direct question and one approved read-only tool task. Preserve prompt/model/checkpoint identities, measured memory, latency and error cases.
2. Exercise actual model-selected Python execution and refusal via the rendered Studio browser on the approved OCI/desktop host, preserving source binding and Docker isolation and capturing independent evidence.
3. Evaluate kernel-controlled latency and RAM use on the release host; use the same model/task corpus for AirLLM versus existing llama.cpp only after both are correctly configured.
4. Reconcile dependency chain and release candidate source/CI with GitLab OCI runner, source digest and explicit owner approval. Do not merge review branches merely because this fixture passed.
5. Produce a reviewed, reproducible zip/app distribution with startup, authentication, telemetry, restart and rollback tests.

## Skeptical-scientist record

Hypothesis: Merlin can relay an actual model-selected tool request through approval, tool execution and a durable evidence-bearing model follow-up. Observation: full loop passed with a deterministic local fixture and actual host subprocess; declined action never executed. Competing explanation: a real language model might emit malformed, ambiguous, duplicate or unsafe tool calls; this fixture does not sample that distribution. Falsifier: tool executes before approval, wrong source hash accepted, user denial ignored, result not delivered to model, or missing ArtifactRef. N-ality axes: model weights, HTTP protocol, approval, source identity, tool result, persistence and target host. Simplex/continuum deferred pending measured multi-resource and repeated inference data. Fuzzy authorization not applicable.
