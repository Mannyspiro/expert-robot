# Titan / Artex roles for Wilborn operations

Status: code-level role contract only. Neither a live Titan nor a live Artex runtime has been invoked or integrated. No GitHub repository secrets have been changed.

- Merlin proposes code and research, limited to synthetic business data.
- Titan reviews business requirements, processes and operational risks; recommends secret lifecycle changes but never receives secret values.
- Artex reviews cybersecurity, dependencies, trust boundaries and tests; does not receive credentials or private customer data.
- Human-approved credential broker handles secret rotation, with least privilege and auditable provider-side operations.

## GitHub secret hardening checklist
1. Inventory secret names/scopes/consumers without displaying values.
2. Prefer GitHub Apps and OIDC over long-lived personal access tokens.
3. Create replacements in an approved secret manager, never in chat or repository files.
4. Use provider encrypted-secret APIs from a trusted broker, test dependent workflows, then revoke old credentials.
5. Review third-party app installations, branch protection and Actions permissions.
6. Scan history for exposures; rotate confirmed compromised credentials.

## Release gates
Authentication, server-side authorization, encryption, backups, restore tests, secret scanning, security review, and real-client pilot approval. No public repository may contain client PII or credentials. This prototype policy does not enforce GitHub or production permissions.
