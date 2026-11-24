# Conversation context ingestion contract

## Objective

Make the relevant history of prompts and responses available to Merlin as
traceable project knowledge. The conversation archive is a source of
requirements and decision provenance; it is not automatically ground truth.

## Required record

Each imported message or extracted decision should retain, where available:
- stable source conversation and message identifiers;
- role (user, assistant, tool, or system-generated result);
- original timestamp and import timestamp;
- exact original text or a lossless source reference;
- content hash and attachment references/hashes;
- project, subsystem, and topic tags;
- extraction version and extraction method;
- links to requirements, decisions, hypotheses, artifacts, and superseding records;
- sensitivity/access classification and retention policy.

Do not silently paraphrase the canonical source. Derived summaries must link to
the exact source messages and identify the summarizer/version.

## Relevance and retrieval

Retrieve context by project, subsystem, requirement, decision, dependency, and
time window. Prefer direct source messages when a decision or constraint is
ambiguous. Preserve contradictory statements and identify which later explicit
correction supersedes an earlier decision. Do not collapse disagreement into
false consensus.

Use relevance filtering so unrelated personal or sensitive material is not
copied into project memory. Project context must not be used to infer unrelated
personal attributes.

## Provenance and integrity

Store source references, content hashes, import receipts, and extraction
versions. A hash establishes identity/integrity of the imported bytes, not the
truth of the content. Keep original source records immutable; append corrections
and supersession links.

## Known related continuity sources

Initial source discovery found relevant project material in the user's Library:
- `expert_robot_cross_chat_handoff_2026-10-09.md`: Expert Robot research and
  cross-chat continuity snapshot; treat its runner states as historical.
- `CACE_CROSS_CHAT_HANDOFF.md`: source-of-truth hierarchy and continuity
  operating rules.
- `CACE_CHAT_IDEA_LEDGER.md`: preserved research/product ideas, including
  operator memory, procedural reasoning, graph/coordinate transformations,
  and evidence boundaries.
- `CACE_LOCAL_AI_REASONING_CURRICULUM_2026-09-19.md`: operator-sequence
  learning, paired counterfactual/perturbation evaluation, geometric
  representations, and anti-memorization testing.

These are related context sources, not proof evidence and not substitutes for
the original Merlin prompts and responses. Import only relevant portions with
source references and preserve their historical dates.

The machine-readable inventory is
`config/research/context_source_manifest_v1.json`. It explicitly marks this
discovery as partial: original message-level Merlin transcripts and attachments
have not yet been located/imported. The manifest must be extended as more
authorized source records are found; it must never mark full coverage based
only on handoff documents.

## Initial importer implementation

`python/conversation_context.py` provides an append-only SQLite store and
JSONL export intake. It currently:
- requires stable source system, conversation, and message IDs;
- preserves role, timestamp, exact text or content reference, content digest,
  attachment references/digests, project tags, privacy classification, and
  explicit supersession metadata;
- rejects restricted records and rejects personal records unless the caller
  explicitly opts in;
- makes duplicate imports idempotent and rejects identity collisions where the
  same source message ID is presented with different content;
- prevents updates/deletes to imported message and attachment rows;
- reports source/conversation/message/attachment coverage without claiming
  complete history;
- supports retrieval by project tag.

This is a storage/import primitive, not yet connected to an authorized ChatGPT
conversation export or to the live C++ research engine. Attachment bytes remain
external; the importer preserves their identifiers and digests rather than
silently copying or modifying them. The actual historical Merlin transcripts
must still be obtained from an authorized export before they can be imported.

## Operational boundary

Only import conversations and attachments available through an authorized
export, connector, or explicit user-provided source. Do not claim that all
historical chats have been imported until coverage is measured and an import
manifest reports the covered sources, gaps, and failures.

## Acceptance criteria

1. A source message can be retrieved by its original conversation/message ID.
2. Every extracted requirement links to source messages.
3. Contradictory requirements remain visible with chronology and supersession.
4. Imported attachments retain identity and retrievable references.
5. Duplicate imports are idempotent.
6. Failed or partial imports produce explicit logs and coverage reports.
7. Sensitive and unrelated context is excluded by policy.
8. A project handoff can reconstruct current requirements and unresolved gaps
   from source-linked records rather than an untraceable summary.
