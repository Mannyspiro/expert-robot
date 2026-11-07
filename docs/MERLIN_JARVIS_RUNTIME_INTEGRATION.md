# Merlin / J.A.R.V.I.S. Unified Runtime Integration

**Status:** architecture integration specification; not a claim that the runtime adapters below are all implemented or qualified.

This document captures the useful interaction ideas from the J.A.R.V.I.S. prototype and maps them onto the existing Merlin MVP. The objective is one production runtime and one source of truth—not a second backend, duplicate memory database, parallel agent scheduler, or independent execution authority.

## 1. Existing foundations to reuse

The repository already contains the core seams:

| Need | Existing implementation | Integration rule |
|---|---|---|
| HTTP API and local service | `python/merlin/app.py` | Extend the existing loopback API; do not add a competing FastAPI server |
| Capability truth | `/api/capabilities` and capability registry | Report unavailable/unqualified honestly |
| Conversational memory | `memory_vault.py` | Reuse explicit user-approved memory; do not create a second SQLite conversation store |
| Interaction learning | `interaction_learning.py` | Store privacy-minimized outcome metadata and aggregate evidence |
| Research/operational telemetry | `telemetry.py`, `telemetry_graph.py`, event ledger | Normalize all events with source and provenance |
| HUD | `/hud`, `simulation.py` | Extend the existing HUD; keep simulation and live telemetry visually distinct |
| Voice output | qualified loopback Kokoro proxy at `/api/speech` | Reuse the TTS adapter and capability qualification |
| Cloud inference | `/api/chat` allowlisted HTTPS gateway | Reuse explicit provider policy; never silently change trust domains |
| Local inference | existing loopback model configuration | Add a measured provider adapter, not a direct Ollama call embedded in the UI |
| Agent dispatch | Hermes outbox and typed prompt contract | All agent work passes through typed tasks, leases, limits and evidence receipts |
| Code/repository execution | Virtual Forge and worker queue | Never execute Python in the API process |

The existing simulation control room is deterministic and correctly labels its data as simulation-only. It is a presentation foundation, not proof that live host telemetry or a real model is connected.

## 2. Target runtime topology

```text
Browser / Desktop HUD
  ├── text input
  ├── browser speech recognition (permission-gated)
  ├── audio playback (user-gesture/autoplay policy)
  ├── research canvas / neural graph
  └── live status + telemetry stream
          |
          | same-origin HTTP + authenticated event stream
          v
Merlin API / session boundary
  ├── identity, session and CSRF/origin policy
  ├── consent and memory controls
  ├── intent compiler
  ├── capability registry
  ├── provider router
  ├── event/telemetry normalizer
  └── tool broker (typed allowlist only)
          |
          +--> Local inference adapter (loopback)
          +--> Remote inference adapter (HTTPS allowlist)
          +--> TTS adapter (loopback Kokoro)
          +--> Hermes task outbox
          |       +--> bounded worker / Avrea / OCI
          |       +--> result and evidence receiver
          +--> CACE independent verifier
          +--> Virtual Forge / canonical registry
          +--> memory vault / interaction learner
```

The browser is a client, not an authority boundary. It may request an operation; only the server-side policy and typed tool broker can authorize it.

## 3. Interaction contract

### Chat and model routing

- Keep one conversation/session contract and one provider router.
- A provider selection is explicit and visible: local, remote, or unavailable.
- Record provider/model identity, revision when known, latency, token/usage metadata when supplied, status and response digest.
- Do not send private memory or conversation context to a remote provider unless the user has enabled that data flow and the provider policy permits it.
- Provider fallback must not silently move data from local to cloud.
- Timeouts, cancellation, maximum output size, concurrency and queue limits are enforced server-side.
- A failed or unqualified provider returns a typed unavailable/error state, not a fabricated answer.

### Voice input and output

