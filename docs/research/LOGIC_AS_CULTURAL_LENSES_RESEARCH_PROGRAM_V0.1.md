# Merlin Research Program: Logic as Lenses of Culture v0.1

**Program ID:** MERLIN-LOGIC-CULTURE-001  
**Status:** research specification; all comparative claims require source-level investigation  
**Parent:** Merlin Master Idea Registry and System Map v1  
**Related:** Mathematical Idea Ledger, XMG, Equation Atlas, Universal Research Curriculum, Merlin Learning

## 1. Research thesis

Logic can be studied simultaneously as:
1. formal systems for representing and evaluating inference;
2. historically evolving intellectual practices;
3. culturally and linguistically situated ways of framing questions, categories, explanations and disagreements;
4. epistemic methods for deciding what counts as evidence, demonstration, testimony, proof or justified belief;
5. practical tools used in science, mathematics, law, medicine, engineering, education, governance, art and everyday life.

These dimensions interact, but they are not identical. Formal validity is evaluated relative to a specified system and semantics. Cultural and historical analysis studies how people select premises, categories, questions, methods and standards of justification. Merlin must not reduce formal logic to cultural preference, nor assume that one formal system captures every form of reasoning.

**Core question:** How do different formal and historically situated reasoning practices make different aspects of the world visible, expressible, debatable and decidable?

## 2. The five-lens model

### Lens A — formal structure
For each formal system record:
- syntax and well-formed expressions;
- semantics and interpretation;
- axioms and inference rules;
- proof calculus or decision procedure;
- consistency, completeness, soundness and decidability results where known;
- expressive limits and counterexamples;
- assumptions, domain and intended application.

Candidate families: classical propositional and predicate logic; intuitionistic and constructive logic; type theory; modal and temporal logic; epistemic and deontic logic; probabilistic logic; fuzzy logic; paraconsistent and relevance logics; linear logic; higher-order logic; categorical approaches.

Do not treat these as interchangeable. A translation between systems needs a typed mapping and a stated preservation theorem or an explicit note about what is not preserved.

### Lens B — historical development
Ask:
- What concrete problem was being addressed?
- What knowledge, notation, instruments, texts and institutions were available?
- Who participated, taught, translated, criticized and transmitted the work?
- What competing approaches existed?
- Which ideas were borrowed, adapted, disputed or independently developed?
- What changed after new evidence, technologies or social conditions appeared?

Represent intellectual development as a network, not a lone-genius timeline. Distinguish contemporary primary sources from later reconstructions and modern interpretations.

### Lens C — language and culture
Investigate how language, translation, metaphor, classification, ontology, narrative and rhetorical conventions affect reasoning and communication.

Examples of questions:
- Which distinctions are encoded grammatically or lexically?
- What is lost or changed in translation?
- Which entities, relations or causal structures are treated as basic?
- How do oral, textual, diagrammatic, mathematical and embodied forms of explanation differ?
- How do education, institutions and social roles shape who may make a claim and what counts as an acceptable argument?

Do not attribute a single logic to an entire culture, language, religion or population. Treat traditions as internally diverse, historically changing and contested. Use specific texts, communities, time periods and scholarly sources.

### Lens D — epistemology and standards of evidence
Record the role of:
- observation and measurement;
- experiment and replication;
- demonstration and proof;
- testimony and expertise;
- memory, oral transmission and documentary records;
- analogy, model, simulation and prediction;
- consensus, dissent and institutional review;
- practical success, ethical constraints and uncertainty.

Ask when two traditions disagree about a conclusion versus when they disagree about the question, definitions, admissible evidence or method.

### Lens E — application and consequences
Study how reasoning systems are used in:
- mathematics and theoretical science;
- empirical sciences and engineering;
- law and jurisprudence;
- medicine and clinical reasoning;
- economics and social sciences;
- language, literature, art and design;
- education and public deliberation;
- computer science, AI and automated decision systems.

A formal model can clarify assumptions and consequences; it cannot, by itself, decide all value judgments or settle the historical meaning of a source.

## 3. Comparative case-study design

Each case study must include:

