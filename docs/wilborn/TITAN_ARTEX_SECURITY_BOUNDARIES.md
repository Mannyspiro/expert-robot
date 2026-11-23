# Titan cryptographic scheme and Artex cybersecurity review

Corrected architecture: **Titan is an encryption scheme, not an AI agent.** Earlier descriptions assigning Titan a business reviewer role were incorrect and are superseded by this file.

- Merlin: business research, code proposals and workflow development.
- Artex: cybersecurity assessment and security verification, subject to actual runtime integration.
- Titan: candidate cryptographic protection for business data; not an identity, agent, business reviewer or GitHub secret manager.
- Authorized human and credential broker: credential rotation and business approvals.

## Titan cryptography qualification gate
Do not deploy Titan to protect client data or GitHub secrets until its exact specification, implementation, version, key management and security assumptions have been recovered and independently evaluated. Prefer established, reviewed AEAD encryption and managed keys for production until Titan is qualified. Never substitute an invented Titan algorithm or claim Titan encryption is active.

## GitHub secret controls
Inventory names and scopes without values. Prefer short-lived GitHub App credentials and OIDC. Rotate through a trusted provider-side broker; verify cutover and revoke old credentials. Never place secret values in chats, commits, logs or agent prompts. No GitHub secrets have been changed by this work.

## Release gates
Authentication, server-side authorization, tested encryption and key lifecycle, backup/restore, secret scanning, independent review, and real-client pilot approval. The prototype role policy is not a production security boundary.
