# Merlin: Science, Mathematics, History and Philosophy Knowledge Platform

## Mission

Build a continually updated, source-grounded map of human inquiry: current science, mathematics, the history and philosophy of each discipline, and prospective research spaces. The platform is an input to Merlin's ideonomy and research-engine development, not a replacement for domain experts or independent verification.

## Research questions asked for every field

1. What objects and phenomena does this field study?
2. Which questions were historically important, and which remain unresolved?
3. What did practitioners measure, construct, calculate, observe or prove?
4. Which instruments, mathematical languages and experimental methods made progress possible?
5. What did pioneers themselves say in papers, letters, notebooks, lectures and correspondence?
6. What was the institutional, cultural, economic, technological and philosophical context?
7. Which predecessors, collaborators, critics and overlooked contributors shaped the work?
8. Which ideas were abandoned, revised, rediscovered or absorbed into another field?
9. What counts as evidence and what would falsify a claim today?
10. What adjacent concepts might form a new research program, and what would make it testable?

## Discipline coverage

The versioned ontology at `research/science/discipline-taxonomy.v1.json` covers mathematics, physical and chemical sciences, life sciences, Earth/space, computing/information, engineering, medical/health, cognitive/behavioral, social sciences, environmental/agriculture, humanities/philosophy, interdisciplinary systems, and prospective fields.

The ontology is deliberately extensible. Branches may be proposed before they exist institutionally, but must be marked speculative. A proposed discipline needs defined objects, concepts, methods, falsifiable or formally decidable questions, and a clear relationship to existing fields.

Historical theories are retained as historical records, not silently deleted and not presented as current fact.

## What makes a good scientist?

Merlin should teach and evaluate scientific practice through observable habits rather than a personality myth:

- intellectual honesty: distinguish observation, inference, assumption and speculation;
- curiosity paired with disciplined question selection;
- methodological competence and calibration;
- willingness to seek disconfirming evidence and publish negative results;
- reproducibility, transparent data and clear provenance;
- proportionate confidence and explicit uncertainty;
- mathematical and conceptual precision;
- collaboration, credit and fair attribution;
- ethical responsibility toward people, animals, environments and society;
- ability to revise beliefs without treating criticism as personal defeat;
- awareness of institutional incentives, bias and historical exclusion;
- communication that makes methods and limitations inspectable.

No single trait guarantees good science. Scientific reliability is a property of methods, communities, instruments, incentives and correction mechanisms as well as individuals.

## History and philosophy of science

Use multiple historiographical lenses: internal intellectual development, social/institutional context, material culture and instruments, colonial/global exchange, economics, gender and labor, and philosophical analysis. Do not reduce history to a sequence of lone geniuses. Pioneers are studied through primary evidence and contemporaneous context, with later interpretations kept distinct.

Philosophical modules include induction, deduction, abduction, falsifiability, confirmation, explanation, causation, realism/anti-realism, models and idealization, measurement, probability, reduction/emergence, values in science, demarcation, paradigm change, and the epistemology of mathematics.

## Pioneer dossier template

For every pioneer or collective:
- time/place and social-historical setting;
- training, institutions, patrons and material constraints;
- the problem as understood at the time;
- tools, instruments, notation and methods available;
- exact work performed and primary-source citations;
- contemporaries, collaborators, rivals and predecessors;
- what was novel versus inherited;
- failed attempts and abandoned explanations;
- how the work was received then;
- what later evidence changed the assessment;
- attribution disputes and historical caveats.

Never invent private thoughts or quote a pioneer without a traceable source. When evidence is absent, say so.

## Public-resource ingestion

See `research/science/source-registry.v1.json` and `research/science/ingestion-contract.v1.json`.

Prioritize public-domain and explicitly open-licensed books. Google Books is a discovery and metadata source; full-view/public-domain status must be checked per item. Internet Archive, HathiTrust, Europeana, Gallica, Library of Congress, Project Gutenberg and institutional collections have item-specific rights. A public URL is not proof of permission to copy or redistribute.

Google search operators may be used to locate legitimate public-domain scans, institutional repositories, manuscript catalogs and open publications. Search indexing is discovery only; rights and provenance are checked at the source.

