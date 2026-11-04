# Merlin.Automation

UiPath implementation scaffold for Merlin. This is the Windows Studio project track; Studio Web uses the companion API-first workflow contracts in `docs/merlin/STUDIO_WEB_WORKFLOWS.md`.

## Current status

- Project structure and shared contracts: scaffolded in Git.
- XAML entry point and workflow shells: included as starter workflows.
- Archive intake helper: included as a reviewed PowerShell source file; run only on a test archive first.
- Studio package restore, XAML validation, and runtime execution: **not yet verified** because Studio is not installed on the target Windows machine.
- No credentials or machine-specific settings are included.

## Open in UiPath Studio

1. On a supported Windows machine, install UiPath Studio Community and sign in.
2. Clone this repository and check out `feat/merlin-uipath-community-mvp-20261104`.
3. Open `uipath/Merlin.Automation/project.json` in Studio. If Studio requests a project conversion or regeneration, accept the Studio-generated manifest and commit that generated file separately.
4. Restore packages using Studio's package manager. Keep package versions compatible with the installed Studio release; do not copy package versions from an unrelated machine.
5. Open `Main.xaml`, then run the validation workflow against the sample task under `Data/examples/`.
6. Run archive intake against a disposable test archive. Confirm the manifest and receipt before using real project archives.

## Project layout

- `Main.xaml`: bounded dispatcher entry point.
- `Workflows/`: small, reusable workflow shells.
- `Config/`: non-secret configuration and schema.
- `Data/`: task and evidence receipt contracts.
- `Scripts/`: fixed helper scripts invoked with explicit arguments.
- `Data/examples/`: harmless test task.

## Execution contract

Only the named operations in `Config/operation-allowlist.json` may be routed. Unknown operations fail closed. GitHub starts read-only. The initial write ceiling is feature-branch and draft-PR preparation only, with explicit human approval. Merge, production deployment, permission changes, credential changes, and destructive operations remain unavailable to the robot.

**Invariant:** capability grows, authority never expands.
