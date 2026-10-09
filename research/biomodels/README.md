# Pinned BioModels carbon metabolism source (offline research)

This folder carries the unchanged **CC0** source file
`BIOMD0000000051.xml` and a copy of its upstream license.

- Source: `https://github.com/biomodels/BIOMD0000000051`
- Pinned commit: `92843fdc466e704445d491fb42b4142d4c70c3f6`
- Git blob of the XML: `e447a9b0ba35ba0156b97c07caaad94631a448cf`
- Biological context: Chassagnole et al. (2002), carbon metabolism.
- The model is **SBML Level 2 version 1**, not the Level 3 version 2
  used in our separate four-species synthetic enzyme experiment.
- The curator notes changed formula representations for ATP/AMP/NAD
  co-metabolites, and parameters not printed in the original manuscript.
  The encoded model and printed equations must not be conflated.
- Source inventory: 18 species, 48 reactions with kinetic laws, two
  compartments, 142 parameters and seven assignment rules.
- Source includes explicit symbolic time references and extracellular
  exchange; do not assume closed-system conservation.
- No biological validation, published figure replay or CACE production
  qualification follows from preserving this model.

See `scripts/qualify_offline_biomodels_0051.py` and the independent
libSBML workflow. The source hash check precedes model parsing; external
source updates must be explicitly re-pinned and independently reviewed.
