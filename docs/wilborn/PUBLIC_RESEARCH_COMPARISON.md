# Public research comparison checkpoint

The new `compare_public_series` function compares two already-ingested public CSV evidence objects with explicit units and caller-asserted comparability. It reports source hashes, row counts, missingness, absolute and relative mean differences, and non-causal limitations.

**Important:** A caller-supplied `comparable=True` is an assumption, not independent verification. Two different content hashes do not prove independent organizations, samples, or provenance. The result always reports zero verified claims. No synthetic business fixtures or real Wilborn records are accepted through this API.

## Next acceptance requirements
1. Add typed dataset metadata (time period, geography, population, measurement definition, units) from trusted catalogs and reject mismatched comparisons.
2. Independently check claims against original source tables and record exact citations.
3. Connect an approved public retrieval provider with network-level SSRF controls, robots/terms compliance, redirect policy and bounded rates.
4. Preserve provenance in Merlin's canonical research registry; do not create a parallel truth store.
5. Verify that production business APIs never accept research evidence as client records.

Mathematical lenses: simplex not applicable to one-dimensional mean comparisons; n-ality deferred until typed independent dimensions are available; continuum deferred because no interpolation is justified; fuzzy matching not applicable to hard provenance or authorization gates. Confirmation bias and selective evidence remain risks because the compared sources are caller-selected.
