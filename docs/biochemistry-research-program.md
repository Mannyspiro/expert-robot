# Biology and Biochemistry Research Program for Expert Robot / CACE
**Checkpoint:** 2026-10-09. **Status:** reading roadmap and synthetic in-silico experiment, not wet-lab evidence, trained model, or CACE production feature.

## Scientific ontology and learning order

1. **Chemical foundations:** stoichiometry, isotopes, electrons, valence, stereochemistry, aqueous acid-base equilibria, pH/pKa, Gibbs energy, temperature, concentration and units. Check atom count, elemental balance, conserved mass, charge and chemical potential before accepting any modeled reaction.
2. **Biomolecules:** carbohydrates, lipids and membranes, amino acids and peptides, cofactors, nucleotides, DNA/RNA, proteins. Separate chemical identity, bond graph, conformational ensemble and measured activity.
3. **Enzymology:** elementary steps, substrate binding, saturation kinetics, reversible inhibition, Michaelis–Menten assumptions, allostery, temperature/pH effects. Keep experimentally fitted constants and assumed constants distinguishable.
4. **Cellular biology:** organelles, membrane transport, metabolism, glycolysis, TCA and oxidative phosphorylation, gene expression, translation, folding, quality control, cell cycle and signaling.
5. **Quantitative modeling:** mass-action and Michaelis–Menten ODEs; stoichiometric matrices and left nullspaces; identifiability, sensitivity, parameter uncertainty, stochastic chemistry, reaction-diffusion PDEs, multiscale linking.
6. **Biophysics:** protein structural evidence, conformational dynamics, free-energy landscapes, electrostatics, statistical mechanics, molecular mechanics and force-field validation. A static protein prediction is not an observed trajectory or enzyme mechanism.
7. **Experimental design and inference:** literature replication, preregistration, blind holdouts, model criticism, measurement provenance, uncertainty accounting and counterfactual tests.

## Live public source register (inspect versions, licenses and cited experiments)

- Introductory biology: NCBI Bookshelf, *Molecular Biology of the Cell*, https://www.ncbi.nlm.nih.gov/books/NBK21054/toc/ (older textbook, foundational not current benchmark).
- Reproducible mechanistic models: BioModels / SED-ML verification study https://pmc.ncbi.nlm.nih.gov/articles/PMC11785046/ ; SBML Level 3 Version 2 https://sbml.org/documents/specifications/ . SBML syntax validation is not semantics or simulation reproducibility.
- Enzyme kinetics with experimental conditions: BRENDA https://www.brenda-enzymes.org/datafields.php ; record organism, mutation, pH, temperature, solvent, units, assay and provenance rather than copying an isolated kcat/Km.
- Protein annotations: UniProtKB https://www.uniprot.org/ and annotation-score caveat https://www.uniprot.org/help/annotation_score (annotation count is not proof of functional correctness).
- Experimental structures: PDB/PDBe https://www.ebi.ac.uk/pdbe/about ; assess wwPDB validation https://www.rcsb.org/news/5d7bb149ea7d0653b99c8815 .
- Structure prediction: AlphaFold 3 paper https://www.nature.com/articles/s41586-024-07487-w and documented limitations https://www.ebi.ac.uk/training/online/courses/alphafold/alphafold-3-and-alphafold-server/introducing-alphafold-3/what-alphafold-3-struggles-with/ .
- Molecular dynamics engine: OpenMM https://github.com/openmm/openmm (components have MIT/LGPL and other licenses; do not assume the entire tree is Apache-2.0).
- Molecule graph chemistry: RDKit https://github.com/rdkit/rdkit (BSD-3-Clause; good for sanitization, fingerprints and stereochemistry, not proof of physical stability).

## First executed abstract experiment

`scripts/experiment_biochemistry_stoichiometry.py` runs purely synthetic, exact-rational checks on the reaction network:

`E + S <-> ES -> E + P`.

Species are free enzyme E, substrate S, complex ES, product P. The columns of the reaction stoichiometric matrix correspond to binding, unbinding and catalysis. Its exact rational rank is **2**, and its left-nullspace has dimension **2**. Independently check:
- total enzyme `E + ES` remains constant;
- total substrate moiety `S + ES + P` remains constant;
- deliberately forgetting substrate consumption gives a conservation counterexample;
- merging opposing binding/unbinding stoichiometric columns preserves the discrete update exactly;
- exact rational, nonnegative state updates for three assumed-parameter holdouts.
No calibration, in vivo/in vitro validation, quantifiable speedup, CACE FEM result, or protein-folding result is claimed.

