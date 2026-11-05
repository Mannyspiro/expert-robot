

## Merlin science and mathematics atlas

A responsive research atlas is being developed under `apps/merlin-web/`. It maps established disciplines, interdisciplinary branches, historical theories and prospective research spaces. The source and ingestion contracts live under `research/science/`.

- Platform scope and historical/philosophical method: `docs/MERLIN_SCIENCE_HISTORY_PHILOSOPHY_PLATFORM.md`
- Discipline ontology: `research/science/discipline-taxonomy.v1.json`
- Public/open source directory: `research/science/source-registry.v1.json`
- Rights-aware intake contract: `research/science/ingestion-contract.v1.json`
- Primary-source pioneer notes: `research/science/reading-notes/`
- Google Books public catalog discovery: `scripts/merlin_google_books_discover.py`
- Rights-aware source staging: `scripts/merlin_science_intake.py`
- Bounded source-dossier to Merlin runtime bridge: `scripts/merlin_science_ideonomy_packet.py`

The atlas is a read-only view. Source text is ingested only when public-domain or open-license status is verified for the exact item/edition; preview-only and restricted works remain metadata and links. All model-produced historical summaries and ideonomy proposals remain unreviewed candidates until human/domain review. Empirical claims require empirical evidence; mathematical claims may be sent to Lean where formalization is appropriate.

The current web app is a static first release and does not yet include a persistent production database or authenticated remote ingestion API. Its deployment is gated on Vercel team authorization and preview review. The canonical research and proof boundaries remain in the existing Expert Robot runtime, C++ research engine, Lean and evidence ledger.