- Speech recognition stays in the browser where supported and requires browser microphone permission.
- Send recognized text through the same chat/session endpoint as typed input.
- Display whether recognition is browser-local or uses a remote browser service; do not imply local processing when the browser does not guarantee it.
- Speech output uses the existing qualified TTS sidecar through `/api/speech`.
- TTS failure must not fail the text response. Show an explicit audio status.
- Do not synthesize or claim a British voice until a specific voice asset and output have been tested.
- Do not start background microphone capture. Listening begins only after a user gesture and visibly indicates active capture.

### Voice session implementation gate

The HUD voice control is a user-started, continuous browser recognition session:
- Recognition starts only from the microphone button click and stops on a second click or when the user submits the message.
- The control exposes pressed/listening state to assistive technology and reports permission, unsupported-browser, recognition-error and stopped states.
- Interim and final recognition text is kept in the editable message field; recognition never submits a message automatically.
- The browser's speech-recognition implementation may use a remote service. The HUD states this limitation and must not label recognition as local unless the browser provides a verifiable local-processing guarantee.
- The browser session does not persist audio or transcript to durable memory by itself. Normal chat submission policy still applies, including explicit cloud-provider selection and confirmation.
- Speech output remains an optional, separately qualified TTS operation. Failure to synthesize or play audio must not discard the text response.

Acceptance checks: verify start/stop through a real microphone permission grant, deny permission and confirm visible error state, confirm continuous interim/final transcript behavior, submit while listening and confirm recognition stops before the chat request, and verify no microphone starts on page load or reload. These require browser/device execution; JavaScript syntax validation alone is not acceptance.

### Memory and preferences

- Reuse `MerlinMemoryVault`; no separate `jarvis_memory.db`.
- Distinguish session context, explicit user-approved durable memories, project artifacts and operational telemetry.
- Provide inspect, edit, export and deletion workflows with clear scope.
- Do not store full raw conversations as a side effect of telemetry.
- Store only the minimum needed for a stated purpose; set retention and access rules.
- A memory item is context, never a tool permission or authority grant.

### Desktop and document operations

Replace free-form slash-command side effects with typed intents:

- `file.search`: bounded roots, no symlink escape, result count/size limits, read-only.
- `document.create`: safe relative path under an approved workspace, extension/content limits, preview and explicit confirmation for writes.
- `memory.propose`: propose a preference or memory; require user approval before persistence.
- `repository.inspect`: read-only registry/Forge query.
- `code.execute`: submit a task to the isolated worker broker; never execute inside the HTTP server.

Each tool has a schema, allowlisted arguments, resource limits, audit event, idempotency key and explicit result state. Unknown commands are inert text, not shell commands.

## 4. Code execution and security invariants

The prototype's `exec(code, exec_globals)` must not be ported into the web server or trusted runtime. Redirecting stdout does not create a sandbox.

Production code execution must use an isolated worker with:
- disposable workspace and immutable input snapshot;
- non-root identity and no host filesystem mount except an explicit scratch directory;
- no credentials by default and no network by default;
- CPU, memory, disk, process-count and wall-clock limits;
- process-tree termination and cancellation;
- bounded stdout/stderr and retained logs;
- declared toolchain and dependency lock;
- source commit, input digest and output digest;
- test result and failure state recorded separately from CACE verification.

The browser must never send Python that is executed directly by the API process. A successful process exit is not proof correctness. A passing test is not independent CACE verification.

Additional controls:
- Do not use wildcard CORS with credentials.
- Bind local development services to loopback by default.
- For non-loopback deployment, require authentication, origin/CSRF protection, TLS and explicit network policy.
- Treat browser HTML, model output, tool output and filenames as untrusted; render text with safe DOM APIs, not `innerHTML`.
- Do not expose API keys, local paths, environment variables or raw exception traces to the browser.
- Use parameterized SQL and bounded request/response sizes.
- Never display synthetic constants as live host or physical telemetry.

## 5. Telemetry and visual language

