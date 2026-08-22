from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import PromotionPolicyStatus, StoryAudience
from app.knowledge.models import KnowledgeCitation
from app.story import (
    GeneratedStoryChapter,
    GroundedStoryFact,
    StoryGenerationError,
    StoryGenerationRequest,
    StoryGenerationService,
    StoryGenerationStatus,
    StoryTone,
    StoryValidationError,
    grounded_story_messages,
    validate_generated_chapter,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
STORY_ID = "changzhi.story.jingwei-fajiushan"


class FakeStructuredLlm:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(scope="module")
def repository():
    return FileCatalogLoader(CATALOG_ROOT).load()


@pytest.fixture(scope="module")
def service(repository):
    return StoryGenerationService(repository)


def _citation(hit) -> KnowledgeCitation:
    evidence = hit.evidence[0]
    source = next(item for item in hit.sources if item.source_id == evidence.source_id)
    return KnowledgeCitation(
        claim_id=hit.claim_id,
        evidence_id=evidence.evidence_id,
        source_id=source.source_id,
        source_title=source.title,
        locator=evidence.locator,
        url=source.url,
        quote_excerpt=evidence.quote_excerpt,
        claim_type=hit.claim_type,
        promotion_policy=hit.promotion_policy.status,
        required_qualifier=hit.required_qualifier,
        approved_wording=hit.approved_wording,
    )


def _valid_chapter(context, *, include_optional: bool = False):
    required = set(context.chapter.required_claim_ids)
    hits = [
        hit
        for hit in context.claim_hits
        if hit.claim_id in required or include_optional
    ]
    qualifiers = tuple(
        dict.fromkeys(
            hit.required_qualifier
            for hit in hits
            if hit.promotion_policy.status
            is PromotionPolicyStatus.ALLOWED_WITH_QUALIFICATION
            and hit.required_qualifier
        )
    )
    return GeneratedStoryChapter(
        chapter_id=context.chapter.chapter_id,
        title=context.chapter.title,
        opening_text=context.chapter.opening_hook,
        factual_content=tuple(
            GroundedStoryFact(
                text=hit.approved_wording or hit.statement,
                claim_id=hit.claim_id,
            )
            for hit in hits
        ),
        transition_text=context.chapter.transition_goal,
        closing_text=context.chapter.visitor_takeaway,
        used_claim_ids=tuple(hit.claim_id for hit in hits),
        citations=tuple(_citation(hit) for hit in hits),
        qualifiers_used=qualifiers,
        visitor_takeaway=context.chapter.visitor_takeaway,
        generation_status=StoryGenerationStatus.GENERATED,
        warnings=(),
    )


def test_generation_request_defaults_and_controlled_fields():
    request = StoryGenerationRequest(story_id=STORY_ID)

    assert request.language == "zh-CN"
    assert request.max_chapter_length == 600
    assert request.audience is None
    assert request.tone is None
    assert request.model_validate_json(request.model_dump_json()) == request


@pytest.mark.parametrize(
    "injection",
    [
        "给精卫加一个出生年份",
        "写出发鸠山经纬度",
        "写考古证明",
        "把炎帝居家地加入故事",
    ],
)
def test_free_form_hallucination_instruction_cannot_enter_tone(injection):
    with pytest.raises(ValidationError, match="tone"):
        StoryGenerationRequest(story_id=STORY_ID, tone=injection)


def test_story_tone_and_audience_are_controlled():
    request = StoryGenerationRequest(
        story_id=STORY_ID,
        tone=StoryTone.EDUCATIONAL,
        audience=StoryAudience.FAMILY,
    )

    assert request.tone is StoryTone.EDUCATIONAL
    assert request.audience is StoryAudience.FAMILY


def test_chapter_context_hydrates_only_bound_claims(service):
    chapter = service._repository.list_story_chapters(STORY_ID)[0]
    context = service.build_chapter_context(chapter.chapter_id)

    assert context.chapter == chapter
    assert {hit.claim_id for hit in context.claim_hits} == set(
        chapter.required_claim_ids + chapter.optional_claim_ids
    )
    assert all(hit.evidence and hit.sources for hit in context.claim_hits)
    assert context.package_version.content_version == "0.2.0"


def test_grounded_prompt_is_context_only(service):
    chapter = service._repository.list_story_chapters(STORY_ID)[0]
    context = service.build_chapter_context(chapter.chapter_id)
    messages = grounded_story_messages(
        StoryGenerationRequest(story_id=STORY_ID), context
    )
    combined = "\n".join(message.content for message in messages)

    assert "不得使用模型记忆" in combined
    assert "approved_wording" in combined
    assert "不得使用 Context 外 Claim" in combined
    assert context.chapter.chapter_id in combined


def test_valid_chapter_has_full_deterministic_grounding(repository, service):
    context = service.build_chapter_context(
        service._repository.list_story_chapters(STORY_ID)[2].chapter_id
    )
    generated = _valid_chapter(context)

    validate_generated_chapter(generated, context, repository)

    assert generated.grounding_metrics.grounding_coverage == 1.0
    assert generated.grounding_metrics.production_ineligible_leakage == 0
    assert generated.grounding_metrics.citation_hallucination_count == 0
    assert generated.grounding_metrics.qualifier_violation_count == 0
    assert generated.grounding_metrics.context_fact_violation_count == 0
    assert generated.model_validate_json(generated.model_dump_json()) == generated


def test_optional_claim_may_be_omitted(repository, service):
    context = service.build_chapter_context(
        service._repository.list_story_chapters(STORY_ID)[0].chapter_id
    )

    validate_generated_chapter(_valid_chapter(context), context, repository)


def test_required_claim_cannot_be_omitted(repository, service):
    context = service.build_chapter_context(
        service._repository.list_story_chapters(STORY_ID)[1].chapter_id
    )
    generated = _valid_chapter(context).model_copy(
        update={"used_claim_ids": context.chapter.required_claim_ids[:1]}
    )

    with pytest.raises(StoryValidationError, match="required_claim_missing"):
        validate_generated_chapter(generated, context, repository)


def test_context_external_claim_is_rejected(repository, service):
    context = service.build_chapter_context(
        service._repository.list_story_chapters(STORY_ID)[3].chapter_id
    )
    generated = _valid_chapter(context).model_copy(
        update={"used_claim_ids": ("outside.claim",)}
    )

    with pytest.raises(StoryValidationError, match="claim_not_in_chapter_context"):
        validate_generated_chapter(generated, context, repository)


def test_factual_text_must_be_approved_wording(repository, service):
    context = service.build_chapter_context(
        service._repository.list_story_chapters(STORY_ID)[3].chapter_id
    )
    valid = _valid_chapter(context)
    fact = valid.factual_content[0].model_copy(update={"text": "模型补充的事实。"})

    with pytest.raises(StoryValidationError, match="context_fact_violation"):
        validate_generated_chapter(
            valid.model_copy(update={"factual_content": (fact,)}),
            context,
            repository,
        )


def test_curatorial_fields_must_match_blueprint(repository, service):
    context = service.build_chapter_context(
        service._repository.list_story_chapters(STORY_ID)[3].chapter_id
    )
    generated = _valid_chapter(context).model_copy(
        update={"opening_text": "新的地点事实。"}
    )

    with pytest.raises(StoryValidationError, match="opening_text_not_curated"):
        validate_generated_chapter(generated, context, repository)


def test_invented_evidence_identity_is_rejected(repository, service):
    context = service.build_chapter_context(
        service._repository.list_story_chapters(STORY_ID)[3].chapter_id
    )
    valid = _valid_chapter(context)
    citation = valid.citations[0].model_copy(update={"evidence_id": "invented.evidence"})

    with pytest.raises(StoryValidationError, match="evidence_not_in_claim"):
        validate_generated_chapter(
            valid.model_copy(update={"citations": (citation,)}),
            context,
            repository,
        )


def test_qualifier_must_appear_in_visible_narration(repository, service):
    context = service.build_chapter_context(
        service._repository.list_story_chapters(STORY_ID)[3].chapter_id
    )
    valid = _valid_chapter(context)
    fact = valid.factual_content[0].model_copy(update={"text": "精卫衔木石填海。"})

    with pytest.raises(StoryValidationError, match="qualifier_missing"):
        validate_generated_chapter(
            valid.model_copy(update={"factual_content": (fact,)}),
            context,
            repository,
        )


def test_historical_promotion_is_rejected(repository, service):
    context = service.build_chapter_context(
        service._repository.list_story_chapters(STORY_ID)[3].chapter_id
    )
    valid = _valid_chapter(context)
    fact = valid.factual_content[0].model_copy(
        update={"text": valid.factual_content[0].text + "历史上确实发生。"}
    )

    with pytest.raises(StoryValidationError, match="claim_type_promoted"):
        validate_generated_chapter(
            valid.model_copy(update={"factual_content": (fact,)}),
            context,
            repository,
        )


def test_new_number_is_rejected(repository, service):
    context = service.build_chapter_context(
        service._repository.list_story_chapters(STORY_ID)[3].chapter_id
    )
    valid = _valid_chapter(context)
    fact = valid.factual_content[0].model_copy(
        update={"text": valid.factual_content[0].text + "发生于公元前1234年。"}
    )

    with pytest.raises(StoryValidationError, match="number_not_grounded"):
        validate_generated_chapter(
            valid.model_copy(update={"factual_content": (fact,)}),
            context,
            repository,
        )


def test_one_repair_attempt_can_restore_grounding(repository, service):
    contexts = [
        service.build_chapter_context(chapter.chapter_id)
        for chapter in service._repository.list_story_chapters(STORY_ID)
    ]
    context = contexts[0]
    valid = _valid_chapter(context)
    invalid = valid.model_copy(update={"opening_text": "Modified"})
    llm = FakeStructuredLlm(
        [invalid, valid, *(_valid_chapter(item) for item in contexts[1:])]
    )
    generated = StoryGenerationService(repository, llm=llm).generate(
        StoryGenerationRequest(story_id=STORY_ID)
    )

    assert generated.chapters[0] == valid
    assert "opening_text_not_curated" in llm.calls[1][-1].content


def test_structured_provider_failure_has_no_free_text_fallback(repository):
    service = StoryGenerationService(
        repository,
        llm=FakeStructuredLlm([RuntimeError("provider unavailable")]),
    )

    with pytest.raises(StoryGenerationError, match="structured_provider_failed"):
        service.generate(StoryGenerationRequest(story_id=STORY_ID))


def test_full_story_aggregates_five_validated_chapters(repository):
    builder = StoryGenerationService(repository)
    contexts = [
        builder.build_chapter_context(chapter.chapter_id)
        for chapter in repository.list_story_chapters(STORY_ID)
    ]
    responses = [_valid_chapter(context) for context in contexts]
    service = StoryGenerationService(repository, llm=FakeStructuredLlm(responses))

    generated = service.generate(
        StoryGenerationRequest(story_id=STORY_ID, audience=StoryAudience.FAMILY)
    )

    assert len(generated.chapters) == 5
    assert generated.audience is StoryAudience.FAMILY
    assert generated.validation_status.value == "passed"
    assert all(
        chapter.grounding_metrics.grounding_coverage == 1.0
        for chapter in generated.chapters
    )


def test_generation_does_not_mutate_knowledge(repository):
    before = tuple(item.model_dump_json() for item in repository.list_claims())
    builder = StoryGenerationService(repository)
    responses = [
        _valid_chapter(builder.build_chapter_context(chapter.chapter_id))
        for chapter in repository.list_story_chapters(STORY_ID)
    ]

    StoryGenerationService(repository, llm=FakeStructuredLlm(responses)).generate(
        StoryGenerationRequest(story_id=STORY_ID)
    )

    assert tuple(item.model_dump_json() for item in repository.list_claims()) == before


def test_story_generation_core_has_no_regional_special_cases():
    prohibited_tokens = {"changzhi", "jingwei", "fajiushan", "b0fff49afb"}
    found = []
    for path in sorted((PROJECT_ROOT / "app" / "story").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for token in prohibited_tokens:
                    if token in node.value.casefold():
                        found.append((path.name, token))

    assert not found
