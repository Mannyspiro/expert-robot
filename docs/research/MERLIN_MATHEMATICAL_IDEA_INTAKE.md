# Merlin Mathematical Idea Intake Protocol

This protocol applies to new mathematical concepts, hypotheses, representations, transformations, proof obligations, experiments and engineering mappings discovered during Merlin work.

## Required behavior

Whenever a new mathematical idea is developed or materially refined:
1. Search the catalog for an existing stable ID before creating a record.
2. Update the existing record if it is the same idea; create a new ID if it is genuinely distinct.
3. Add a typed relation to related ideas rather than duplicating their content.
4. Update the human-readable ledger index.
5. Preserve provenance and epistemic status.
6. Run the catalog validator and relevant tests.
7. Commit the record with the code or research artifact that implements it, when applicable.

This is a repository workflow rule. It does not imply that every future conversation is automatically written to GitHub; a conversation must be incorporated through an available repository workflow or an authorized agent run.

## Minimum record fields

- `id`: stable ID, never recycled;
- `title`: short descriptive name;
- `kind`: `concept`, `representation`, `transformation`, `conjecture`, `theorem`, `experiment`, `engineering_mapping`, or `open_question`;
- `claim`: precise statement or research question;
- `definitions`: terms and mathematical objects;
- `assumptions`: explicit conditions and scope;
- `status`: one of the enumerated epistemic statuses;
- `provenance`: source chat/document/commit/experiment;
- `relations`: typed links to other stable IDs;
- `objections`: counterexamples, caveats or unresolved issues;
- `next_steps`: concrete proof, experiment, literature or implementation task.

## Status discipline

- `candidate`: proposed, not yet checked;
- `literature_checked`: relevant literature search recorded, no novelty claim implied;
- `counterexample_checked`: specified counterexample search performed;
- `finite_tested`: finite computational/test evidence only;
- `formalized`: formal statement or encoding exists; compilation/proof status must be separately recorded;
- `supported`: evidence supports the precisely scoped claim;
- `refuted`: a counterexample or contradiction refutes the scoped claim;
- `unresolved`: evidence is insufficient or conflicting.

Do not promote a broad idea because one narrow example passed. Do not label a result `formalized` merely because Lean-looking source exists; record whether the pinned toolchain compiled it and whether the theorem was actually proved without unintended axioms.

## Relation vocabulary

Use controlled relation types where possible:
`generalizes`, `specializes`, `depends_on`, `equivalent_under`, `maps_to`, `contrasts_with`, `tested_by`, `formalized_by`, `implemented_by`, `applies_to`, `motivated_by`.

## Provenance and reproducibility

For computational work, include source revision, input hash, configuration, random seed, toolchain, command, output artifact hash and environment. For literature, include stable URL/DOI and the exact claim supported. For informal discussion, identify the conversation date/topic and mark the claim as a candidate until independently checked.

## Safety and authority

Idea intake is documentation and research routing only. It does not authorize code execution, deployment, physical actuation, data access or merging. Such actions remain behind the existing permission, verification, approval and rollback controls.

**Invariant: capability grows, authority never expands.**
