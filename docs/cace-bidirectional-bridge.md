# Bidirectional CACE ↔ Expert Robot bridge

Two repository-scoped deploy keys are used without sharing their private material between execution domains.

## Forward path

Expert Robot secret → trusted dispatcher → isolated Cace-app bridge branch → free CACE ARM64 runner.

The self-hosted runner has `contents: read`, `persist-credentials: false`, no Expert Robot reverse deploy key, and no merge or promotion authority. It performs bounded static/formal qualification and uploads evidence as an artifact.

## Reverse path

A separate GitHub-hosted Cace-app publisher receives the qualification artifact. Only when `status == pass` may it use the Cace-app secret whose deploy key is scoped to Expert Robot.

Supported reverse-key secret names:

- `EXPERT_ROBOT_SSH_PRIVATE_KEY`
- `EXPERT_ROBOT_DEPLOY_KEY`
- `CACE_TO_EXPERT_ROBOT_SSH_KEY`
- `EXPERT_ROBOT_DEPLOY_PRIVATE_KEY`

The first configured value is used.

The publisher creates only `cace-return/<request-id>` in `Mannyspiro/expert-robot`, containing `.cace-return.json`, bounded qualification evidence, and the original request envelope. It does not merge anything.

## PR creation

Expert Robot's `CACE Return PR` workflow validates pass status, request schema, source SHA, source/base agreement, qualification-only authority, `promotion_authority == false`, and the evidence namespace. It then uses Expert Robot's own scoped `GITHUB_TOKEN` to create a PR.

## Base44

Base44 is treated as a discoverable external integration only. Capability discovery may report tracked Base44 markers, but this bridge does not deploy to Base44, invoke Base44 APIs, change Base44 configuration, or authorize paid resources.

The return path preserves `Capability grows, authority never expands.` Automatic merge and automatic promotion remain forbidden.