1. **Scope:** named tradition, school, text, community, place, language and date range.
2. **Problem setting:** what question or dispute was active and why it mattered.
3. **Primary evidence:** original text, translation, artifact, diagram or documented practice, with edition and provenance.
4. **Scholarly context:** reliable specialist interpretations, disagreements and historiographical caveats.
5. **Reasoning reconstruction:** definitions, categories, premises, inferential moves, evidence and conclusions.
6. **Formal reconstruction:** only where defensible; specify which modern formal system is being used and what it preserves or changes.
7. **Comparison:** compare selected dimensions, not entire civilizations or worldviews.
8. **Counter-reading:** plausible alternative interpretations and evidence against the proposed reading.
9. **Learning artifact:** accessible explanation, historical timeline, primary-source excerpt within rights limits, guided reconstruction and student exercise.
10. **Review:** specialist review for culturally specific or contested interpretations.

### Candidate case-study areas

These are research queues, not assertions that the traditions share one method:
- ancient Greek syllogistic, dialectic and demonstrative mathematics;
- Indian Nyaya reasoning and pramana theories, alongside distinct Buddhist epistemological traditions;
- Mohist and other early Chinese argumentation and classification practices;
- Islamic kalam, falsafa and medieval logical scholarship;
- medieval scholastic disputation and commentary;
- African philosophical traditions and their varied forms of argument, debate and knowledge transmission;
- Indigenous knowledge practices, studied through community-specific sources and protocols rather than imposed external taxonomies;
- modern symbolic logic, mathematical foundations, computation and AI.

Add cases only with reliable scholarship and enough context to avoid flattening internal differences.

## 4. Cross-cultural comparison schema

A case record should carry:

- stable ID and title;
- named tradition/school/community and scope;
- language(s), region and date range;
- source references, edition, translation and provenance;
- author/contributor identities only when historically supported;
- problem statement and intellectual context;
- key concepts and terms, including untranslatable terms;
- premises, inferential moves and conclusion;
- standards of evidence and justification;
- relation to institutions, tools and teaching practices;
- formal reconstruction, if any, with assumptions and limitations;
- comparisons and typed relations to other cases;
- contested interpretations and objections;
- reviewer and review date;
- teaching level, media and accessibility metadata;
- epistemic status.

Status labels should distinguish 'source_collected', 'translation_reviewed', 'historical_context_reviewed', 'formal_reconstruction_candidate', 'specialist_reviewed', 'contested' and 'unresolved'. These statuses are not a ranking of cultures or traditions.

## 5. The translation problem

Merlin should build a typed translation/crosswalk layer between:
- natural-language concepts;
- historical technical terms;
- modern mathematical notation;
- formal logic systems;
- diagrams and visual argument maps;
- XMG glyph expressions;
- machine-readable claim/evidence graphs.

Every translation records:
- source and target language/system;
- scope and intended interpretation;
- terms with no exact equivalent;
- assumptions introduced by the translation;
- information lost, generalized or added;
- whether inferential relations are preserved;
- reviewer and source provenance.

A translation is not an equivalence merely because two expressions are placed side by side. Use typed relations such as 'approximate_translation', 'contextual_analogue', 'formal_embedding', 'equivalent_under_assumptions', 'contrasts_with' and 'untranslatable_in_context'.

## 6. XMG and visual reasoning interface

XMG can render formal and informal reasoning as typed, inspectable structures:
- premises and conclusions;
- inference steps;
- quantifier scope;
- temporal/modal operators;
- contradiction and paraconsistent states;
- uncertainty and probabilistic dependencies;
- argument maps and competing explanations;
- source-to-claim links and translation edges.

The glyph AST is semantic authority; visual glyphs are renderings. A rendered symbol must not erase ambiguity, context, provenance or assumptions. Different formal systems should have distinct type environments and rule sets.

## 7. Merlin Learning integration

A student should encounter a live problem, not only a finished definition:
1. meet a historical puzzle or disagreement;
2. inspect what information was available at the time;
3. try to reason through the problem;
4. compare several historically documented approaches;
5. reconstruct one argument using its original categories;
6. optionally translate it into a modern formal system;
7. inspect what the translation preserves and loses;
8. practice a new problem and revisit it through spaced retrieval.

Assess the student's ability to distinguish premises, evidence, inference, assumptions, context, translation and interpretation. Do not grade students on agreeing with a single cultural or philosophical interpretation.

## 8. Research agents and quality controls

- **Hermes:** routes case studies and coordinates research stages.
- **History-of-Ideas Teacher:** builds chronology and source-grounded context.
- **Logic Specialist:** formalizes inference systems and checks the reconstruction.
- **Language/Translation Reviewer:** audits terminology and translation loss.
- **Epistemology Reviewer:** distinguishes kinds of evidence and justification.
- **Media Curator:** locates licensed primary-source media and contextual metadata.
- **Independent Assessor:** checks whether claims follow from sources and whether comparisons are fair.
- **Coder-Teacher:** maintains schemas, parsers, source adapters, tests and visualization tools.

