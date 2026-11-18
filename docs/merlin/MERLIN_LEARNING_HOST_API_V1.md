# Merlin Learning research host API

The host can compose the canonical course evidence reader and optional fixed Titan lab with its existing verified-identity resolver. `LearningResearchAPI(platform, evidence_service, identity_resolver, lab_bridge=None)` dispatches only the four POST operations below. It does not create an identity provider, a tenant, enrollment, a new evidence store or a public listener.

Inject the adapter through `app.make_handler(..., learning_research_api=api, learning_identity_resolver=resolver)` or `app.serve(...)` with the same resolver. The host adopts the adapter's explicitly supplied canonical platform/registry when these are absent; mismatched explicitly supplied objects are rejected. Tenant/project provisioning belongs to the existing services, and matching lab/evidence provisioning is checked before use. The loopback host and its existing origin/body limits remain in force.

| POST path suffix after `/api/learning/courses/{course_id}/research/` | Operation |
|---|---|
| `sources` | Owner/tenant-admin attestation of exact reviewed source snapshots and optional declared conflicts. |
| `evidence` | Enrolled learner's course/version-scoped lexical source retrieval. |
| `lab` | Optional injected fixed Titan structural lab with pre-run prediction and run identity. |
| `submit-lab` | Optional injected lab receipt submission for pending review, with a reflection. |

All operations require exact `course_version` and `manifest_sha256`. Their operation-specific fields are explicitly allowlisted by the adapter. Body identity, tenant, role, project, alternate source revision, verifier configuration and arbitrary operations are rejected. The adapter resolves Actor solely from host-authenticated headers through the injected resolver; it never decodes a token independently or trusts caller identity claims. An actual deployment must configure a maintained verifier and the relevant issuer/audience/JWKS policy through the existing host authentication contract.

Missing configuration returns503, invalid credentials401, denied scope/role403, changed binding409 and malformed requests400. Operational/integrity failures return a bounded generic error; token/source/private exception content is not echoed. Unknown paths do not dispatch. Research requests use strict JSON (duplicate keys/nonfinite values rejected), a 131,072-byte body ceiling, bounded depth/node count and a bounded response. Malformed length/body and nested-source fields produce generic bad-request errors; internal missing-artifact failures remain distinguishable service errors. The exact status/redaction behavior is covered by focused regressions.

The tests use real temporary LMS/registry/source services, an explicitly synthetic identity resolver and a real loopback HTTP server. They compile the actual nested host POST/origin methods from app.py for narrow dispatch integration without importing/seeding unrelated application components. This is neither full application startup nor live institutional SSO. Existing focused LMS/Titan/retrieval tests remain part of the regression shard.

The implementation provides an injectable host interface. An institutional pilot still needs actual issuer/tenant provisioning, instructor review, accessibility/rights/retention decisions and operational acceptance. No real student data, private chat/Drive corpus, new provider, public deployment, grade/mastery, cryptographic primitive or independent qualification is added. Rollback is a source revert while preserving existing canonical stores. Master-plan history and the exact test checkpoint retain the measured scope.
