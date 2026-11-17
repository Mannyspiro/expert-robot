# Hermes Teacher v1

The second Hermes is an opt-in source-bound reviewer and teacher, not a replacement for the independent CACE service. It has a dedicated `merlin.hermes.teacher.task` lane in the existing outbox, uses the existing HermesWorker and stage journal, and emits Hermes telemetry with a distinct teacher agent ID. Topic separation is routing, not OS or database access control.

Runtime admission must authenticate the complete work inventory, author IDs, reviewer, repository commit, corpus partition, approvals and resource lease. IDs asserted by a model are not proof of independence. Each supplied artifact and acceptance criterion needs exactly one review; assessed text must cite exact byte ranges and matching quotes. V1 is bounded UTF-8 review of a supplied manifest, not proof that all historical work, binary assets or every runtime entrypoint was reviewed.

The teacher cannot review a revision it helped author. Its recommendations cannot set verification/qualification/promotion authority. It may produce source-bound, content-addressed lesson proposals for both coders, including applicability, counterexamples and regression suggestions. Heldout reviews cannot emit shared lessons. Proposals are durable in the existing journal/result, not automatically adopted into prompts, model weights or a canonical curriculum.

Checkpoint/replay binds exact task, input bytes and reviewer configuration. Generated reviews survive acknowledgement retries. In-flight provider calls are not exactly-once. A live reviewer must be an approved isolated adapter; this code does not provide OS isolation or launch a model.

The non-dispatched CACE handoff lists exact subject artifacts and excludes the author/reviewer identities. A trusted downstream coordinator must enforce that policy, choose the correct proof/artifact verification scope, and use existing independently authenticated CACE configuration. The handoff is not a signature, authorization or verification receipt.

The shared mathematical policy in `MERLIN_MATHEMATICAL_METHODS_V1.md` is carried by `scientific_loop_contract()` in the teacher's request. Conditional Parrondo-style switching, information theory and other applicable mathematics support hypothesis formation and measured improvement, never self-approval.

Continuation note: five retained source blobs from the interrupted teacher implementation were uploaded before this turn. They are published by identity in this checkpoint. The prior working session reported 128 focused tests, but its complete working directory/logs are not present in the current runtime. That result is historical, not a rerun of this combined commit. The new mathematical primitives and scientific-loop tests have their own current evidence; the full expanded gate remains pending.