## Evidence and claim model

Each claim is typed (observation, measurement, theorem, model, hypothesis, interpretation, historical report, philosophical argument, methodological rule or conjecture), carries an epistemic status, and links to exact source spans. Contradictory sources are preserved. OCR and machine extraction are treated as fallible.

The source pipeline is:
`discover -> identify -> rights check -> metadata -> permitted text -> OCR quality -> segment/cite -> claims/methods -> historical context -> compare -> formalize -> independent review -> publish`.

## Merlin integration

- Canonical records belong in the existing research engine/evidence ledger.
- Source workers have bounded read access and can write candidate records only.
- The science web app is a read-only view of canonical data plus clearly labeled curated seed content.
- Lean is used for formal mathematical claims when suitable; empirical claims require data, method and independent replication rather than forced formalization.
- CACE verifies artifact integrity, provenance and formal evidence, while domain correctness remains separately reviewed.
- Novel ideas enter ideonomy as conjectures with source lineage and explicit confidence; no automatic promotion.
- Resource limits, rollback and authority boundaries remain unchanged.

## Initial release scope

The first web app is a responsive research map with searchable discipline taxonomy, historical-program gallery, primary-source directory, research method guide and a structured ingestion contract. It is a foundation, not yet a fully populated corpus or an automated mass-ingestion service.


## Existing Merlin runtime integration

The new `scripts/merlin_science_ideonomy_packet.py` connects a rights-cleared pioneer dossier to the existing `python/orchestrator.py` and C++ runtime protocol. It builds a bounded research task that asks Merlin to:
- separate source observations, historical interpretation and conjecture;
- extract methods, instruments, evidence and limitations;
- map discipline relationships;
- propose a small number of falsifiable ideonomy candidates;
- identify missing predecessors, collaborators and alternative explanations;
- suggest a measurable improvement to Merlin's own research process.

Example on a machine where the existing C++ runtime and a configured model are available:

```bash
python3 scripts/merlin_science_ideonomy_packet.py \
  --dossier research/science/reading-notes/newton-principia-reading.json \
  --runtime ./build/expert_robot_runtime \
  --role controller \
  --out state/science-research/newton-ideonomy-candidate.json
```

The command is deliberately not run in CI because the hosted Avrea smoke runner does not have the user's local model weights or runtime configuration. The smoke test validates packet construction only. Runtime output is stored as an unreviewed candidate with source digest and citation links; it cannot write to the canonical theorem graph or promote claims.


## Mandatory research and engineering governance

`research/science/merlin-research-governance.v1.json` is the machine-readable policy for every Merlin build and research task. A task must not create or modify an artifact until it has a validated plan from `scripts/merlin_engineering_plan.py`. The plan records primary and secondary domains, in-scope subsystems, exclusions, requirements with acceptance tests, assumptions, constraints, inductive/deductive/abductive reasoning, disconfirmation paths, design alternatives, bias/fallacy review, resource budgets, independent verification and rollback.

The Python orchestrator now rejects every non-health-check task unless a plan file is supplied and passes validation. It injects the exact plan and digest into the runtime task. The science ideonomy bridge generates and persists a plan sidecar, validates it, and dispatches with that plan. This enforces the current Python dispatch boundary. Direct C++ protocol callers and other independent worker/dispatch paths still require their own equivalent gate before the policy can be called universal. CI tests the plan validator and the science bridge's generated plan.

### Skeptical reasoning

For each material claim, Merlin must distinguish observations, measurements, source reports, derived results, theorems, models, hypotheses, interpretations, analogies and conjectures. It must:
- state premises and inference rules for deduction;
- state sample, coverage, exceptions and generalization limits for induction;
- compare alternative explanations for abduction;
- identify counterexamples, disconfirming evidence and failure conditions;
- inspect cognitive bias, research-design bias, logical fallacies, assumptions, confounders, incentives and measurement limitations;
- treat bias flags as hypotheses to investigate, not as accusations or proof;
- retain contradictions and uncertainty rather than forcing consensus.

### Domain and subsystem scope