No agent may independently certify its own historical interpretation or cultural representation. High-impact or culturally specific material requires qualified human review.

## 9. Initial deliverables

1. Versioned case-study schema and validator.
2. Source/provenance schema with edition, translation, license and rights fields.
3. Formal-logic profile schema with syntax, semantics, inference rules and known limits.
4. Translation/crosswalk schema with explicit loss and equivalence status.
5. Research protocol and reviewer rubric.
6. Small pilot set of cases selected by source availability and specialist review, not by a desire to rank traditions.
7. XMG argument-map prototype.
8. Three Math Kung Fu / Merlin Learning lessons with source-backed history and retrieval practice.
9. Independent review report documenting disagreements and corrections.

## 10. Acceptance criteria

- Formal system definitions include semantics and assumptions, not just labels.
- Historical claims have traceable primary or specialist sources.
- Modern reconstruction is visibly separated from historical actors' own vocabulary.
- No whole-culture essentializing claims.
- Translation loss and uncertainty are explicit.
- Comparative claims can be challenged and revised.
- All media has provenance and rights metadata.
- Teaching content distinguishes established facts, contested interpretation and open research.
- Tests validate schema, provenance completeness and status transitions.
- No unsupported claim is promoted because it is rhetorically compelling.

## 11. Relationship to the wider Merlin system

This program consumes the mathematical idea ledger and research source graph; uses the universal research curriculum to train specialists; uses Hermes and the prompt/result contract for bounded research tasks; uses Avrea for reproducible text/data processing and tests; uses CACE for artifact integrity and signed evidence when the signer profile is qualified; uses Lean for formal statements; uses XMG for typed representation and visualization; and exports approved lessons into Merlin Learning.

The program contributes new typed records to the canonical registry and dashboard. It does not create a parallel knowledge base.

**Research principle:** preserve both the rigor of formal systems and the specificity of lived intellectual history. Compare carefully; do not collapse differences for the sake of a single universal story.


## 12. Existing Merlin logic-lens implementation — extend, do not duplicate

PR #80 already introduced a computational logic-lens foundation:
- `scripts/merlin_logic_lenses.py` explores fuzzy membership, finite n-valued, paraconsistent, intuitionistic, modal/temporal, probabilistic, rough approximation, many-sorted/type, algebraic, topological, category-semantic, information, game and quantum logic families.
- It defines bounded finite truth-table generation, several fuzzy operators, candidate ranking and logic/mathematics/composition combinations.
- `formal/MathAI/LogicLenses.lean` contains finite n-valued min/max operations and fuzzy Gödel, product and Łukasiewicz conjunctions, with commutativity/idempotence lemmas.
- `research/science/merlin-research-governance.v1.json` requires fuzzy and n-valued logic lens review, logic composition, explicit epistemic labels, reasoning protocols and bias/fallacy review.
- `tests/merlin_logic_ideonomy_smoke.py` checks bounded generation, truth-table caps, deterministic ideonomy, composition counts and research-packet construction.
- `docs/MERLIN_SCIENCE_HISTORY_PHILOSOPHY_PLATFORM.md` defines the science/history/philosophy source-grounded atlas and pioneer dossier template.

See [PR #80 — Merlin science, mathematics, history and philosophy atlas](https://github.com/Mannyspiro/expert-robot/pull/80), which reported a successful Avrea smoke workflow run #42088542852.

**What the existing code does not establish:** the Python candidate scores are heuristic priors, not measured usefulness or truth; finite tables do not establish general properties; Lean lemmas about connectives do not validate historical interpretations; the existing computational logic families are not a comparative history of cultural reasoning practices.

This research program adds the missing source-grounded historical, linguistic, epistemic, translation and specialist-review layers. It should reuse the existing logic engine and formal models, attach its case-study records to the existing science source registry and canonical research graph, and export lessons to Merlin Learning. Do not fork a second logic catalogue or duplicate the fuzzy/n-valued implementations.

### Existing-to-new interface

- Existing formal profile -> new case study: link by stable logic-system ID and exact formal specification revision.
- Historical source -> concept/argument reconstruction: cite edition, translation, page/section and source span.
- Historical term -> modern term: create a translation record with equivalence/analogy/loss status.
- Formal reconstruction -> Lean/XMG: link to definitions, assumptions, theorem/test receipts and visual AST identity.
- Case study -> curriculum lesson: export only after source and specialist review, keeping interpretation disputes visible.
