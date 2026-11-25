# Merlin observable research window

The research window presents actual published Merlin events, exact registered
figures, and readable proof sources in one local program window. It extends the
existing HUD composition (`hud_activity`, `hud_http`, `hud_runtime`), canonical
artifact registry, knowledge graph, and durable telemetry outbox. It does not
start a model, generate research claims, or manufacture resource measurements.

## Open the window

From the repository root:

```bash
python3 -B scripts/merlin_research_window.py \
  --state-dir /path/to/merlin-window-state serve
```

This binds `127.0.0.1:5173` and opens `/dashboard` in the default browser. The
state directory holds the existing registry and its content-addressed blobs,
knowledge graph, and outbox. Reusing this directory restores recorded activity
and artifacts after restarting. Use a persistent location for ongoing research.

Use `serve --port 4173 --no-open` when another application manages the browser.
`PORT` supplies the default port when set. A port already in use causes an error;
there is no automatic port fallback. `--strictPort` is accepted for managed
preview compatibility.

The repository's dependency-free `npm run dev` launches this Python service with
state in `../merlin_window_state`. A managed preview may append its own `--host`
and `--port` values. The explicit development host is `0.0.0.0`; the standalone
Python command defaults to loopback. The HTTP surface is read-only and has no
publishing endpoint. A remote host must supply its own normal access controls.

## Publish an observed research event

Write a JSON event file using Merlin's telemetry contract, then publish it:

```bash
python3 -B scripts/merlin_research_window.py \
  --state-dir /path/to/merlin-window-state emit --event-file event.json
```

The same command without `--event-file` reads JSON from standard input. For
example, a real research task beginning can publish:

```json
{
  "source": "operator",
  "kind": "task.started",
  "run_id": "positive-unequal-weights",
  "payload": {
    "question": "Positive unequal weights",
    "summary": "Checking the weighted ordered-moment candidate.",
    "proof_status": "Candidate; formal verification is pending."
  }
}
```

Publish explicit activity and stage changes as they occur:

```json
{
  "source": "operator",
  "kind": "task.progress",
  "run_id": "positive-unequal-weights",
  "payload": {
    "stage": "formalization",
    "status": "active",
    "summary": "The exact candidate source is loaded in the proof checker."
  }
}
```

The window consumes only observable records. A source label identifies the
publisher; it does not independently establish a theorem or validate a claim.
`proof_status`, `formula`, and `metrics` are displayed as recorded research
content. Publish them only with the corresponding actual evidence. Existing CACE
attestation conditions are retained and are not inferred from operator reports.

Stages are `intake`, `hypothesis`, `representation`, `experiment`,
`counterexample`, `formalization`, `verification`, and `artifact`. An explicit
`research.stage` or `task.progress` stage takes precedence over inferred event
phases. Stage completion checkmarks require an explicit `completed_stages` list
on a research/task event. Later stages do not imply earlier stages succeeded.
An artifact registration never advances the research stage, completes a proof,
or replaces the main research summary.

For a stopped or completed bounded task, publish `task.progress` with status
`waiting`, or `task.completed` respectively. A `system.error` displays `failed`
until an explicit activity update resumes the run. A fresh active task rotates
the ASCII emblem and animates the activity strip. After 90 seconds without a
recorded event, active becomes waiting. This is a freshness indicator, not a
measurement of CPU use, model inference, or progress percentage.

## Show exact figures and proof sources

Explicitly register each artifact when it becomes relevant:

```bash
python3 -B scripts/merlin_research_window.py \
  --state-dir /path/to/merlin-window-state artifact \
  --path /path/to/research/figures/weighted-bound.svg \
  --allow-root /path/to/research \
  --run-id positive-unequal-weights \
  --title "Weighted bound" \
  --caption "Exact plot from the recorded weighted experiment." \
  --display-kind graph
```

For a Lean source, use `--display-kind source` and a `.lean` file. For a text proof
receipt, use `proof`; JSON evidence can use `data`. Images must use `graph`.
Allowed images are PNG, SVG, JPEG, and WebP. Text/plain, Lean source, and JSON are
readable as text. Artifacts are capped at 8 MiB. The command returns an immutable
ArtifactRef, graph node ID, event ID, and relative URL.

The publisher resolves symlinks and rejects a file outside every explicit
`--allow-root`. It copies exact bytes into the canonical registry and binds a
knowledge graph artifact node to that exact version and digest. Only registered
display nodes can be fetched over HTTP; there is no repository or host filesystem
browser. Every artifact response rechecks its pinned bytes and returns an
`X-Artifact-SHA256` header. A changed or missing blob fails closed. SVG responses
are sandboxed and text is served with `nosniff`.

The **Graphs** panel shows artifacts connected by a `uses` relationship to the
current run. It automatically follows new graphs while the checkbox is selected,
and retains the gallery for review. **Proof & evidence** displays the complete
registered UTF-8 text in `pre#source`, its exact identity, and an **Open artifact**
plain-text link. It does not render the source as HTML or execute it. **Research
map** displays recorded graph relationships and lets the user inspect each node.
It bounds the visualization to the first 28 nodes and states when truncated.

Artifact identity includes registry version. If a file is edited and later
reverted to earlier bytes, the new registry version has its own graph node.
Previously registered URLs remain pinned to their original version.

## Existing runtime integration

A running Merlin process can publish to its existing outbox with
`telemetry_outbox_sink`, or use `ResearchWindow.emit` when that composition owns
the same canonical stores. `ResearchWindow.register_artifact` performs the
explicit registry and graph operation and records its actual completion event.
There is no second telemetry history or hidden model process.

HTTP reads restore the last 1,000 telemetry records from the canonical outbox and
project them without leasing or acknowledging them. Normal outbox delivery can
continue independently. The standalone window intentionally does not start a
second delivery consumer. The dashboard polls at 2.5-second intervals while
visible and 10 seconds while hidden. A lost connection stops motion, reports
disconnection, and retains the last received evidence.

Motion can be paused. The setting persists locally, and the operating system's
reduced-motion preference takes precedence. Reduced motion does not stop event
updates or alter the evidence.

## Verification

Run the focused boundary and state tests:

```bash
PYTHONPATH=python python3 -B -m unittest discover -s tests \
  -p test_research_window.py -v
```

Coverage includes fresh/stale/failed/completed states; run isolation; pending
proofs with artifact arrivals; explicit stage completion; absence of fabricated
CACE attestation; exact text and graph bytes; pinned old and reverted versions;
corrupt blobs; root/symlink/media rejection; read-only HTTP behavior; bounded
outbox replay across restart; and the motion and graph-follow presentation
contracts. Browser visual and interaction checks remain separate from these
programmatic boundary tests.
