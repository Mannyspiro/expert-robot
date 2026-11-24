# Public dataset comparability gate

New `compare_with_metadata` requires typed geography, period, population, measure and unit metadata for both sources. If any dimension differs, it blocks the difference calculation and returns the mismatch list. Metadata must bind to each evidence content hash.

This improves **declared comparability**, not actual source verification: metadata are still supplied by the caller. Hash equality does not establish semantic equivalence. Real data sources may differ in sampling, denominators, methodology, seasonality, or revisions despite identical labels.

Next ranked work: extract metadata from trusted published source catalogs; validate units and periods using standardized typed vocabularies; compare original citations and denominators; build an approved retrieval connector with network-level controls and respect for source access rules.

No production client data, Artex implementation, Titan encryption, or live ChatGPT connector is added here. Merlin's public research evidence remains a separate data class from Wilborn's synthetic demo and real business records.
