# Evidence-Aware Knowledge Retrieval

M2B adds a deterministic, read-only retrieval layer over a single Catalog
package snapshot. It does not generate answers, call an LLM, access the
internet, or connect Knowledge to Planning.

## Pipeline

```text
KnowledgeQuery
  -> package-scoped structured filters
  -> production eligibility gate
  -> deterministic lexical ranking
  -> Evidence and Source hydration
  -> KnowledgeHit
  -> KnowledgeContext
```

Filtering precedes ranking. A high lexical score can never make an ineligible
Claim retrievable.

## Production Filter

Default retrieval requires all of the following:

1. the Claim is `verified`;
2. its promotion policy is `allowed` or `allowed_with_qualification`;
3. it has at least one `verified` Evidence whose relation is `supports`;
4. the supporting Evidence refers to a `verified` Source in the selected
   package snapshot.

Draft, review-required, rejected, disputed, internal-only, forbidden, and
unsupported Claims are excluded by default. `include_disputed=true` is an
explicit review-oriented opt-in: a disputed Claim must still have an allowed
policy and verified supporting Evidence from a verified Source. Returned
contexts warn when disputed Claims are present.

## Structured Scope

`KnowledgeQuery` supports Region, Theme, Anchor, and Claim-type filters. Across
filter categories the behavior is AND; within one category, a Claim matches if
it overlaps any requested ID. An empty `query_text` is valid, so callers can
browse a structured scope without inventing search text.

Retrieval starts from the selected `ContentPackage`, rather than the
repository-wide union, so the resulting context records and reflects one
package, schema version, and content version.

## Lexical Matching

M2B uses only the Python standard library. Text is Unicode NFKC-normalized and
case-folded. Chinese runs are represented by character bigrams and trigrams;
Latin letters and numbers use word tokens. Matching considers:

- Claim statement;
- normalized statement;
- Source title;
- controlled Claim-type terms.

A small content-neutral Chinese query vocabulary handles common question forms
such as appearance, cause, location, and historical-status questions. Ordered
character subsequence matching handles intervening characters, such as a query
term that is separated by a directional word. These rules contain no Region,
route, Theme, Anchor, or mythology-specific identifiers.

A non-empty query with no meaningful lexical or intent match returns an empty
context with `no_matching_production_knowledge`; it does not fall back to
unrelated content. If results share lexical fragments but none has an exact,
expanded, subsequence, causal, or Claim-type relevance match, the context adds
`insufficient_direct_match` so downstream code cannot mistake weak topical
overlap for sufficient knowledge.

## Ranking And Explanations

Scores express retrieval relevance, not truth probability. Current weights
are:

- Anchor filter match: 8
- Theme filter match: 6
- Region filter match: 4
- Claim-type filter match: 2
- exact normalized query: 12
- normalized-statement n-gram match: 2 per unit
- statement n-gram match: 1.5 per unit
- Source-title n-gram match: 0.75 per unit
- generic query-expansion match: 3 per term
- causal marker match for a causal query: 7
- ordered subsequence match: 6
- inferred Claim-type relevance: 12
- Source relationship tie-break: 0.25 for primary, authoritative, or scholarly;
  0.1 for secondary; 0 for reference-only

Primary, authoritative, and scholarly Sources deliberately receive the same
small tie-break weight. `AuthorityLevel` describes the Source's relationship
to its material; it is not a truth hierarchy.

Every hit records stable, deterministic `match_reasons`, such as
`anchor_match`, `normalized_statement_match`, `query_expansion_match`,
`claim_type_relevance`, and `source_authority_primary`. Ties are resolved by
`claim_id`.

## Qualifier Preservation

Each hit carries both the complete `PromotionPolicy` and flattened
`required_qualifier` and `approved_wording` fields. An
`allowed_with_qualification` Claim therefore cannot enter a context without
the wording needed to preserve its factual level. M2B does not paraphrase or
generate final prose.

## Evidence And Source Hydration

All verified Evidence attached to a returned Claim is retained when its Source
is also verified. Verified `supports` Evidence is ordered first and establishes
eligibility. Verified `contradicts`, `contextualizes`, and `mentions` Evidence
may follow as supporting context but never substitutes for `supports`.

Evidence snapshots preserve Evidence ID, Source ID, relation, locator, and
quote excerpt. Deduplicated Source snapshots preserve Source ID, title, type,
authority, publisher or author, publication date, URL, and document reference.
The model supports multiple Evidence records and multiple Sources per Claim.

## Snapshot And Network Boundary

`KnowledgeContext` is frozen and JSON-serializable. It records `package_id`,
`schema_version`, and `content_version`, and embeds the provenance needed to
understand a saved result even if a public URL later becomes unavailable.

Runtime retrieval reads only the local Catalog snapshot. Source URLs are audit
and provenance fields; retrieval never dereferences them.

## Future Embedding Boundary

An embedding or vector candidate generator may be added later, but it must sit
after the same production gate and before the same Evidence/Source hydration
boundary. It must not weaken eligibility, remove qualifiers, replace stable
IDs, or turn ranking scores into truth probabilities. M2B itself has no
Embedding, vector database, query rewrite, reranker, or answer-generation
dependency.
