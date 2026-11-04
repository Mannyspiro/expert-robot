# Real-World Equation Atlas — Merlin Research Package

This directory contains the research prompt, a 100-entry initial atlas, Merlin context, a first Math Kung Fu lesson, and a JSON Schema for normalized entries.

## Files
- `PROMPT.md` — complete Merlin research instruction.
- `ATLAS_001-100.md` — initial 100-entry atlas and cross-domain analogies.
- `MERLIN_CONTEXT.md` — relevant project context, XMG, pipeline, and constraints.
- `LESSON_001_OPTIMIZATION.md` — first visual-intuition lesson.
- `equation-entry.schema.json` — normalized machine-readable entry schema.

## Status
This is a curated starting atlas, not an exhaustive literature review. Entries are canonical equation families with brief application notes. Each entry still requires domain-specific sources, variable/unit completion, assumptions, validity regime, validation evidence, and evidence-status adjudication before being promoted as a Merlin-verified knowledge object.

## Next research iteration
1. Enrich entries with primary sources and claim-to-source citations.
2. Add complete variable/unit/assumption metadata.
3. Implement dimensional checks and symbolic/numerical test templates.
4. Add benchmark datasets and reproducible experiment manifests.
5. Add XMG frame/transform metadata where geometric representations are relevant.
6. Create lesson modules with diagrams, equivalent representations, and short recall tests.
7. Submit evidence-backed changes as a separate virtual PR for independent review.
