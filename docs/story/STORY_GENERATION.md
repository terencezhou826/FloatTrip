# Evidence-Grounded Story Generation

## Flow

```text
StoryGenerationRequest
  -> StoryBlueprint and ordered StoryChapters
  -> one StoryChapterContext per Chapter
  -> strict structured LLM output
  -> deterministic M2C-derived validation
  -> GeneratedStory
```

The generator gives the LLM one Chapter Context at a time. A Context contains the Chapter, Blueprint, package version, and hydrated production-eligible Knowledge hits with verified supporting Evidence, Source snapshots, promotion policy, approved wording, and required qualifier. It never exposes an unrestricted Catalog and never performs network retrieval.

## Output Contract

`GeneratedStoryChapter` separates curated opening, transition, closing, and takeaway text from `factual_content`. Each factual item names exactly one Claim and must exactly equal that Claim's approved wording, or its statement when no approved wording exists. Required Claims must be used; optional Claims may be omitted.

The Chapter also records used Claim IDs, deterministic Citations, qualifiers used, generation status, warnings, and computed grounding metrics. `GeneratedStory` aggregates Chapters, Claim IDs, Citations, audience, Story version, and the frozen package/schema/content version.

## Safety Validation

Generation reuses the M2C validation boundary and additionally checks:

- Chapter identity and curated text are unchanged.
- Every used Claim belongs to the current Chapter Context and is production eligible.
- Every factual item matches reviewed Claim wording exactly.
- Every Citation identity, locator, quote, Source snapshot, Claim type, policy, and qualifier matches Context.
- Required qualifiers appear in visible narration.
- Mythology is not promoted to unqualified historical fact.
- Unsupported numbers and known fact-promotion phrases are rejected.

The service allows one structured repair attempt using the same Context. It has no free-text fallback. Insufficient Evidence must result in less content, never model-memory supplementation or Knowledge writes.

## Versioning

The generated artifact freezes `package_id`, `schema_version`, `content_version`, and Story version. A later Catalog update cannot silently change the recorded provenance of an already generated Story.
