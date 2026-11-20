# Bounded request intake

`ProductionJobInbox` lets an authenticated host persist a dot-originated work request in Merlin's existing canonical registry. The request remains `pending_operator_review`. Intake does not invoke coders, enqueue Hermes tasks, call OCI, execute code, verify evidence or promote a capability. This is a tested local intake component, not an installed production service.

```python
from merlin.project_registry import MerlinRegistry
from dot_ai_os.job_inbox import ProductionJobInbox

inbox = ProductionJobInbox(
    MerlinRegistry("./state"),
    namespaces=("merlin", "rsi"),
)
result = inbox.submit(
    principal=authenticated_host_subject,
    idempotency_key=unique_opaque_request_key,
    request={
        "namespace": "merlin",
        "objective": "Compare a source-grounded retrieval candidate",
        "source_commit": exact_source_commit,
        "source_refs": selected_exact_context_refs,
        "acceptance_criteria": ["Exact citations resolve", "No namespace leakage"],
        "max_cost_usd": 0,
    },
)
status = inbox.status(
    principal=authenticated_host_subject,
    request_id=result["request_id"],
)
```

The host must supply `principal` from authenticated connection state, separately from model-controlled request JSON. This class does not authenticate a user. A future write-scoped MCP wrapper must preserve that boundary; exposing a `principal` tool argument would defeat caller isolation. Only a principal digest is stored. Status accepts one exact request ID and does not list the registry or return source text.

The constructor requires an explicit namespace allowlist and an existing project. It never calls the bridge's project initializer. Every source reference is resolved through the scoped context bridge, including exact project, source path, namespace, version and digest checks. Sources from several allowlisted namespaces may support one request. A narrower later policy can reject status access to a request containing a revoked source namespace.

Bounds are fixed at 20 unique source references, 128 KiB total referenced context, 16 KiB for the complete serialized request envelope, 2,000 objective characters and 20 bounded acceptance criteria. The only admitted budget is integer `max_cost_usd=0`. Unknown fields, including caller-supplied approval, execution, verification and promotion fields, are rejected. An accepted budget declaration does not itself enforce provider billing.

Each idempotency key is globally unique within the project. Identical principal, payload and key replay the same immutable request and response. Reusing a key for another principal, objective, source, criterion or budget conflicts. Use opaque random keys, rather than recurring labels such as `request-1`.

A key-binding artifact is committed before its principal-scoped request artifact. If the host stops between those local writes, identical retry can complete the request; the key cannot be reassigned meanwhile. Both artifacts use the canonical registry's append-only version history. Multiple versions or invalid bindings fail closed. Status rechecks the saved envelope and source references; it does not inherit a previous integrity check after source tampering.

Linux `O_NOFOLLOW` advisory locking serializes cooperating submissions. The existing `dot-dual-coder.lock` filename is shared with the two-coder workflow to avoid canonical blob temporary-file races. Intake waits at most five seconds by default, then raises `InboxBusy`; retry the identical request later. This lock does not protect against unrelated writers or a compromised host, and canonical SQLite/blob durability remains the underlying storage guarantee.

Accepted and read-back results explicitly retain `execution_state=not_dispatched`, `approval_state=not_requested`, `qualification=false` and `promotion_authority=false`. Explicit operator review and the existing Hermes, MCFC and independent CACE policies remain later gates.

Focused validation covers 22 cases, including concurrent identical requests, concurrent cross-principal key collisions, interrupted local writes, idempotent replay, changed requests, source tampering, namespace isolation, budget bounds, unsafe lock paths and absence of claim/qualification mutations. No external service was invoked by those tests.
