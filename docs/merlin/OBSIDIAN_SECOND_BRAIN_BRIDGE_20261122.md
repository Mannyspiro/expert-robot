# Merlin second brain: Obsidian-compatible local vault bridge

**Status:** review-only source candidate, not production-qualified, not a model-memory or external app integration.

## Why this implementation

The user identified "Obsidian second brain" as a reference for improving Merlin. We confirmed multiple *distinct* publicly licensed repositories, but did not verify that any one of them is the project shown in the original YouTube Short:

- [JSand15/obsidian-second-brain](https://github.com/JSand15/obsidian-second-brain/tree/400349c87c01d6468277d7ad32091496eedd9170): MIT, PARA/Inbox/Decision/Reading notes and capture UX. **Concept reference**, not cloned.
- [s2b-dev/smart-second-brain](https://github.com/s2b-dev/smart-second-brain/tree/93fb0ffe5b815c355bf063891858ec8ae676c579): MIT, Obsidian plugin with semantic search/graph/embeddings. **Research inspiration**, not cloned.
- [alebellotta/local-second-brain](https://github.com/alebellotta/local-second-brain/tree/95493e2e8a661c2b91533f2a50ab96c74b7d79c6): MIT, local retrieval/knowledge. **Research inspiration**, not cloned.

The main Obsidian app is not open source and is not vendored. **No third-party source code is copied here.** The bridge is an original Python implementation using only the standard library. It is a candidate local format adapter; it does not require the Obsidian application or plugin API, external model or browser.

## Exact intended behavior

The operator explicitly points Merlin at an existing local vault. Merlin can then index ordinary Markdown files, Obsidian wikilinks, Markdown links, simple frontmatter tags/aliases, inline tags, ambiguous/unresolved links, backlinks, and content hashes. It exposes bounded lexical note search with paths, line numbers and SHA-256 source identity.

- Read-only: never writes Markdown, Obsidian settings, SQLite memory, MerlinRegistry, MerlinKnowledgeGraph or event outbox.
- No cloud: never sends vault text to OpenAI, Z.ai, model context, GitHub, telemetry or any network service.
- No automatic permanent memory: this is an *ephemeral discovery index*. Graph edges are note links, **not verified claims**. User-approved promotion is a separate future capability.
- Safe boundaries: 2,000 notes, 512 KiB per note, 32 MiB cumulative source bytes per inventory pass by default; verified search rereads source files and imposes independent source-content budgets; no hidden/.obsidian or .git paths; symlink directories and files plus hardlinks are excluded or denied; no-follow descriptor-based file open; bounded UTF-8 parsing; fail closed on changed note content during a search. Missing source coverage is shown as partial both in inventory and search.
- CLI display: structural metadata by default. Note-line snippets only when explicitly requested.
- Scoped platform: requires Python 3.10+ and POSIX-style openat/O_NOFOLLOW support. Windows portability, OS-level sandboxing and actual Obsidian application runtime are **not qualified**.
- No embeddings in v1. The default lexical search is a simple per-line match. An explicit optional SQLite FTS5 **memory-only** index handles terms across paragraphs with deterministic lexical BM25 ranking; it is **not embedding-based semantic search** or a validated improvement in real retrieval quality. FTS5 requires SQLite compiled with FTS5 and is bounded to at most 8 MiB source content per temporary index.

## Run locally

From the Merlin repository root, with a user-owned local Obsidian vault:

    python3 -B scripts/merlin_obsidian_vault_cli.py --vault /path/to/vault
    python3 -B scripts/merlin_obsidian_vault_cli.py --vault /path/to/vault --search "local model"
    python3 -B scripts/merlin_obsidian_vault_cli.py --vault /path/to/vault --search "local model" --include-snippets
    python3 -B scripts/merlin_obsidian_vault_cli.py --vault /path/to/vault --search "local model" --mode fts5

All requests are explicit. The CLI neither creates a vault nor watches one in the background. On partial evidence (omitted notes), inventory mode uses a nonzero exit code, and callers should retain omissions instead of claiming a complete index. Search results are metadata-only by default; opening raw notes for model context requires a distinct permission decision.

## CI and measured acceptance

The tests in tests/test_merlin_obsidian_vault_bridge.py cover:
1. Wikilinks, relative Markdown links, aliases, backlinks, tags, YAML-lite properties, skipped fenced links.
2. Source hashes and line-number retrieval, explicit snippet output.
3. Hidden directories and symlink escape denial.
4. Hardlink and invalid UTF-8 denial.
5. Byte, per-note and note-count limits.
6. Ambiguous titles failing closed instead of picking the wrong note.
7. Absolute/external/traversal targets not followed.
8. No persistent memory or vault mutation.
9. Source changing between indexing and content read rejected.
10. Invalid budgets and search requests.
11. Aggregate byte budget enforced before an oversized note is read.
12. Partial scan omissions are propagated to lexical search results.

Both the 12-case note-graph suite and separate eight-case memory-only FTS5 suite are added to scripts/run_merlin_offline_ci.sh with distinct counted results and exact source revision. The initial 10-case version passed full independent CI (282 Python, 33 native C++ tests; pipeline 3101351476). The first 12-case revision failed in pipeline 3101355275 because the changed bounded-read method had an outdated fault-injection mock signature; that failure is preserved and the mock was corrected at 1cbb3ba. The subsequent full exact-source run is independent evidence; local prototype tests alone do not establish release acceptance.

## Scientific and security interpretation

Premise: local Markdown link discovery adds a source-transparent retrieval option without new privileged models or remote dependencies. Cheapest discriminating test: verify actual note identities/link coverage and negative controls on one exact source, then test a user-approved held-out retrieval corpus against Merlin's existing registry query baseline.

- **N-ality (applied):** keep note identity, link topology, permission, source coverage, retrieval correctness, memory persistence and model inference as separate axes.
- **Simplex (deferred):** no calibrated resource/correctness Pareto frontier is measured. Weighting memory quality against safety cannot override permission gates.
- **Continuum (deferred):** real latency or retrieval-quality distributions need repeated representative measurements.
- **Fuzzy (not applicable to authorization):** the lexical rank heuristic may guide result ordering, never automatically validate facts or approve memory promotion.
- **Falsifiers:** vault content or settings modified; external symlink bytes read; ambiguous link silently resolves; source change escapes the hash gate; current offline CI regresses; note content transmitted without consent.

## Ranked next build steps

1. Verify the final exact-source 12-case vault plus eight-case FTS5 suites alongside the existing 272 Python/33 C++ baseline, preserve every failure, and verify no temporary/on-disk index leaks.
2. Separate note ingestion from canonical MerlinRegistry/ArtifactRef and MerlinKnowledgeGraph writes: only user-approved, provenance-checked promotion can create durable approved graph records.
3. Benchmark optional memory-only SQLite FTS5/BM25 against the per-line lexical baseline on a *held-out* evaluation corpus; measure recall@k, latency/RSS, source-citation correctness and privacy before promoting the experimental engine to default.
4. Design Studio UI vault browser, explicit permissions and revocation; test with an actual rendered browser, keyboard, restart and offline transitions.
5. Only after vault correctness and privacy gates, consider opt-in embeddings with locally available weights and measure output quality. Do not infer general capability from a graph visual.

The authoritative Merlin master plan v6 remains unchanged, including ten tracks, 37 original tasks and eight extensions. This branch is intentionally separate from PR #222 and cannot be merged into production without independent review.
