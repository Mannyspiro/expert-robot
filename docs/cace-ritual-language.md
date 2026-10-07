# CACE Ritual Language (CRL) v0.1

**Extension:** `.crl`

CRL is a domain-specific programming language for expressing historical ritual,
occult, alchemical, and magic-circle procedures as reproducible scientific
experiments.

It is not a supernatural scripting engine. It is a compiler front-end for:

```
historical source
-> CRL
-> Magick IR
-> exact geometry
-> witness-conditioned provenance
-> controls / ablations
-> CACE known-physics models
-> measurements
-> residual + certified uncertainty
-> Expert Robot experiment selection
-> experiment-inspired mathematics
```

## Why a language instead of only JSON

Historical procedures are sequential and parameterized. A language makes the
procedure human-readable while retaining a deterministic typed compilation
target.

The source text stays separate from the compiled IR so we can diff:

- manuscript witness changes;
- glyph/name changes;
- geometry changes;
- timing changes;
- material substitutions;
- acoustic changes;
- experimental controls.

## Core syntax

```text
RITUAL 0.1
ID example
TITLE "Example operation"
TRADITION "Historical source family"

WITNESS witness1 kind=manuscript provenance=direct weight=1 \
  shelfmark="Example MS" folio="12r"

CLAIM P0_perceptual historical_only "Historical claim being tested"

CIRCLE outer radius=2 center=0,0,0 normal=0,0,1
CIRCLE inner radius=3/2 center=0,0,0 normal=0,0,1
TOPOLOGY "inner contained_by outer"

SYMBOL authority1 kind=name role=authority text="..." \
  position="outer@0deg" order=0 repeat=1 confidence=1 provenance=witness1

VOICE authority1 mode=live_voice spl=65 repeat=1

MATERIAL metal1 class="silver" role="conductive object"

ORIENT manuscript_relative
TIME_CONSTRAINT "historically prescribed time"
STEP "construct outer boundary"
STEP "perform invocation"

MEASURE acoustic instrument="measurement microphone" rate=96000
MEASURE magnetic instrument="3-axis magnetometer" rate=1000

CONTROL "rotate complete geometry"
CONTROL "scramble symbolic order while preserving geometry"
CONTROL "recorded voice"
BLINDING double
RANDOMIZE true
PREREGISTER true
HOLDOUT 0.2

MODEL acoustic_wave
MODEL maxwell_em
MODEL sensor_noise

UNKNOWN unmodeled policy=residual_only \
  "Residual not explained by declared models; not itself an explanation"

END
```

## First-class channels

CRL deliberately separates:

```
geometry
symbols / glyphs / names
materials
acoustic waveform
orientation
astronomical/timing metadata
environment
human actions
measurements
controls
known-physics models
unmodeled residual channels
```

A spoken name can therefore be varied independently as:

- lexical/symbolic sequence;
- phoneme sequence;
- spectrum;
- phase;
- rhythm;
- SPL;
- live versus recorded source.

## Witness rules

CRL inherits the manuscript safeguards developed in the Harley/Sloane/Egerton
work:

- individual witnesses, never generic diagrams;
- diplomatic glyph form remains separate from normalized interpretation;
- visual and textual evidence remain separate;
- copied observations count once;
- several mutations from one diagram are capped to one effective locus;
- missing pixels remain latent;
- a visually similar page never substitutes for a missing folio;
- diagram-family transmission is not whole-manuscript descent.

## Magic-circle route

Circle-oriented CRL programs compile through the dedicated route:

```
CRL
-> source/witness validator
-> exact Circle3/Point3/Line3 geometry
-> symbolic-position graph
-> topology graph
-> material boundary assignments
-> acoustic/timing/orientation channels
-> control generator
-> CACE multiphysics packet
-> synchronized measurement plan
-> residual certificate
-> replication ledger
```

Important topology characters include:

- ring count;
- nesting;
- openings/breaks in boundaries;
- operator locus;
- target/entity locus;
- polygon-circle combinations;
- fixed angular positions;
- order of labels;
- measured spacings/ratios.

Generic "circle exists" is deliberately low-information.

## Portal route

Portal terminology remains graded:

- P0_perceptual
- P1_information
- P2_field_energy
- P3_matter_transport
- P4_spacetime_connection

A P0/P1 result cannot be relabeled P3/P4. Each level requires its own
observable, controls, certified known-physics exclusion, and replication.

## Integration with mathematics discovery

After experiments, CRL results enter the same experiment-to-math loop as all
other CACE research:

```
result patterns
-> conjecture candidates
-> counterexample search
-> RecursiveLemmaFactory
-> Lean
-> theorem registry
-> optimization benchmark
-> qualified CACE optimization
```

Thus even a null occult experiment can be useful if it reveals geometry,
symmetry, acoustics, meshing, inference, or error-estimation mathematics that
improves CACE.
