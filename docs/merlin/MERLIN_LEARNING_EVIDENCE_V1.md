# Course-scoped evidence reader

Merlin Learning can now retrieve evidence from exact curator-reviewed snapshots through the existing DotContextBridge and MerlinRegistry. Titan's course is the synthetic integration example. This service returns source excerpts and review states; it does not generate answers, establish source truth, or award grades.

## Host integration contract

The host supplies an authenticated `Actor`, an existing `LearningPlatform`, an existing `MerlinRegistry`, and a distinct provisioned registry project for each tenant. Request data cannot choose the actor, tenant/project mapping or source references used in retrieval.

`LearningEvidenceService(platform, registry, tenant_projects=..., namespaces=...)` exposes:

* `provision_course_sources(curator, course_id=..., course_version=..., manifest_sha256=..., sources=..., conflicts=...)`: the course owner or tenant administrator attests review of explicit record/source ArtifactRef pairs. The published resource URL and optional source version must match. A canonical source manifest is frozen for that exact tenant/course/version/digest; changed curation requires a new course version.
* `retrieve(learner, course_id=..., course_version=..., manifest_sha256=..., query=..., lesson_id=None, limit=6, budget_bytes=16000)`: an enrolled learner reads only the approved course sources, optionally restricted to the selected lesson's source IDs. Permission, course identity and integrity checks precede ranking and byte-budget selection.

The existing context bridge's optional `pinned_records` parameter resolves exact historical metadata and source versions. It is a host scoping primitive, not an authorization service. Existing unpinned callers retain their prior behavior. Later ingestion cannot silently change a course's evidence.

Each citation carries record/source references, original UTF-8 byte offsets, excerpt digest, text and provenance metadata. Callers must render source text and annotations as untrusted data. Lexical scores are ordering hints with no permission, truth or probability meaning.

| State | Meaning |
|---|---|
| `evidence_available` | Reviewed source excerpts matched the lexical query within the response budget. |
| `abstain` | No relevant approved evidence was found, or the budget excluded all citations; the reason distinguishes these cases. |
| `requires_review` | A matching source belongs to an explicit curator-declared conflict group. Member references survive excerpt truncation; members outside an explicit lesson scope have a visible omission count and reason. |

Conflicts are reviewed annotations, not automatic semantic contradiction detection. A budget too small for required metadata fails explicitly. Retrieval never updates mastery, qualification or promotion authority. Source ingestion, origin authentication, institutional session wiring, public deployment and retention policy are separate host responsibilities.

## Frozen software evaluation

The repository fixture `tests/fixtures/learning-evidence-eval-v1.json` was frozen before the first reader evaluation. Its SHA-256 is `b6b6b28f3aaea631c78fc7e06a23ca0d5d4342cfc065a3887f451f18a942b018`. It contains four original synthetic sources, one development case and three separately identified evaluation cases. All cases are public and nonblind; this is a software contract check, not a held-out accuracy or educational-efficacy study.

`run_synthetic_evidence_demo(root, source_commit)` runs the real platform, enrollment, source curation and reader. It persists a pre-run protocol, each raw candidate response, the independent byte-oracle grading result and a canonical report. The protocol binds the runtime reader, bridge and evaluator file hashes. Failed candidates remain recorded. The grader checks against original frozen bytes and host-owned expected scope and references; a self-consistent forged excerpt/hash pair cannot earn credit.

The selected regression suite also covers enrollment/tenant/course boundaries, historical replay, unrelated corrupt sources, malformed references, original UTF-8 citation bytes, declared conflict retention and concurrent curation. It does not establish general retrieval quality, source completeness, independent verification, cryptographic security or real student learning.

## Repairs and prevention

| Defect family | Observation and cause | Regression and prevention |
|---|---|---|
| Curation freeze race | A synchronized pre-fix local run of two different curations returned one error and one success but published two versions. The history check and append were separate cooperating operations. | A nonblocking cooperative `flock` on the existing registry database descriptor bounds the history/check/append/readback section. Forced concurrency now leaves one frozen version; exact replay remains valid. No new store or lock file is created. Unrelated direct writers bypassing this protocol remain outside that guarantee. |
| Budget hides conflict context | Source review found excerpt selection alone could omit a conflicting source. This was a design finding, not a production incident. | The bridge exposes matched record identities before excerpt truncation. Conflict references are retained independently of chosen excerpts, with explicit lesson omissions and a metadata budget floor. |
| JSON type strictness | Separate review reproduced the grader accepting Boolean `true` as integer version `1` through Python equality; the same raw-dictionary comparison pattern existed in pinned metadata. | Compare canonical JSON identities and parse nested ArtifactRefs with strict types. Boolean-as-version regressions cover the reader and evaluator; no source fixture change. |
| Citation grader omits scope | Separate coder review found copied valid citations could pass without the expected course binding and source manifest. | The grader requires host-owned expected scope and manifest reference in addition to exact original-byte citation checks; wrong or missing scope has negative regressions. |

Rollback is a source-level revert to the parent implementation. Existing course manifests, canonical context versions and LMS schema remain intact. No production service mutation is required for isolated validation. The master plan and exact OCI receipt record what was actually run.
