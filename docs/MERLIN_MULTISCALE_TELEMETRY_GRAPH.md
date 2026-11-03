# Multiscale telemetry graph

GET /api/telemetry/graph projects persisted telemetry identifiers into four
zoom levels: run, task, event and evidence. Edges express containment and
explicit evidence references only; the projection does not infer causality.
Each event retains its source label. Empty or absent identifiers are omitted.
The graph is a data projection, not a claim that the runtime has agents,
hypotheses or proofs unless those are explicitly emitted as events/evidence.
The graph is suitable for a HUD renderer to progressively expand by level.
