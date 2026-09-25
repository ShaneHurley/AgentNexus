# Evidence and Source Rubric

## Claim classifications

Use exactly one classification per claim:

- `CONFIRMED`: directly established by an authoritative primary record or reproducible observation that is specific to the decision context.
- `CORROBORATED`: directly supported by at least two genuinely independent, applicable primary lineages.
- `SUPPORTED`: directly supported by at least one credible, applicable lineage, but independent confirmation is absent or incomplete.
- `INFERRED`: reasoned from cited evidence, with the inference and assumptions stated explicitly.
- `CONFLICTING`: credible applicable evidence materially disagrees. Preserve both sides and do not vote.
- `UNKNOWN`: available evidence cannot support a bounded conclusion.
- `NOT_APPLICABLE`: the claim or source class does not apply, with a reason.

Do not classify a vendor claim, benchmark, popularity signal, valid JSON, green test, or repeated derivative coverage as confirmation by itself.

## Evidence record

Every material evidence item should preserve:

- stable source ID, lineage ID, URL or repository locator;
- title, author or publisher, publication date, version, and access date;
- source class and whether it is primary or derivative;
- exact page, section, line, commit, issue, test, timestamp, or other locator;
- bounded quotation or direct observation;
- applicability and transfer assumptions;
- authority, directness, method quality, recency, reproducibility, and independence;
- access class, output handling, and limitations.

Use `UNKNOWN` for unavailable fields rather than inventing them.

## Independent lineages

A lineage is the underlying origin of a claim: one study, dataset, benchmark, press release, interview, incident, repository experiment, or authoritative record. Multiple pages repeating it remain one lineage. A replication using independently collected data may be a new lineage; a reanalysis of the same data is not automatically independent.

## Source preference

Prefer, in order:

1. directly applicable authoritative records and reproducible observations;
2. primary official documentation, standards, specifications, code, tests, datasets, and papers;
3. independent replications and measured production reports;
4. credible practitioner reports with inspectable methods;
5. secondary synthesis that accurately links its primary lineage.

Source authority does not erase poor methods or weak applicability. Recency does not automatically beat a still-current standard. Preserve credible minority evidence.

## Access and disclosure

Record an access class such as `PUBLIC`, `INTERNAL`, or `RESTRICTED`, plus output handling:

- `QUOTE`: bounded excerpts permitted.
- `CITE_ONLY`: identify the source without excerpting restricted content.
- `REDACT`: remove sensitive details while preserving the conclusion's limits.
- `OMIT`: do not expose the evidence in the output.

Restricted material defaults to `CITE_ONLY`, `REDACT`, or `OMIT` unless audience authorization is established. Never infer authorization from retrieval access alone.

## Fact discipline

Keep these distinct:

- observed fact;
- source-reported claim;
- interpretation;
- inference;
- proposal;
- decision.

A canonical fact must identify its supporting evidence IDs, contradicting evidence IDs, classification, scope, and limitations. Material factual prose in the report must resolve to a fact or evidence ID.
