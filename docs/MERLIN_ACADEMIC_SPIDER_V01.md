# Merlin AcademicSpider — focused university registry

## Purpose

AcademicSpider generates scoped Google search URLs for public professor pages,
faculty directories, research groups, publications, and preprints. It is a
discovery planner, not a Google scraper or a complete census of faculty.

## Initial institution registry

| Institution | Domain | Why included |
|---|---|---|
| Stanford | stanford.edu | Combinatorics, geometry, topology, mathematical research |
| MIT | mit.edu | Combinatorics, algebraic geometry, representation theory, theoretical CS |
| Princeton | princeton.edu | Combinatorics, graph theory, differential geometry, topology, mathematical physics |
| Harvard | harvard.edu | Algebraic/geometric combinatorics, geometry, topology, dynamics, mathematical physics |
| ETH Zurich | ethz.ch | Combinatorics/optimization, geometry/dynamics, symplectic and algebraic geometry |
| Zuse Institute Berlin | zib.de | FormalLean and agentic AI for mathematics; computational combinatorics + Lean |

The registry is deliberately small and evidence-led. Expand only when an institution
adds a distinct research cluster or formal-methods capability relevant to Merlin.

## Run

From the repository root:

    PYTHONPATH=python python3 -m merlin.academic_spider --pretty
    PYTHONPATH=python python3 -m merlin.academic_spider --domain ox.ac.uk --name "University of Oxford" --topic "combinatorics" --topic "formal mathematics"

Each JSON record contains institution, domain, query category, Google query,
and search URL. Google `site:` queries only surface indexed pages, so results
must be reviewed and canonicalized.

## Recommended research workflow

1. Run the registry query set.
2. Keep only official faculty directories, professor homepages, and university
   research-group pages.
3. Follow official public links to personal homepages, publication lists,
   preprints, lecture notes, software, and seminars.
4. Record researcher, institution, topics, publication identifiers, source URL,
   retrieval time, and evidence status.
5. Deduplicate by canonical URL, ORCID, DOI, and stable institutional profile URL.
6. Map researcher -> paper -> mathematical object/method -> open problem ->
   candidate conjecture -> Lean formalization.
7. Keep hypotheses separate from source-backed facts and Lean-verified theorems.

## Merlin research-council debate

**Discovery advocate:** A broad but finite university registry increases the chance
of finding cross-field bridges: for example, geometric combinatorics can connect
graph embeddings, polytopes, optimization, and topology.

**Skeptical mathematician:** Keyword overlap is not a mathematical connection.
A page mentioning "geometry" does not establish shared definitions, a valid
transformation, or a theorem. Every proposed bridge needs explicit objects,
maps, invariants, assumptions, and a counterexample search.

**Implementation decision:** prioritize pages with named researchers and concrete
papers/projects. Score candidate links by shared mathematical structures and
methods, not word similarity alone. Preserve citations and source provenance;
send conjectures to computation and Lean, never directly to the verified corpus.

## Boundaries

- No automated scraping of Google result pages in this version.
- Do not bypass logins, paywalls, CAPTCHAs, robots exclusions, or access controls.
- Any future fetcher must respect site terms, robots.txt, rate limits, and response
  budgets.
- Collect public professional research information only.
- A discovered profile or paper is evidence of a source, not proof of its claims.

## Next increment

Add a public-URL intake and canonicalization store with provenance, then a
robots-aware low-rate fetcher limited to URLs discovered from official domains.
