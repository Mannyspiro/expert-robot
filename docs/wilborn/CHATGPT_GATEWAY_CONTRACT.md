# ChatGPT / Merlin integration contract — future authenticated gateway

This is a specification, not a deployed or registered ChatGPT plugin.

## Intent
ChatGPT is the conversational front door. A separately authenticated gateway checks user identity, tenant, scope and approval. Merlin researches and proposes work; Titan reviews business workflows; Artex reviews cybersecurity. All three receive synthetic or explicitly approved redacted inputs, not GitHub secrets.

## Read-only first tool surface
- `list_cases`: returns only fields authorized for the authenticated user.
- `get_case_status`: returns a permitted case's stage and service type.
- `get_service_metrics`: aggregated operational metrics subject to privacy thresholds.

Do not expose generic SQL, arbitrary file paths, command execution or arbitrary URL fetch through business tools.

## Write operations require separate gates
- `create_referral`: staff identity, explicit consent, validated schema, idempotency key and audit.
- `schedule_appointment`: availability recheck, timezone, confirmation and duplicate prevention.
- `draft_follow_up`: draft only; sending requires separate user confirmation.

## Preconditions before deployment
1. Dedicated business tenant, authenticated identities and server-enforced RBAC.
2. Encryption, retention policy, backups, restores, incident response and logging without sensitive payloads.
3. Approved ChatGPT connector configuration and actual end-to-end test.
4. Live Titan/Artex integration verification, or explicit fallback to human reviewers.
5. No production secrets or personal records in public repositories, prompts or logs.

The current loopback-only demo API must never be directly exposed to the public internet.
