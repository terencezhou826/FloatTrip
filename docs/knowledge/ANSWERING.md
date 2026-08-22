# Evidence-Grounded Cultural Answering

M2C adds a standalone cultural Knowledge answer service over the production-safe
M2B Retriever. It is not connected to Planning, Chat, Runtime, Story, or any
user interface.

```text
KnowledgeAnswerRequest
  -> KnowledgeRetriever
  -> KnowledgeContext
  -> deterministic Answerability Gate
  -> strict structured LLM
  -> GroundedKnowledgeAnswer
  -> deterministic validation
```

**LLM is a renderer/reasoner over approved evidence, not a source of cultural
facts.**

## KnowledgeContext

The service builds a package-scoped M2B `KnowledgeContext` from the question
and optional Region, Theme, Anchor, and Claim-type filters. The default
retrieval limit is 10 so a broad question can retain ancient-text, mythology,
and official-narrative Claims even when one source family ranks higher.

M2C does not rerank or rewrite the M2B result. Source diversity comes from the
larger deterministic Context and a prompt rule that keeps different source
types distinct.

## Answerability Gate

The Gate runs before any LLM call and returns `direct_support`,
`partial_support`, or `insufficient`. It considers:

- verified `supports` Evidence retained by M2B;
- direct and structured `match_reasons`;
- retrieval score diagnostics;
- `no_matching_production_knowledge` and `insufficient_direct_match` warnings;
- whether a request for a precise year, coordinate, or archaeological finding
  has corresponding evidence in the Context.

An insufficient decision bypasses the LLM and returns the deterministic text:
"现有可用于公开输出的已核验资料不足以确认这一说法。"

## Grounded Prompt

The dedicated system prompt says that the model may use only the supplied
`KnowledgeContext`. It forbids model memory, external facts, invented IDs,
new people, dates, places, coordinates, events, and archaeological conclusions.
It also preserves Claim types, source distinctions, promotion qualifiers, and
the exact Citation snapshot.

The Context and answerability decision are serialized into a data-only human
message. Source URLs are provenance fields and are never dereferenced by the
service.

## Structured Output

`build_structured_llm(GroundedKnowledgeAnswer, temperature=0)` binds every
required field through strict function calling. The service never parses free
text. A provider error fails explicitly. Schema or grounding validation can
receive one repair attempt using the same original Context; a second failure
closes with `validation_failed`.

## Qualifier Preservation

For every used `allowed_with_qualification` Claim, deterministic validation
requires the answer to contain either the exact `required_qualifier` or the
complete `approved_wording`. The same text must appear in `qualifiers_used`.
Allowed Claims without a qualification policy receive no artificial prefix.

This ensures that mythology remains attributed to its narrative source and an
official narrative remains attributed to the publishing institution.

## Claim Type Preservation

The validator rejects certainty language such as "历史上确实发生",
"真实发生", "已经证实", or "考古证明" when mythology or local-legend
Claims are used. A textual `historical_fact` cannot be used with the same
language to promote the text's narrative into a verified historical event.

Numbers in the answer must already occur in the question or frozen Context.
This blocks invented years and coordinates without attempting unrestricted
natural-language fact checking.

## Citation Validation

Every non-insufficient answer requires at least one used Claim and Citation.
Every used Claim must be cited. Validation checks that:

- the Claim exists in the current Context and remains production eligible;
- the Citation Claim is listed in `used_claim_ids`;
- Evidence belongs to the Claim and has relation `supports`;
- Source belongs to that Evidence;
- locator, quote excerpt, source title, and URL exactly match the Context;
- Claim type, policy, qualifier, and approved wording exactly match the Hit.

Context-external, internal-only, review-required, invented, or modified
identities therefore fail closed.

## Grounding Coverage

`GroundedKnowledgeAnswer` exposes deterministic derived metrics:

- `used_claim_count`
- `citation_count`
- `qualified_claim_count`
- `qualifier_satisfied_count`
- `grounding_coverage`

Coverage is:

```text
cited used Claims + qualifier-satisfied qualified Claims
--------------------------------------------------------
used Claims + qualified Claims
```

An evidence-free insufficient answer has coverage 1.0 because it makes no
cultural Claim. Validated factual answers must also reach 1.0 because every
used Claim requires a Citation and every qualified Claim requires its wording.

## Insufficient Evidence

Weak topical overlap cannot substitute for direct evidence. Questions that ask
for a fact excluded from the production corpus, or for an unsupported year,
coordinate, or archaeological conclusion, are rejected before generation.
Related Claims are not presented as though they answer the unsupported premise.

## Memory Isolation And Boundaries

The only cultural facts available to the LLM are the frozen fields in
`KnowledgeContext`. M2C does not use model memory as evidence, fetch Source
URLs, inspect map bindings, ingest data, generate Claims or Evidence, call an
Embedding service, or access a vector database.

Future integrations must preserve the same Gate, strict schema, Citation
identity checks, qualifiers, Claim types, Catalog version, and fail-closed
behavior. M2C itself does not connect the answer service to Planning or Chat.
