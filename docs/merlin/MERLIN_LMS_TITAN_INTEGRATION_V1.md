# Merlin Learning and Titan research labs

This slice connects the existing tenant-scoped LearningPlatform to Titan's fixed
structural protocol lab using Merlin's canonical registry, hypothesis ledger and
knowledge graph. Titan is encryption/protocol research; the historical compute
fabric naming is a separate candidate. The lab performs no cryptographic
operations and does not award mastery, a security claim or qualification.

`titan_course_manifest(source_commit)` returns a fresh source-pinned course with
three objectives: distinguish evidence classes, reproduce public structural
fixtures and propose a transfer/counterexample test. `create_titan_course` creates
an instructor-owned draft. Publication still requires the existing separate
reviewer policy; the builder never publishes it automatically.

The host constructs `LearningLabBridge(platform, evidence_recorder,
tenant_projects=..., source_commit=...)`. Actor identity and distinct per-tenant
project provisioning come from the trusted host. Request bodies must not create
Actors, project mappings, source identities or verifier credentials.

An enrolled learner calls `run_titan_lab` with an exact published course version,
manifest SHA-256, lesson, run ID and a pre-run prediction. Only the fixed
`titan-structural-model-v1` lesson task is supported. Its canonical report records
the course/learner binding, source file and model/vector identities, scientific
frame, all four representation applicability decisions and explicit limitations.
The LMS stores run reservation/receipt links; artifact bytes and evidence stay in
the existing canonical stores. Identical replay resolves one version/evidence;
changed run identity and tampered bytes/provenance are rejected.

`submit_lab_assessment` re-resolves that exact evidence and delegates to the
existing assessment queue. Optional version/hash preconditions in
`LearningPlatform.submit_assessment` are checked inside its write transaction,
including replay. A course revision cannot silently relabel lab evidence. Work
remains pending calibrated independent human review; neither successful lab
execution nor an instructor's content publication certifies learner mastery.

Canonical blob publication now uses per-writer staging files. Graph node/edge
insertion serializes the immutable identity check and insertion in one write
transaction. These repairs support concurrent evidence producers across Merlin,
not a separate LMS-only evidence store. Conflicting identities remain errors.

`run_synthetic_titan_demo(root, source_commit)` is a repeatable integration fixture
using synthetic teacher/reviewer/learner actors and dedicated local databases. It
preserves a transcript/predictions ArtifactRef before the lab, exercises source
citations, publication, enrollment, evidence, pending assessment and recommendation,
and supports exact replay. Its synthetic reviewer is not a faculty attestation.
The five public fixtures are not held-out evidence of learning efficacy or
cryptographic conformance. Test-only signed CACE receipts remain synthetic; no
production verifier is provisioned or inferred.

This library slice does not provide institutional SSO/LTI rollout, public hosting,
real student-data onboarding, a cipher/KEM implementation, live independent CACE
qualification or educational-efficacy evidence. Those remain separate production
gates in the master plan. The running private Merlin service and its state are
outside the isolated integration validation workspace.

## Host-configured HTTP adapter

Pass the provisioned bridge as `learning_lab_bridge` to `serve` or
`make_handler`. Both course and lab routes use the bridge's platform. A
separately supplied platform must be the same instance. Provision the per-tenant
projects on the host before enabling the adapter. The existing learning session
resolver supplies the actor on every request.

POST to `/api/learning/courses/{course_id}/titan-lab/run` with
`course_version`, `manifest_sha256`, `lesson_id`, `run_id` and `prediction`.
POST to the sibling `submit` route with the same four binding fields plus
`submission_id` and `reflection`. Use the original identifiers and content for
retries. The run returns the canonical receipt and submission remains pending
review. A stale course binding returns HTTP 409. Unconfigured lab access returns
503. The application-level test uses synthetic host identities on loopback.
Institutional identity-provider and LTI acceptance remain open.
