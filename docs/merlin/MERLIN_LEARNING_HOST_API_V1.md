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

To run the evidence reader from the standard `python -m merlin.app` entry point, configure `MERLIN_REGISTRY_ROOT` and `MERLIN_LEARNING_DB_PATH` to point to the existing registry and course database. Set `MERLIN_LEARNING_RESEARCH_TENANT_PROJECTS` to a JSON object mapping each authorized tenant ID to its own existing project ID. For example, `{"example-college":"example-college-sources"}` illustrates the shape. Use identifiers issued by the deployment owner. Merlin checks for existing LMS tables before opening stores that could initialize the same file.

The host uses its existing OIDC issuer, audience, JWKS URL and algorithm configuration. Install the authentication dependency recorded in `requirements-merlin-auth.txt`. An absent or blank tenant mapping keeps automatic composition disabled. A configured map enables the curation and evidence routes. Lab execution and submission require an explicitly injected `LearningLabBridge`.

The startup suite launches the full application against a disposable course and registry, retrieves evidence, terminates the process and reads the same pinned sources after restart. The optional `scripts/merlin/validate_learning_oidc_startup.py` profile runs the normal module entry point against a loopback issuer using the pinned PyJWT source. Its receipt records byte-level citation checks, authentication results and process exits. The institutional pilot still requires the deployment owner's issuer and tenant settings, instructor review, rights, accessibility and retention decisions.
