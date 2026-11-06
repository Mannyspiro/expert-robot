# Merlin GovInfo XML parser contract v0.1

## Scope
This module performs bounded structural extraction from XML fixtures and captured GovInfo bytes. It is not an XSD validator, complete USLM implementation, Federal Register legal parser, source authenticity verifier, or legal conclusion engine.

## Inputs and provenance
Every parse call requires a collection and package ID. Every output binds the exact input bytes by SHA-256 and identifies the parser version. Callers must preserve the upstream capture manifest and source URL alongside the records.

## Output behavior
- Federal Register input produces a document-level record with title, document number, publication date, effective date, agency names and extracted text when recognizable tags exist.
- USCODE, STATUTE and PLAW inputs produce section-level records when section elements exist.
- Missing metadata is represented as null and an extraction warning; the parser never fabricates dates, titles, citations or agencies.
- Unknown structures produce a generic document record rather than being silently discarded.

## Safety and limits
The parser enforces a configurable byte cap and rejects DTD/entity declarations. It uses Python's standard XML parser. No network calls or credentials are present. Schema validation against pinned GovInfo/USLM XSDs remains a separate qualification step.

## Qualification still required
1. Pin the exact GovInfo schema repository commit and XSD digest per collection.
2. Add official, versioned fixtures for FR, CFR, USLM statutes and bills.
3. Validate against those XSDs in an isolated Avrea job.
4. Compare extracted metadata and section boundaries against source package metadata.
5. Obtain CACE review of parser source, fixture corpus and reproducibility receipt before marking qualified.
