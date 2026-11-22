# Retained browser sources → typed research intake

This fixed handoff records one real **retained-byte integrity and capture-coverage measurement** using Merlin's canonical research APIs. It produces a typed plan, measured observation, typed review, and immutable receipt in the existing `merlin-browser-research` project. It performs no acquisition, browser launch, provider/model call, scientific domain experiment, training, or capability promotion.

The operation is intentionally about source intake. It can make captured context available for later systems, technology and mathematical research without claiming that the content is true or that a research hypothesis has been tested. Parallax's missing specification and the proposed broader Xenomaths/XMG engines remain explicit open work.

## Host integration

The fixed host coordinator must authenticate the connected caller, pin the actual imported module files and the new handoff module before import, admit the original browser publication against the accepted native operation receipt, and supply the exact current program bytes. This library grants no filesystem or application authority. Its injected registry and callback are trusted host objects, never request-supplied values.

Use the already accepted private runtime's exact source modules. Keep the frozen browser runtime ZIP unchanged. The private service's own registry and configuration remain untouched: instantiate a separate canonical `MerlinRegistry` at `/var/lib/merlin-public-browser/registry`, with the existing fixed project `merlin-browser-research`. The coordinator needs bounded write access to this research registry only and read access to its pinned modules and program.

```python
from merlin.project_registry import MerlinRegistry
from merlin.browser_research_handoff import BrowserResearchHandoff

handoff = BrowserResearchHandoff(
    MerlinRegistry('/var/lib/merlin-public-browser/registry'),
    source_commit=verified_source_commit,
    program_bytes=verified_program_bytes,
    authorize=host_authorization_callback,
)
result = handoff.submit({
    'schema': 'merlin-browser-research-handoff-request/1',
    'request_id': exact_request_uuid,
    'episode_id': saved_episode_id,
    'publication_ref': accepted_same_project_publication_ref,
})
# A subsequent process only reads/verifies retained evidence:
status = handoff.status(exact_request_uuid)
```

`authorize(operation, binding)` must return exactly `True` for an admitted `read` or `write`. The coordinator verifies the authorization's actual subject, fixed operation, exact source/deployment pins, request identity and process deadline. A callback or a self-reported source commit is not independent authentication. The module has no arbitrary-path CLI, shell executor, network client or browser/model import.

The request accepts exactly four fields. It cannot choose a registry, project, program, script, URL, provider, model, shell command or deployment. The publication must identify `browser/episodes/<episode>/publication.json` in the fixed project. All consumed references must be exact version-one `ArtifactRef`s. A new operation cannot rewrite an existing immutable result.

### Dependency closure

The required existing modules are:

| Module | Purpose |
| --- | --- |
| `merlin.artifact_ref` | Exact project/path/version/digest references |
| `merlin.project_registry` | Canonical persistent bytes, version history and readback |
| `merlin.scientific_loop` | Measured `Observation` and prediction comparison |
| `dot_ai_os.bridge` | Existing canonical JSON/digest helpers |
| `dot_ai_os.research_protocol` | Typed plan/review creation and append-only persistence |
| Both existing package `__init__.py` files | Normal package imports |

These imports use Python standard-library dependencies only. No new browser or model package is required. The initial operation does not instantiate `RegistryBranchSession`: future admitted candidate evaluation can add its existing branch/recovery modules and real host approval/lease callbacks. Source intake by itself is not a completed scientific branch or a qualified RSI candidate.

## What is recorded

1. A canonical intent binds the exact request, program SHA-256/version, source commit, handoff-module SHA-256 and one actual observation timestamp.
2. The exact program bytes are retained. A `merlin-research-plan/1` is persisted **before** the capture-body measurement. It states that the original acquisition predates this new source-intake plan.
3. Every declared saved file, plus publication, episode manifest and browser handoff, is resolved and re-hashed through the canonical registry. The operation checks complete inventory, exact byte lengths, event/capture/action bindings and the four capture artifacts. It preserves full acquisition URLs, including HTTP and queries.
4. The measurement reports exact verified input counts/bytes, capture counts, usable capture counts and failed action counts. It separately preserves **reported** context-bridge intake counts; optional bridge records are not resolved or verified by this measurement. A locally usable capture has its own successful action, 2xx document status and nonempty UTF-8 rendered text. This definition says nothing about scientific correctness.
5. A typed review compares two predeclared expectations: complete retained integrity and the presence of a locally usable capture. Zero usable captures produces a retained negative review. Missing/corrupt/contradictory evidence produces a retained failure and requires reconciliation.
6. An immutable result links the exact program, plan, raw measurement and review. Domain execution remains `not_run`; model/browser calls and model cost remain zero; qualification and promotion remain false.

The four mathematical lenses are explicitly assessed in the typed plan. They are not applicable to this finite exact-inventory operation, with a reason, invariant/test and unresolved limits for each. This is not an assessment of their usefulness in a future domain experiment.

The original browser publisher remains responsible for its complete browser-event validation; the fixed native coordinator remains responsible for execution admission, stopped-worker proof and process isolation. This handoff measures retained-byte identity and capture bindings. It does not independently attest that Chromium ran or validate website authorship/content.

## Durability and limits

Handoff records use `research-handoffs/<uuid>/`; typed records use the existing `research/browser-intake-<uuid>/` protocol paths. The canonical registry is the only evidence store. A cooperative advisory lock serializes handoff writers; it is not a security boundary against trusted code that ignores the protocol.

A completed repeat or fresh-process status call re-verifies retained plan, program, measurement, review and source references, then returns the exact original result. It creates no new plan version and does not run another measurement. An intent without a final result returns `reconciliation_needed`; even identical submission cannot repeat the operation implicitly. Partial artifacts stay retained. There is no automatic recovery callback or remote retry in this addition.

Admission ceilings are one episode, eight captures/actions, 320 declared files, 12 MiB episode evidence, 256 KiB per handoff JSON record and 16 KiB request bytes. The fixed host coordinator must also enforce its process deadline, memory/disk headroom and one-operation concurrency policy. The module does not change existing browser/model budgets.

## Verification

The focused unit tests use real canonical registry and research-protocol modules over synthetic retained records. They cover exact restart replay, corrupt original/output bytes, different request/source bindings, interrupted publication, cross-project references, HTTP/query preservation, wrong action/URL lineage, authorization and bounds. They do not execute a browser or claim native acceptance.

`tests/browser_research_wire_compatibility.py` additionally feeds the **actual frozen browser recorder/publisher** using its fake-renderer fixture into the real typed handoff. It then starts a separate isolated Python process, loads the exact handoff file with the unchanged private modules, reopens the registry, and verifies the same retained result through `status`. This checks wire compatibility and process restart using HTTPS, query-bearing HTTPS and HTTP captures. It is still a synthetic local check, clearly labeled as such.

The focused test command from the repository root is:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=python python -m unittest discover -s tests -p test_browser_research_handoff.py -v
```

Exact local validation output, input/source hashes and the compatibility report are retained under `docs/evidence/merlin-browser-research-handoff-20261121/`. The compatibility script's path arguments select source fixtures for local verification; they are not exposed as production API inputs.

Native integration and connected invocation remain pending until an actual accepted host operation retains their evidence. Installing or scheduling these files does not establish that outcome.
