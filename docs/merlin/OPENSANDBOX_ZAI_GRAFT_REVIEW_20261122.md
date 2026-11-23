# Merlin optional OpenSandbox, Z.ai and Graft experiment — 2026-11-22

**Status:** source-pinned, opt-in experiment on top of the existing draft AirLLM/OpenBot PR #206.
No production release, host deployment, automatic model spending, or change to
Merlin's canonical ArtifactRef, approval policy, model configuration or Studio defaults.

## Source ledger and ranking

| Rank | Candidate | Pinned source | License | Action |
| --- | --- | --- | --- | --- |
| 1 | [OpenSandbox](https://github.com/opensandbox-group/OpenSandbox) | 2ff37a988e4df129babaa6f07bb616394ef94086 | Apache-2.0 | Experimental isolated Python runner |
| 2 | [Z.ai GLM API](https://docs.z.ai/) | Hosted service, no source checkout | Provider terms/API account | Explicit opt-in text-only model proxy |
| 3 | [getmodern-ai/Graft](https://github.com/getmodern-ai/graft) | c77155dcac2d7988fa27268c5ea78c23b651d5ab | Apache-2.0 | Pin source and study MCP tool authoring; not active |
| Deferred | [AEndrix03/Graft](https://github.com/AEndrix03/Graft) | f9913b045ef927f5b9afad37f3e6544111f05736 | Apache-2.0 | Memory/bug-recall benchmark against Merlin existing stores |
| Deferred | [ZCode](https://github.com/zai-org/ZCode) | fec975905a2abd4c07e35c40d51fa097a2258ec9 | Apache-2.0 | Study TUI/UI ideas, not overwrite Merlin Studio |

The two pinned source trees are Git submodules. Fetch and independently verify:

    git submodule update --init third_party/opensandbox third_party/graft
    python3 scripts/merlin/verify_optional_sources.py

Preserve Graft's upstream NOTICE and both Apache license files in redistribution.
A submodule commit identity proves source selection, not secure design or a
passing dependency audit. No Graft service is exposed automatically.

## OpenSandbox: operator-driven Python execution

Purpose: run an **approved byte-identical Python source** in an isolated
OpenSandbox container with bounded resources and a deny-all egress policy.
Merlin's built-in Studio Python tool remains unchanged until this candidate
passes real host security and reliability evaluation.

Requirements: a trusted, operator-managed OpenSandbox server bound locally
with appropriate authentication, and Docker on its execution host.
The OpenSandbox repository documents starting its server with:

    uvx opensandbox-server init-config ~/.sandbox.toml --example docker
    uvx opensandbox-server

Install the pinned SDK in an isolated environment, after reviewing dependencies:

    python3 -m venv .venv-opensandbox
    . .venv-opensandbox/bin/activate
    python3 -m pip install ./third_party/opensandbox/sdks/sandbox/python

Create a source file intentionally, review its contents, calculate its SHA-256,
choose a trusted immutable image digest, then run:

    sha256sum /path/to/approved_experiment.py
    python3 scripts/merlin/opensandbox_eval.py \
      --script /path/to/approved_experiment.py \
      --approved-sha256 <64-lowercase-hex-digest> \
      --image registry.example/python@sha256:<64-lowercase-image-digest> \
      --port 8080 --timeout 15

Replace example registry/digests with actual approved values. The adapter does
not fetch a specific image or expose any API endpoint to Merlin's model.
It requires an exact SHA of the proposed script, a digest-pinned container
image, and an OpenSandbox lifecycle with CPU 1, memory 512Mi, max 45 seconds.
It requests deny-all outbound egress and **checks the reported egress policy
before sending source bytes**, writes into /tmp inside the sandbox, runs
Python without user site imports, and calls destroy() in a finally block.

**Limits:** successful SDK policy readback is not proof of enforcement by
Docker, the host kernel, the container engine or network infrastructure. The
system must be independently tested against real egress attempts, resource
exhaustion, container escape protections, malicious inputs, cancellation,
credential isolation, audit and orphan cleanup before routine Merlin code
execution is moved to this backend. A process or network timeout can exceed
the client expectation if the infrastructure fails. The initial runner is
manual, not a merged replacement for Studio's host-executed Python.

## Z.ai: optional hosted GLM text model

Z.ai is a **cloud model provider**, not local source or local model weights.
Merlin Studio's original model endpoint accepts only loopback to preserve the
existing default. The new companion bridge maps that local protocol to Z.ai's
general OpenAI-compatible endpoint, but **never starts automatically**.

Only if the operator intentionally accepts remote text disclosure and possible
usage charges:

    export ZAI_API_KEY=...      # keep secrets outside the repo and chat
    python3 portable/merlin_studio/zai_bridge.py \
      --enable-cloud --model <your-authorized-general-API-model-id> \
      --max-calls 4 --port 8774

Connect Studio's existing Settings panel:
- Model URL: http://127.0.0.1:8774/v1/chat/completions
- Model ID: merlin-zai
- Chat-only mode. Tool declarations and tool_choice are stripped; a cloud-emitted JSON
  tool envelope is rejected even in Studio's read-only compatibility mode.
  **No remote tool execution** or native tool call integration is supported here.

The bridge demands an explicit CLI cloud opt-in, environment key, 1–20 call
attempt ceiling, limited prompt/output size, a single in-flight request,
fixed TLS host and path, and a non-streaming text response. Keys are never
logged or returned. No model spending or data transfer was performed during
development. General API: https://api.z.ai/api/paas/v4

Z.ai also has a separate Coding Plan API, but entitlement/use constraints may
differ. **Do not use the Coding Plan endpoint in this bridge**; its general
endpoint is pinned. Any private conversation/text sent through the bridge
is shared with that external provider and may incur charges. External model
quality, model access, cost and cancellation have not been qualified.

## Graft: proposal, not tool authority

The chosen Graft project is the Apache-licensed tool-acquisition MCP server
at getmodern-ai/graft. It generates, tests and can promote new integration
tools into an agent working set. That capability is potentially useful for
Merlin but requires host credential custody, per-connection authorization,
untrusted API document handling and explicit approval on every write.
The alternative AEndrix03/Graft is an unrelated coding-agent memory system.

Before any live Merlin integration, require a deterministic local simulated
service test demonstrating:
1. no credential in candidate code, logs or model prompt;
2. no real API write before operator approval, including retries;
3. immutable candidate source and schema bound to independent tests;
4. no automatic promotion or privilege escalation;
5. replayable ArtifactRef results and clean rollback after failure.

Do not automatically merge Graft's tool store with Merlin's canonical registry,
or equate passing Graft's scripted examples with production qualification.

## Verification and evidence

The dedicated .github/workflows/merlin-opensandbox-zai.yml:
- Fetches **exact pinned** OpenSandbox and Graft Git commits.
- Checks gitlinks, source cleanliness, .gitmodules URLs, Apache notices.
- Compiles original Python adapters.
- Executes tests/test_opensandbox_zai_integration.py using an injected
  OpenSandbox SDK fixture, a simulated Z.ai sender and loopback HTTP requests.
- Performs **zero** real Docker executions, Graft tool acquisitions, live Z.ai
  model calls or billable requests.

Acceptance after this CI is independent native execution: (a) real deny-all
egress confirmed by a blocked external request; (b) controlled resource/timeout
experiment; (c) real source-identity receipt; (d) model quality and privacy
check against local baseline; (e) tested recovery and explicit release review.

## Skeptical-scientist frame

**Premise:** an isolated execution service could reduce host blast radius
without sacrificing useful research performance. **Falsifier:** production
network/resource controls fail, false approvals are accepted, or runtime/
dependency overhead exceeds measured benefits on representative tasks.
**Competing alternative:** retain a restricted local process worker only for
trusted, operator-supplied code. Independent axes: source provenance, API
connectivity, isolation, authority, correctness, latency, and cost (n-ality).
Simplex resource allocation and continuum latency models deferred until
calibrated measurement; fuzzy scores cannot replace strict authorization.
