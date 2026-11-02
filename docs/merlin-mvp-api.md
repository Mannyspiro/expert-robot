# Merlin MVP API 0.3

Run from the repository root:

    PYTHONPATH=python python3 -m merlin.app --port 8765

The server binds only to 127.0.0.1. It uses Python's standard library and SQLite; no external service is needed for deterministic research/engineering endpoints.

## Endpoints

- GET /health
- GET /api/capabilities
- GET /api/events
- POST /api/chat (loopback model proxy; disabled until MERLIN_MODEL_QUALIFIED=1)
- POST /api/speech (loopback Kokoro proxy)
- POST /api/ideonomy/rank
- POST /api/analogy/validate
- POST /api/rsi/qualify
- POST /api/geometry/validate
- POST /api/netlist/validate
- POST /api/biology/mm/simulate (Michaelis-Menten RK4 simulation)
- POST /api/evolution/mm-fit (seeded evolutionary parameter fit)

Request and response bodies are JSON. Requests are limited to 1 MB. The event store records request hashes and result summaries, not raw request text. Database path defaults to ~/.local/share/merlin/events.sqlite3 and can be overridden with MERLIN_DB_PATH or --db.

Model chat, Hermes execution, image/video generation, and biochemistry remain explicitly unconfigured until real adapters are qualified. The capability endpoint distinguishes these from implemented deterministic endpoints. Kokoro and NousCoder services are optional local sidecars; the model is not inference-qualified yet.

This is a real API foundation, not the completed Merlin product. It does not expose arbitrary shell, file, repository, or deployment actions.


Biochemistry uses a closed single-substrate Michaelis-Menten model with RK4 integration and explicit substrate/product mass balance. Evolutionary fitting estimates Vmax/Km from supplied observations using a seeded bounded population search. Both remain HYPOTHESIS_ONLY and require independent data validation; they are not wet-lab protocols or clinical predictions.
