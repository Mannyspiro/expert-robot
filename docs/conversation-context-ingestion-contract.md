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
