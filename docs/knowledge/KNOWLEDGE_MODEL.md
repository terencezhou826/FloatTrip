# Cultural Knowledge Model

M2A extends the existing Catalog with a read-only, evidence-grounded cultural
knowledge layer. Knowledge remains package content; it is not a second content
platform and it is not a retrieval system.

## Core Chain

```text
KnowledgeClaim
  -> KnowledgeEvidence
    -> KnowledgeSource
      -> precise locator and URL/document reference
```

Every production-eligible claim must be traceable through this chain. A Source
records where material came from, a Claim records one independently reviewable
statement, and Evidence records how a precise excerpt relates the Source to the
Claim.

## KnowledgeSource

`KnowledgeSource` describes a document or public resource. Its controlled
`source_type` values are:

- `ancient_text`
- `government`
- `academic`
- `local_chronicle`
- `heritage_record`
- `scenic_official`
- `museum`
- `news`
- `tourism_operation`
- `other`

A Source records title, publisher or author, optional publication date, URL
and/or document reference, applicable Regions, language, authority,
verification status, and metadata. At least one of URL or document reference
is required.

## AuthorityLevel

Authority expresses the Source's relationship to the Claim and its material:

- `primary`: first-hand material for the Claim, such as the text of an ancient
  work or an original record
- `authoritative`: a formal government or institutional publication
- `scholarly`: academic research subject to scholarly methods
- `secondary`: a derivative explanation or general secondary source
- `reference_only`: useful for discovery but not sufficiently established

Authority is not a truth score. An ancient text can be a primary source for
what the text says while the narrative it contains remains mythology.
`primary` also describes the underlying material, not necessarily its current
physical carrier. For example, an ancient text accessed through Chinese Text
Project remains primary evidence for what that ancient text says, while
Chinese Text Project is a modern digital transcription and access carrier, not
the ancient physical manuscript itself.

## KnowledgeClaim

A Claim is one atomic statement with stable subjects and optional Region,
Theme, and Anchor references. It contains both display wording and a normalized
form, a controlled type, verification status, promotion policy, optional
validity dates, and metadata.

Controlled `claim_type` values are:

- `historical_fact`
- `mythology`
- `local_legend`
- `academic_interpretation`
- `official_narrative`
- `tourism_operation`
- `geographic_fact`
- `heritage_fact`

Claim type and Source authority are independent. An official page that repeats
a local tradition normally supports an `official_narrative`; it does not by
itself convert that tradition into `historical_fact`.

## VerificationStatus

Sources, Claims, and Evidence use:

- `draft`
- `review_required`
- `verified`
- `rejected`
- `disputed`

For a Claim, `verified` means reviewers confirmed that the statement is
faithful to its cited evidence and correctly typed. It does not assert that
every event described by the statement occurred in physical history.

**Verified mythology is not verified historical fact.** A verified mythology
Claim can accurately represent an ancient narrative while remaining explicitly
mythological.

**Verified official narrative is not historical truth.** It confirms that the
identified institution published the attributed statement and that the Claim
represents it faithfully; independent historical verification still requires
evidence appropriate to a historical-fact Claim.

`disputed` preserves competing evidence and is not production eligible by
default. `rejected` is retained for audit purposes and is also ineligible.

## KnowledgeEvidence

Evidence connects one Claim to one Source. It includes a structured locator, a
short quote excerpt, a controlled relationship, verification status, and
metadata. The locator supports page, chapter, volume, paragraph, URL fragment,
line range, or another bounded description. At least one locator field is
required, and quote excerpts are limited to 1,000 characters.

Evidence relationships are:

- `supports`
- `contradicts`
- `contextualizes`
- `mentions`

Contradictory evidence is valid Catalog data. Validation checks references and
coverage; it does not force competing sources into a single conclusion.

## PromotionPolicy

Promotion policy is separate from verification:

- `allowed`
- `allowed_with_qualification`
- `internal_only`
- `forbidden`

The policy can provide approved wording, a required qualifier, and forbidden
wordings. `allowed_with_qualification` requires at least approved wording or a
required qualifier. This supports expressions such as "according to the text"
or "tradition holds" without adding route-specific rules to Python code.
Retrieval and Generation must carry the applicable `required_qualifier` or
`approved_wording` forward and must not paraphrase away a qualification in a
way that raises the Claim's factual status.

## Production Eligibility

`CatalogRepository.is_claim_production_eligible()` returns true only when:

1. the Claim status is `verified`;
2. its policy is neither `internal_only` nor `forbidden`;
3. it has at least one `verified` Evidence with relation `supports`;
4. that Evidence points to a `verified` Source.

Draft, review-required, disputed, rejected, unsupported, and policy-blocked
Claims are false by default. M2A defines this boundary but does not connect it
to Planning, prompts, or retrieval.

## Evidence Coverage

Catalog validation computes:

```text
verified Claims with verified supporting Evidence from a verified Source
--------------------------------------------------------------------------
                         all verified Claims
```

The required ratio is `1.0`. If there are no verified Claims, the ratio is
defined as `1.0` because no verified Claim is uncovered. Draft,
review-required, disputed, and rejected Claims are excluded from the
denominator.

## Storage And Loading

Each content package can have an optional `knowledge/` directory. Files are
loaded recursively in sorted path order. Every JSON file contains exactly one
of these collections:

- `sources`
- `claims`
- `evidence`

This permits future sharding by subject, county, source family, or release
without changing the Loader. A package without `knowledge/` loads empty
collections and remains backward compatible. IDs are globally unique across
Catalog entity types, and all Region, Theme, Anchor, Claim, and Source
references are validated.