Every research or engineering item has one primary domain and may have explicitly justified secondary domains. The domain audit reports duplicate labels and cross-domain overlaps; it does not automatically reassign an item based on its name. Unmapped overlaps are review candidates. Emerging fields remain speculative until definitions, formal objects, methods and independent evaluation justify a status change.

### Storage and transcript intake

The governance contract sets conservative staging defaults: 256 MiB total staging, 10 MiB per source, 2 MiB per transcript, 5,000 staged files, and a 1 GiB free-disk reserve. These are defaults, not guarantees about the machine's actual disk. Workers must preflight actual free space, stop before quotas are exceeded, deduplicate by canonical URL and content hash, avoid storing video/audio media, compress permitted text, and never prune canonical or verified evidence automatically.

`scripts/merlin_youtube_discover.py` discovers metadata only when an explicitly configured YouTube Data API key is available. Transcript intake accepts authorized VTT/SRT exports or explicitly open-licensed material, with a 2 MiB cap and rights declaration. The official YouTube captions API is owner-authorized; arbitrary public transcript retrieval is not assumed. Every transcript record should preserve video URL, caption language/type, retrieval date, rights basis, timestamps and content hash.

### Problem decomposition, translation and adaptive reframing

Every engineering/research plan now includes a required problem_representation contract, validated by scripts/merlin_problem_reframing.py. Merlin must preserve the original problem, then decide whether decomposition is useful. When it is, it creates smaller subproblems with explicit objectives, dependencies, interfaces and acceptance criteria. If decomposition would add no value, it records why.

For mathematical problems, Merlin actively looks for multiple useful representations of the same underlying object or question. Candidate languages include:
- symbolic equations, systems of equations and inequalities;
- coordinate frames, basis changes, matrices and tensors;
- geometric constructions, loci and transformations;
- graphs, hypergraphs, networks and constraint systems;
- combinatorial objects, recurrences and generating functions;
- logic, type theory, proof systems and formal specifications;
- category-theoretic objects, morphisms and functorial views;
- dynamical systems, state spaces, phase portraits and invariants;
- probability distributions, statistical models and information-theoretic views;
- optimization formulations, topology and algorithmic representations.

These are candidate lenses, not a mandatory checklist for every task. Merlin chooses representations that expose structure, simplify proof or computation, or make hidden assumptions visible. It labels each translation as exact isomorphism, mathematical equivalence, embedding, structural analogy, or heuristic reframing. Every mapping records what is preserved, what is lost, its validity conditions, what does not transfer, and how to test the correspondence.

An analogy is not an equivalence. A visual resemblance is not a theorem. Proofs transfer only when a structure-preserving map and all required hypotheses have been established. Otherwise the translated view is used to generate conjectures or search strategies, and the result must be checked back in the original formulation.

Merlin should reframe when a search stagnates, the current representation becomes unwieldy, assumptions fail, independent formulations disagree, a useful invariant appears, or another discipline offers a productive model. It should compare candidate frames by invariant preservation, tractability, information loss, assumption burden, independent verifiability and resource cost. It should retain failed reframings and counterexamples as evidence rather than repeatedly rediscovering them.

The Python orchestrator plan gate now requires this representation contract for all non-health-check tasks. The science-history ideonomy bridge creates its own decomposition and source-evidence/discipline-graph representations. CI includes validator tests for decomposition, exact/analogical distinctions, missing non-transferable properties and the explicitly justified no-decomposition case.


## Video and transcript research index

`research/science/video-transcript-index.v1.json` records four MIT OpenCourseWare YouTube lectures with English transcript availability: requirements definition, verification and validation, classification/statistical fallacies, and statistical sins. It also records a cognitive-bias transcript PDF discovered through Pressbooks, but leaves its rights status unknown.

The catalog stores video IDs, official source pages, transcript availability, language, license conditions and concise original research notes. It does not store video/audio files or full transcript text. MIT OCW material is generally CC BY-NC-SA 4.0; its terms require attribution, noncommercial use and share-alike, and item-level exceptions must be checked. Merlin's transcript intake therefore blocks CC BY-NC-SA text unless the intended use is explicitly noncommercial. Unknown-rights sources remain metadata-only. The official OCW terms also state that AI use must comply with those license restrictions.