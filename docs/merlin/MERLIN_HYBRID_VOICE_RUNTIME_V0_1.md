# Merlin Hybrid Voice and HUD Runtime v0.1

## Design lineage

This implementation imports the useful parts of the JARVIS desktop-assistant archive into Merlin's existing web HUD and service boundary. It does not fork a second Tkinter application or replace the canonical registry, knowledge graph, Hermes, Avrea, MCFC or CACE.

## Current interaction path

1. The browser loads the runtime provider-status endpoint.
2. The operator chooses a qualified local or cloud model.
3. The browser sends the current tab's bounded conversation context to the Merlin chat API.
4. Merlin routes the request to a loopback OpenAI-compatible local endpoint or an HTTPS cloud endpoint whose host is explicitly allowlisted.
5. The response is rendered as text in the HUD. The browser keeps a bounded in-tab history; this PR does not claim persistence across reloads.
6. Optional speech output calls the loopback TTS sidecar only after the TTS qualification flag is set.
7. Browser speech recognition is feature-detected and remains subject to browser support and microphone permission.
8. Explicitly approved preferences and project notes are stored in a separate local SQLite memory vault. The browser includes them in model context only when the operator enables **Use memory**.

## Runtime configuration

- `MERLIN_MODEL_QUALIFIED=1`: local model has completed the applicable qualification process.
- `MERLIN_MODEL_URL`: loopback-only OpenAI-compatible local chat endpoint; defaults to `http://127.0.0.1:8080/v1/chat/completions`.
- `MERLIN_LOCAL_MODEL`: required local model identifier; falls back to `MERLIN_MODEL_NAME`.
- `MERLIN_REMOTE_MODEL_QUALIFIED=1`: cloud model has completed the applicable qualification process.
- `MERLIN_REMOTE_MODEL_URL`, `MERLIN_REMOTE_API_KEY`, `MERLIN_REMOTE_ALLOWED_HOSTS`: HTTPS cloud endpoint, secret and explicit hostname allowlist.
- `MERLIN_REMOTE_MODEL_NAME`: required cloud model identifier; falls back to `MERLIN_MODEL_NAME`.
- `MERLIN_TTS_QUALIFIED=1`: local speech sidecar has completed its qualification process.
- `MERLIN_TTS_URL`: loopback-only TTS endpoint; defaults to `http://127.0.0.1:8880/v1/audio/speech`.
- `MERLIN_MEMORY_DB_PATH`: optional path for the explicit memory vault; defaults to `memory.sqlite3` beside the configured Merlin event database.

The provider-status endpoint returns only status, transport class and qualified model identifiers. It never returns credentials or provider URLs. Its state is QUALIFIED_CONFIGURED, not a live health claim: reachability is not probed until a request is made. An endpoint being reachable or installed is not sufficient to mark a provider qualified.

## User-approved memory vault

The local API exposes `GET /api/memory`, `POST /api/memory/preferences`, `POST /api/memory/projects`, and matching DELETE routes. Saving requires an explicit UI confirmation and an `approved: true` API field. The HUD commands are:

- `/remember key = value`
- `/project name | current status`
- `/memory`
- `/forget key`
- `/forget-project name`

Memory records are versioned and transactionally stored in SQLite. The event ledger receives only entry identifiers and content digests, not raw memory values. Conversation transcripts are not retained. The opt-in context toggle is off by default. Do not save passwords, API keys, tokens, private keys, or sensitive personal information. The vault is a convenience memory store, not an authorization or verification source.

## JARVIS concepts retained

- Local-first and optional cloud intelligence.
- Calm conversational interaction with optional voice input/output.
- Persistent system telemetry and a clear runtime status.
- Permission and qualification gates around external capabilities.
- Separate council preparation and normal chat.
- Safe handling of UI/background operations and no arbitrary terminal-command execution.

## Deliberately not claimed yet

- Wake-word detection or always-on microphone capture.
- Desktop application/file control.
- Cross-session transcript retention. The separate user-approved preference/project vault is implemented, but it is not automatically included in chat context.
- Piper/Kokoro deployment, voice identity qualification or measured speech latency.
- A native desktop shell or OS login startup.
- Merlin composer-to-Hermes/Avrea dispatch.
- Independent CACE receipts for provider execution.

## Qualification

The dedicated Avrea workflow checks Python compilation, the focused Merlin API suite and inline HUD JavaScript syntax on the exact PR head. It retains runner identity, logs and a machine-readable result artifact on success or failure. A green workflow is a code/test qualification result, not proof that model or TTS services are installed or qualified in production.