## Candidate mathematics and verification bridge

Target elementary Lean theorems:
- Conservation under a single reaction step, for *arbitrary* exact rational fluxes, with no empirical assumptions.
- Equality of separate forward/reverse updates and the compressed net-binding flux update.
- More generally, if `lᵀ S = 0`, then `lᵀ (x + S v Δt) = lᵀ x` for arbitrary rational flux `v` and step `Δt`.
These abstract propositions are algebraic. Positivity, reaction kinetics correctness, estimated parameters, bounded integration error, and correspondence to the actual model are **separate** proof obligations.

CACE FEM/PDE extensions (unqualified): diffusion-reaction mass balance with oriented boundary flux; conservative discretizations for boundary exchange; interval bounds for residuals; adaptive mesh refinement driven by *proved* error indicators; and independent cross-solver checks. Chemistry products and force-field output must not be treated as manufactured matter.

## Recursive capability improvement without expanding authority

`source/provenance -> typed hypothesis -> synthetic or curated model -> invariant detection -> deliberate counterexample -> independent checker/Lean -> model equivalence -> blind holdout -> measured performance gain -> rollback check -> policy gate -> optional qualified optimization`

- Learning is incremental updating of a **reviewed knowledge/index and candidate code**, not an autonomous self-authorizing model-weight rewrite.
- Candidate optimizations can change execution only after independent checking, benchmark improvement, no-regression holdout, immutable commit/result binding, collar enforcement and rollback.
- Rejected claims, bugs and negative experiments are retained; an AI-generated manuscript is evidence to evaluate, not an oracle.
- Time or cloud budgets: use free GitHub-hosted checks first; Avrea only with the period-specific cost/usage preflight and explicit bounded reservation; one heavy lane at a time.
- Never perform unapproved clinical, live-organism, environmental release, high-risk pathogenic, or unsafe wet-lab experiments.

## Ranked next independent experiments

1. **Proof bridge:** formalize substrate/enzyme conservation and compressed flux equivalence, review proof statements and axiom dependencies.
2. **Reaction-network generalized matrix test:** synthetic networks with conservation laws and mutation tests; seek a counterexample for sloppy unit conversion or missing products.
3. **Standards bridge:** SBML subset importer (fail-closed on unsupported units/rules) cross-checked with a trusted independent SBML simulator; preserve SED-ML simulation definitions.
4. **Published kinetics case:** select one well-curated, nonhazardous BioModels system; fit or transfer measured constants with organism/pH/temperature controls; compare blinded trajectories and parameter uncertainty.
5. **Structure/sequence case:** use a benign reference protein with PDB experimental coordinates and explicit quality validation; investigate conformer sensitivity; no mechanism proof from AlphaFold confidence alone.

Each iteration must output SHA-pinned sources, methods, assumptions, machine-readable witnesses, counterexamples, model limitations and verification status.

## Published-model intake diagnostic (2026-10-09; fail-closed)

The pinned CC0 source `biomodels/BIOMD0000000051@92843fdc466e704445d491fb42b4142d4c70c3f6`
passed immutable commit and Git-blob checks. Independent `python-libsbml==5.21.2`
reported an SBML Level 2 Version 1 model with 18 species and 48 kinetic-law
reactions, but **40 consistency issues, including three severity-ERROR
findings with libSBML code 10541**. Those three findings state that kinetic
law formula units do not equal the required amount-per-time dimensions.
Evidence: GitHub Actions run `38002448162`, artifact
`pinned-biomodels-carbon-source-intake` (artifact ID `11650150126`).
The reported issue messages were originally truncated; the upgraded intake
stores up to 1500 characters per serious error, line/column locators and counts
by libSBML issue ID. The new diagnostics require a fresh run.

**Disposition:** model quarantined for dynamic simulation validation. Do not
override or downgrade libSBML severity solely to obtain a green workflow.
An old published SBML model can be historically useful while failing modern
consistency checks. Before comparing trajectories or connecting CACE, locate
the exact three kinetic laws and their unit-bearing symbols, establish
whether the issue reflects model annotations or physically inconsistent units,
compare the curator's intended simulation semantics, document any *separate*
proposed corrected derivative under a new source digest, and independently
cross-check outputs. No empirical claim or CACE qualification is inferred.
