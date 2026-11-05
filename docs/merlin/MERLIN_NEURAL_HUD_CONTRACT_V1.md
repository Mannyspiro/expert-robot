# Merlin Neural HUD Contract v1

## Intent

The Merlin HUD is a full-screen, mobile-capable research instrument. Its visual language may take broad inspiration from cinematic AI assistants and investigative workspaces, but it must remain an honest operational interface: animation is a visualization of recorded system activity, not a claim to expose private model reasoning.

## Layout

- **Top status rail:** project/run identity, connection state, active phase, agent count, event count and evidence count.
- **Neural activity field:** animated graph of the active research process. The center represents the Merlin orchestration core; outer layers represent intake, hypothesis formation, modeling/representation, formal work and result/artifact collection.
- **Adaptive research canvas:** the largest work surface. It changes representation with the current phase: equation and hypothesis maps, coordinate transforms, experiment plots, counterexample spaces, theorem dependency graphs, verification evidence and artifact lineage.
- **Persistent bottom composer:** conversational input, voice affordance and context attachment affordance. Controls must be labelled honestly until connected to authenticated endpoints.

## Neural graph semantics

The graph is a projection of observable event and state data.

- Nodes represent bounded entities: agents, hypotheses, representations, experiments, proof obligations, verification receipts and artifacts.
- Edges represent typed relationships or event flow. They must be sourced from graph records or normalized activity events.
- Active nodes use a restrained cyan highlight; verified nodes use a distinct green treatment; tentative or queued nodes remain muted.
- A pulse may travel only along a relationship supported by the current snapshot. Do not animate arbitrary paths and imply real execution.
- Agent nodes are limited in number for legibility; show a bounded subset and expose the full activity list in the event feed.
- Evidence nodes are visually distinct from hypotheses and claims. A claim is not verified merely because it has an attached artifact.
- A verification state is green only when an independent verifier receipt is present and its binding checks have succeeded. Demo fixtures must never receive a production-verified visual state.

## Activity vocabulary

The current phase vocabulary is:

1. intake
2. hypothesis
3. representation
4. experiment
5. counterexample
6. formalization
7. verification
8. artifact

Events should carry stable event IDs, timestamps, run IDs, source agent/tool identity, project/revision context and a typed event kind. The HUD consumes normalized activity snapshots; it does not become a second source of truth.

## Runtime truth and demo behavior

- Live telemetry is read from the HUD activity endpoint.
- If the endpoint is unavailable, the interface may show a labelled simulation to demonstrate layout and motion.
- Demo mode must be unmistakable in the status rail and event summaries.
- Simulated agent activity, proof receipts, runner results and evidence must never be persisted as real project data.
- The HUD must not invent task completion, resource usage, approvals, proof success or deployment status.
- Chat, voice submission and attachments remain visibly unavailable until connected to authenticated APIs.

## Motion, accessibility and mobile

- Respect `prefers-reduced-motion`; all information must remain understandable with animation disabled.
- Motion is subtle and purposeful: pulses indicate event flow, not urgency.
- Maintain readable contrast, semantic labels and keyboard-operable controls.
- On narrow screens, preserve the status rail, neural field, adaptive canvas and composer without requiring horizontal scrolling.
- Avoid excessive glow, rapid flashing, full-screen transitions and decorative particle noise that competes with equations or engineering diagrams.

## Security and authority boundary

The HUD is a presentation surface, not an authority surface. It may display approval requests and verification outcomes, but cannot grant approval, expand a runner's authority, waive resource limits or promote a research claim. Capability grows; authority never expands.

## Acceptance criteria

- The neural field renders from an activity snapshot and changes when phase, agent or evidence data changes.
- Every visible status is traceable to a normalized event, registry record or explicit demo fixture.
- Demo and live states are visually distinguishable.
- A verified result shows its receipt identity and source revision in the adaptive canvas or detail view.
- Reduced-motion mode preserves state and relationship information.
- No chat/voice action is represented as successful before the authenticated backend confirms it.
