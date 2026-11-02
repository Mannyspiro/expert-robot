# Merlin MVP API 0.3

Run from the repository root:

    PYTHONPATH=python python3 -m merlin.app --port 8765

The server binds only to 127.0.0.1. It uses Python's standard library and SQLite; no external service is needed for deterministic research/engineering endpoints.

## Endpoints

- GET /health
- GET /api/capabilities
- GET /api/events
- POST /api/chat (allowlisted remote HTTPS OpenAI-compatible gateway with SSE passthrough; local loopback model remains separately gated)
- POST /api/speech (loopback Kokoro proxy)
- POST /api/ideonomy/rank
- POST /api/analogy/validate
- POST /api/rsi/qualify
- POST /api/geometry/validate
- POST /api/netlist/validate

Request and response bodies are JSON. Requests are limited to 1 MB. The event store records request hashes and result summaries, not raw request text. Database path defaults to ~/.local/share/merlin/events.sqlite3 and can be overridden with MERLIN_DB_PATH or --db.

Model chat, Hermes execution, image/video generation, and biochemistry remain explicitly unconfigured until real adapters are qualified. The capability endpoint distinguishes these from implemented deterministic endpoints. Kokoro and NousCoder services are optional local sidecars; the model is not inference-qualified yet.

This is a real API foundation, not the completed Merlin product. It does not expose arbitrary shell, file, repository, or deployment actions.


## Network inference v1

See [NETWORK_MODEL_STREAMING_V1.md](NETWORK_MODEL_STREAMING_V1.md). Configure `MERLIN_REMOTE_MODEL_URL`, `MERLIN_REMOTE_API_KEY`, `MERLIN_REMOTE_ALLOWED_HOSTS` and `MERLIN_REMOTE_MODEL_QUALIFIED=1` through the runtime environment, never a committed file. Remote inference requires HTTPS and an exact hostname allowlist. Set `stream: true` to pass through server-sent events incrementally. The current standard-library proxy is an MVP for low concurrency; an async connection-pooled gateway is the next performance step. Provider fallback must not silently move private prompts across trust boundaries.
