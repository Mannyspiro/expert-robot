# Merlin read-only research dashboard

The browser HUD is a read-only view over Merlin's canonical stores. It does not create
hypotheses, edit graph nodes, change evidence, approve jobs, or promote research.

## Initialize the canonical stores

From the repository root:

```bash
PYTHONPATH=python python3 scripts/init_merlin_dashboard_stores.py
```

By default this creates the stores under `~/.local/share/merlin`:

- `registry/merlin.sqlite3` and content-addressed artifact blobs
- `knowledge-graph.sqlite3`
- `event-outbox.sqlite3`
- `hypotheses.sqlite3`
- `events.sqlite3` (created when the API starts)
- `merlin-hud.env` with local path configuration

The bootstrap is idempotent. It opens or creates the stores and upserts the
`merlin-main` project record; it does not fabricate research events or evidence.
Use `--data-dir`, `--project-id`, and `--project-name` to select another local
store root or project identity.

## Start the local API and dashboard

```bash
bash scripts/run_merlin_hud.sh
```

Open:

```text
http://127.0.0.1:8765/hud
```

The server binds to loopback only. Keep it that way unless an authenticated access
layer is added. Do not expose this development API directly to a public interface.

## Read-only routes

- `GET /hud` — responsive browser dashboard
- `GET /api/hud/activity` — event timeline and activity summaries
- `GET /api/hud/graph` — canonical knowledge-graph snapshot
- `GET /api/hud/node?node_id=...` — one graph node, typed neighbors and workspace descriptor

The HUD API rejects mutating methods. If canonical store paths are not configured,
the page uses its explicit demo state; it does not silently present demo content as
live research. Empty stores produce an empty live dashboard until real project,
hypothesis, graph and outbox events are written by their owning services.

The chat composer is presentation-only. No chat submission or research-dispatch
endpoint is exposed through the dashboard.

## Production notes

- Keep the registry, graph, ledger and outbox on persistent storage.
- Back up SQLite databases and the registry blob directory together.
- Treat graph edges and HUD descriptors as navigation metadata, not proof.
- Treat simulation output as simulation evidence, not physical validation.
- Lean claims remain unverified until exact-source compilation and independent CACE
  verification receipts are present.
- Keep execution approval, leases, worker credentials and merge authority outside
  the read-only dashboard.