Every metric and event carries:
- `schema` and schema version;
- `source` (for example `simulation`, `host`, `model`, `worker`, `cace`);
- `environment` and `run_id`;
- timestamp, task ID and component;
- measurement name, value, unit and collection method;
- status, uncertainty/quality where applicable;
- evidence references and content digest where available.

The HUD must keep distinct visual treatments and labels for:
1. deterministic simulation;
2. measured host/runtime telemetry;
3. model-reported usage;
4. worker execution state;
5. independently verified evidence.

No default value such as a cryogenic temperature may appear as a real measurement unless an instrument adapter supplies a calibrated reading with provenance. Missing measurements display `unavailable`, not a plausible-looking constant.

The neural constellation is a visualization of the actual normalized task, artifact and evidence graph. Its edges must represent declared relationships (depends-on, produced-by, verifies, derived-from); decorative animation must not be presented as model cognition or private chain-of-thought.

## 6. Versioned API/event increments

Prefer additive, versioned extensions to existing endpoints:

- `POST /api/chat`: session ID, message, explicit provider policy, memory-use consent and streaming preference.
- `POST /api/speech`: reuse the current proxy; add bounded voice selection and explicit output status.
- `POST /api/tools/dispatch`: typed tool ID, validated arguments, idempotency key, requested resource budget and approval reference.
- `GET /api/runtime/status`: provider qualification, health probe, active jobs, queue depth and source-labeled host metrics.
- `GET /api/events/stream`: authenticated resumable event stream with event IDs and backpressure.
- `GET /api/memory`, `POST /api/memory/proposals`: explicit memory lifecycle; never expose unrestricted raw database access.

These are target contracts, not assertions that every endpoint currently exists. Update `/api/capabilities` only when the corresponding adapter and tests are present.

## 7. Implementation sequence and acceptance gates

### J0 — Inventory and contracts
- Map the current HUD, chat, memory, TTS, telemetry, outbox, registry and Forge interfaces.
- Record endpoint schemas and current capability statuses.
- Add contract tests before changing existing behavior.

**Accept when:** no duplicate runtime or memory store is introduced; existing simulation and MVP tests remain green.

### J1 — Unified session/chat adapter
- Add one session-aware conversation contract over the current API.
- Connect local and remote providers through the existing provider policy.
- Add cancellation, bounded streaming, explicit provider selection and safe rendering.

**Accept when:** local and remote paths are tested independently; provider failures and trust-boundary behavior are covered.

### J2 — Voice loop
- Connect browser speech recognition to the same chat endpoint.
- Connect TTS to the existing qualified sidecar.
- Add visible listening, speaking, error and permission states.

**Accept when:** no background microphone capture; text works when audio is unavailable; audio tests prove actual generated output.

### J3 — Tool broker
- Define typed file/document/memory/Forge tools.
- Enforce allowlists, path containment, approvals, idempotency and budgets.
- Route code execution only to isolated workers.

**Accept when:** traversal, symlink, oversized input, unauthorized write, cancellation and sandbox escape tests fail closed.

### J4 — Live observability HUD
- Subscribe to normalized runtime events.
- Add host metrics only from a real host collector.
- Graph the real task/artifact/evidence graph and retain source labels.

**Accept when:** synthetic, host, model, worker and CACE events cannot be confused in UI or API responses.

### J5 — Qualification and production rollout
- Run exact-head tests and collect logs/artifacts for every attempt.
- Qualify local model, remote model, TTS, worker and CACE adapters independently.
- Perform security review, load tests, restart/recovery and retention/deletion tests.

**Accept when:** each advertised capability has a versioned qualification receipt and no blocked capability is represented as operational.

## 8. Non-goals

This integration does not:
- create a parallel FastAPI/JARVIS server;
- require Ollama or a new model download as a production prerequisite;
- store duplicate conversation history;
- run arbitrary Python in-process;
- grant browser code direct filesystem or repository access;
- claim a simulated council is multiple independent models;
- expose private model chain-of-thought;
- make capability growth an automatic increase in authority.

**Invariant:** capability grows; authority never expands.
