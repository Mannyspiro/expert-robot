# Merlin Council: Local Execution and Debate Protocol

## Purpose

Turn the six simulated council perspectives into actual independent model calls without pretending that prompt personas are independent people or independent models.

## Execution contract

- `POST /api/council/prepare` creates role-specific packets only; it does not call a model.
- `POST /api/council/run` performs actual inference only when `MERLIN_MODEL_QUALIFIED=1`.
- The runtime accepts only an HTTP loopback endpoint (`127.0.0.1`, `localhost`, or `::1`). It cannot send council prompts to a remote provider.
- `MERLIN_MODEL_URL` defaults to `http://127.0.0.1:8080/v1/chat/completions`; `MERLIN_MODEL_NAME` is metadata sent to the local OpenAI-compatible server.
- Each of the six opening calls receives only the shared question/context and its own role packet. No peer outputs are included in the opening phase.
- `rounds=1` is the default and costs six local inference calls. `rounds=2` performs six additional cross-examination calls after all openings exist. The second round sees peer openings and is explicitly labeled as debate.
- Only non-streaming OpenAI-compatible chat-completions responses are accepted. Response size is bounded.
- Transcript outputs include per-response hashes, model/provider labels, optional usage metadata, and a transcript hash. The event ledger stores only request metadata and hashes, not full prompts or transcript text.
- The endpoint returns `promotion_authorized=false` and `authority_expansion=false`; no model response can approve, merge, deploy, or promote code.

## Enablement

Do not set `MERLIN_MODEL_QUALIFIED=1` merely because a model server responds. First complete local model qualification: known-model identity, deterministic smoke tests, prompt/response bounds, refusal/error behavior, latency/resource measurements, and reproducible output capture. Then enable the variable in the local service environment.

Example request:

```json
{
  "question": "Should Merlin use a contextual strategy selector?",
  "context": "Compare quality, latency, memory, and switching overhead.",
  "verbosity": "lively",
  "rounds": 1
}
```

Use `rounds=2` only when the added six calls are worth the cost. The default remains one round to conserve CPU time.

## Interpretation

A single local model wearing six role prompts creates useful structured disagreement, but not six independent model judgments. Report this as **role-diverse, same-model deliberation**. Stronger independence requires a separately qualified second model or human reviewer, different evidence paths, and explicit provenance. Never imply model diversity that did not occur.

## RSI boundary

Council output is advisory. Qualification, independent review, held-out testing, rollback readiness, human approval, compute limits, and authority-nonexpansion remain separate gates. The invariant remains: **capability grows, authority never expands.**
