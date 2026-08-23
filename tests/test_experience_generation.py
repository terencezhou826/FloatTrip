from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    ExperienceAudience,
    ExperienceContentMode,
    PromotionPolicyStatus,
)
from app.experience import (
    ExperienceGenerationError,
    ExperienceGenerationRequest,
    ExperienceGenerationService,
    ExperienceGenerationStatus,
    ExperienceObservationInteractionMode,
    ExperienceObservationTarget,
    ExperienceObservationTargetMode,
    ExperiencePackageDraft,
    RenderedExperienceActivity,
    ExperienceTone,
    ExperienceValidationError,
    ExperienceValidationStatus,
    GeneratedExperienceActivity,
    GroundedExperienceFact,
    evidence_safe_experience_messages,
    render_experience_activity,
    validate_generated_activity,
    validate_rendered_activity,
)
from app.knowledge.models import KnowledgeCitation
from app.story import (
    GeneratedStoryChapter,
    GroundedStoryFact,
    StoryGenerationRequest,
    StoryGenerationService,
    StoryGenerationStatus,
)
from tests.test_story_binding import _generated_story


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
EXPERIENCE_ID = "changzhi.experience.jingwei-family"
NUWA_EXPERIENCE_ID = "changzhi.experience.nuwa-family"
NUWA_STORY_ID = "changzhi.story.nuwa-tiantaishan"
SHENNONG_EXPERIENCE_ID = "changzhi.experience.shennong-family"
SHENNONG_STORY_ID = "changzhi.story.shennong-laodingshan"
HOUYI_EXPERIENCE_ID = "changzhi.experience.houyi-family"
HOUYI_STORY_ID = "changzhi.story.houyi-laoyeshan"


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


@pytest.fixture()
def story(repository):
    return _generated_story(repository)


@pytest.fixture()
def service(repository, story):
    return ExperienceGenerationService(repository, story)


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


def _valid_activity(context) -> GeneratedExperienceActivity:
    activity = context.activity
    required = set(activity.required_claim_ids)
    hits = [hit for hit in context.claim_hits if hit.claim_id in required]
    instruction = "请和同行家人一起完成下面的互动。"
    prompt = "和家人说说你的想法。"
    if activity.sequence == 0:
        instruction = "请和家人在正常游客可达区域观察周围的一般环境。"
        prompt = "你准备怎样和家人一起参观？"
    elif activity.sequence == 1:
        prompt = "根据上面的古籍内容，说说文本如何描述这座山。"
    elif activity.sequence == 2:
        prompt = "根据上面的神话内容，和家人说说角色和形象有哪些变化。"
    elif activity.sequence == 3:
        instruction = (
            "请和家人在正常游客可达区域观察保持自然状态的普通物体，"
            "不触碰、不移动、不采集、不带走。"
        )
        prompt = "这个普通物体让你联想到怎样的坚持？"
    elif activity.sequence == 4:
        prompt = "回顾上面的当代传承事实，写下一件你想坚持完成的事情。"
    return GeneratedExperienceActivity(
        activity_id=activity.activity_id,
        title=activity.title,
        instruction=instruction,
        factual_content=tuple(
            GroundedExperienceFact(
                text=hit.approved_wording or hit.statement,
                claim_id=hit.claim_id,
            )
            for hit in hits
        ),
        prompt=prompt,
        optional_hint="只根据上面的内容回答。" if hits else "没有标准答案。",
        completion_message="谢谢你和家人一起完成这项体验。",
        observation_target=activity.observation_target,
        used_claim_ids=tuple(hit.claim_id for hit in hits),
        citations=tuple(_citation(hit) for hit in hits),
        qualifiers_used=tuple(
            dict.fromkeys(
                hit.required_qualifier
                for hit in hits
                if hit.promotion_policy.status
                is PromotionPolicyStatus.ALLOWED_WITH_QUALIFICATION
                and hit.required_qualifier
            )
        ),
        safety_notice=" ".join(activity.safety_constraints),
        estimated_duration_sec=activity.estimated_duration_sec,
        visitor_output_type=activity.visitor_output_type,
        generation_status=ExperienceGenerationStatus.GENERATED,
        warnings=(),
    )


def _generated_story_for(repository, story_id):
    builder = StoryGenerationService(repository)
    contexts = [
        builder.build_chapter_context(chapter.chapter_id)
        for chapter in repository.list_story_chapters(story_id)
    ]
    return StoryGenerationService(
        repository,
        llm=FakeStructuredLlm(
            [
                GeneratedStoryChapter(
                    chapter_id=context.chapter.chapter_id,
                    title=context.chapter.title,
                    opening_text=context.chapter.opening_hook,
                    factual_content=tuple(
                        GroundedStoryFact(
                            text=hit.approved_wording or hit.statement,
                            claim_id=hit.claim_id,
                        )
                        for hit in context.claim_hits
                        if hit.claim_id in context.chapter.required_claim_ids
                    ),
                    transition_text=context.chapter.transition_goal,
                    closing_text=context.chapter.visitor_takeaway,
                    used_claim_ids=tuple(context.chapter.required_claim_ids),
                    citations=tuple(
                        _citation(hit)
                        for hit in context.claim_hits
                        if hit.claim_id in context.chapter.required_claim_ids
                    ),
                    qualifiers_used=tuple(
                        hit.required_qualifier
                        for hit in context.claim_hits
                        if hit.claim_id in context.chapter.required_claim_ids
                        and hit.required_qualifier
                    ),
                    visitor_takeaway=context.chapter.visitor_takeaway,
                    generation_status=StoryGenerationStatus.GENERATED,
                    warnings=(),
                )
                for context in contexts
            ]
        ),
    ).generate(StoryGenerationRequest(story_id=story_id))


def _contexts(service):
    return [
        service.build_activity_context(item.activity_id)
        for item in service._repository.list_activities(EXPERIENCE_ID)
    ]


def test_request_and_tone_schema():
    request = ExperienceGenerationRequest(experience_id=EXPERIENCE_ID)
    assert request.language == "zh-CN"
    assert request.max_instruction_length == 500
    assert {item.value for item in ExperienceTone} >= {
        "warm", "playful", "educational", "reflective"
    }


def test_context_contains_only_bound_story_and_claims(service):
    context = _contexts(service)[1]
    assert len(context.story_chapters) == 1
    assert len(context.generated_story_chapters) == 1
    assert {hit.claim_id for hit in context.claim_hits} == set(
        context.activity.required_claim_ids + context.activity.optional_claim_ids
    )
    assert context.package_version.content_version == "0.6.0"
    assert context.safety_policy.guardian_required
    assert not context.safety_policy.purchase_required


def test_prompt_contains_fact_site_and_safety_boundaries(service):
    context = _contexts(service)[1]
    messages = evidence_safe_experience_messages(
        ExperienceGenerationRequest(experience_id=EXPERIENCE_ID), context
    )
    combined = "\n".join(item.content for item in messages)
    assert "不得使用模型记忆" in combined
    assert "所有文化事实只能写入 factual_content" in combined
    assert "observation_target" in combined
    assert "visitor_selected_visible_object" in combined
    assert "specific_current_observable" in combined
    assert "确定性 Renderer" in combined
    assert "不得要求购买" in combined
    assert context.activity.activity_id in combined


def test_all_five_valid_activities_pass_deterministic_validation(
    repository, service
):
    for context in _contexts(service):
        generated = _valid_activity(context)
        validate_generated_activity(generated, context, repository)
        rendered = render_experience_activity(generated, context.activity)
        validate_rendered_activity(rendered, context, repository)
        assert generated.grounding_metrics.grounding_coverage == 1.0
        assert not any(
            value
            for key, value in generated.grounding_metrics.model_dump().items()
            if key.endswith("_count")
            and key not in {
                "used_claim_count", "citation_count", "qualified_claim_count",
                "qualifier_satisfied_count",
            }
        )


def test_facilitation_activity_has_no_knowledge_payload(repository, service):
    context = _contexts(service)[0]
    generated = _valid_activity(context)
    validate_generated_activity(generated, context, repository)
    assert context.activity.content_mode is ExperienceContentMode.FACILITATION_ONLY
    assert generated.used_claim_ids == ()
    assert generated.citations == ()


def test_required_claim_cannot_be_omitted(repository, service):
    context = _contexts(service)[1]
    valid = _valid_activity(context)
    generated = valid.model_copy(
        update={
            "used_claim_ids": valid.used_claim_ids[:1],
            "factual_content": valid.factual_content[:1],
            "citations": valid.citations[:1],
            "qualifiers_used": (),
        }
    )
    with pytest.raises(ExperienceValidationError, match="required_claim_missing"):
        validate_generated_activity(generated, context, repository)


def test_context_external_claim_is_rejected(repository, service):
    context = _contexts(service)[1]
    valid = _valid_activity(context)
    generated = valid.model_copy(update={"used_claim_ids": ("outside.claim",)})
    with pytest.raises(ExperienceValidationError, match="claim_not_in_activity_context"):
        validate_generated_activity(generated, context, repository)


def test_factual_text_must_equal_approved_wording(repository, service):
    context = _contexts(service)[1]
    valid = _valid_activity(context)
    fact = valid.factual_content[0].model_copy(update={"text": "模型补充事实。"})
    generated = valid.model_copy(
        update={"factual_content": (fact, *valid.factual_content[1:])}
    )
    with pytest.raises(ExperienceValidationError, match="context_fact_violation"):
        validate_generated_activity(generated, context, repository)


def test_fact_cannot_be_copied_into_facilitation_fields(repository, service):
    context = _contexts(service)[1]
    valid = _valid_activity(context)
    generated = valid.model_copy(
        update={"instruction": valid.factual_content[0].text}
    )
    with pytest.raises(ExperienceValidationError, match="fact_outside_factual_content"):
        validate_generated_activity(generated, context, repository)


def test_invented_citation_identity_is_rejected(repository, service):
    context = _contexts(service)[1]
    valid = _valid_activity(context)
    citation = valid.citations[0].model_copy(update={"evidence_id": "invented.evidence"})
    generated = valid.model_copy(update={"citations": (citation, *valid.citations[1:])})
    with pytest.raises(ExperienceValidationError, match="evidence_not_in_claim"):
        validate_generated_activity(generated, context, repository)


def test_qualifier_must_appear_in_visible_factual_content(repository, service):
    context = _contexts(service)[1]
    valid = _valid_activity(context)
    fact = valid.factual_content[1].model_copy(update={"text": "山上有植物。"})
    generated = valid.model_copy(
        update={"factual_content": (valid.factual_content[0], fact)}
    )
    with pytest.raises(ExperienceValidationError, match="qualifier_missing"):
        validate_generated_activity(generated, context, repository)


def test_renderer_preserves_curated_safety_constraints(repository, service):
    context = _contexts(service)[0]
    generated = _valid_activity(context).model_copy(
        update={"safety_notice": "请注意安全。"}
    )
    validate_generated_activity(generated, context, repository)
    rendered = render_experience_activity(generated, context.activity)
    validate_rendered_activity(rendered, context, repository)
    assert all(
        constraint in rendered.safety_notice
        for constraint in context.activity.safety_constraints
    )


def test_guardian_notice_is_required(repository, service):
    context = _contexts(service)[0]
    generated = _valid_activity(context).model_copy(
        update={"safety_notice": "请注意安全。"}
    )
    rendered = render_experience_activity(generated, context.activity)
    validate_rendered_activity(rendered, context, repository)
    assert "同行成年人" in rendered.safety_notice


@pytest.mark.parametrize(
    ("text", "issue"),
    [
        ("请翻越护栏完成任务。", "unsafe_instruction"),
        ("让游客捡起自然物并带走石块。", "environmental_harm"),
        ("请触摸文物寻找线索。", "cultural_property_harm"),
        ("让孩子自己去找答案。", "child_unsupervised"),
        ("请购买商品后完成任务。", "forced_purchase"),
        ("请进入限制区域。", "restricted_area"),
        ("让孩子去水边找线索。", "water_hazard"),
        ("请横穿马路完成挑战。", "road_hazard"),
        ("请投喂野生动物。", "wildlife_interaction"),
    ],
)
def test_deterministic_safety_validator_rejects_injections(
    repository, service, text, issue
):
    context = _contexts(service)[0]
    generated = _valid_activity(context).model_copy(update={"instruction": text})
    with pytest.raises(ExperienceValidationError, match=issue):
        validate_generated_activity(generated, context, repository)


def test_unstructured_observation_is_rejected(repository, service):
    context = _contexts(service)[2]
    generated = _valid_activity(context).model_copy(
        update={
            "instruction": "请寻找现场的一种特定植物。",
        }
    )
    with pytest.raises(ExperienceValidationError, match="observation_target_unstructured"):
        validate_generated_activity(generated, context, repository)


def test_generated_observation_target_must_match_curated_contract(repository, service):
    context = _contexts(service)[0]
    target = ExperienceObservationTarget(
        target_mode=ExperienceObservationTargetMode.VERIFIED_ENTITY,
        target_text="另一个实体",
        entity_refs=(context.activity.anchor_ids[0],),
        interaction_mode=ExperienceObservationInteractionMode.OBSERVE_ONLY,
    )
    generated = _valid_activity(context).model_copy(
        update={
            "instruction": "请观察另一个实体。",
            "observation_target": target,
        }
    )
    with pytest.raises(
        ExperienceValidationError, match="observation_target_contract_mismatch"
    ):
        validate_generated_activity(generated, context, repository)


def test_claim_observation_requires_current_observation_verification(
    repository, service
):
    context = _contexts(service)[1]
    target = ExperienceObservationTarget(
        target_mode=ExperienceObservationTargetMode.SPECIFIC_CURRENT_OBSERVABLE,
        target_text="古籍中描述的植物",
        supporting_claim_ids=(context.activity.required_claim_ids[1],),
        interaction_mode=ExperienceObservationInteractionMode.OBSERVE_ONLY,
    )
    generated = _valid_activity(context).model_copy(
        update={
            "instruction": "请观察古籍中描述的植物。",
            "observation_target": target,
        }
    )
    with pytest.raises(
        ExperienceValidationError, match="current_observation_claim_not_verified"
    ):
        validate_generated_activity(generated, context, repository)


@pytest.mark.parametrize(
    "text",
    [
        "请站到故事人物当年使用过的石头旁。",
        "请确认这里是某位人物曾居住的现场。",
        "请观察这里的历史现场。",
    ],
)
def test_unsupported_site_reality_assertion_is_rejected(
    repository, service, text
):
    context = _contexts(service)[0]
    generated = _valid_activity(context).model_copy(update={"instruction": text})
    with pytest.raises(
        ExperienceValidationError, match="current_observation_hallucination"
    ):
        validate_generated_activity(generated, context, repository)


def test_facilitation_only_rejects_fact_markers(repository, service):
    context = _contexts(service)[0]
    generated = _valid_activity(context).model_copy(
        update={"prompt": "据《某古籍》记载，请回答。"}
    )
    with pytest.raises(
        ExperienceValidationError, match="facilitation_only_contains_fact_marker"
    ):
        validate_generated_activity(generated, context, repository)


def test_new_number_is_rejected(repository, service):
    context = _contexts(service)[1]
    generated = _valid_activity(context).model_copy(
        update={"prompt": "请回答公元前1234年发生了什么。"}
    )
    with pytest.raises(ExperienceValidationError, match="number_not_grounded"):
        validate_generated_activity(generated, context, repository)


def test_historical_promotion_is_rejected(repository, service):
    context = _contexts(service)[1]
    generated = _valid_activity(context).model_copy(
        update={"completion_message": "这说明故事历史上确实发生。"}
    )
    with pytest.raises(ExperienceValidationError, match="claim_type_promoted"):
        validate_generated_activity(generated, context, repository)


def test_one_repair_attempt_can_restore_safety(repository, story):
    builder = ExperienceGenerationService(repository, story)
    contexts = _contexts(builder)
    valid = [_valid_activity(context) for context in contexts]
    unsafe = valid[0].model_copy(update={"instruction": "请翻越护栏。"})
    llm = FakeStructuredLlm([unsafe, valid[0], *valid[1:]])
    package = ExperienceGenerationService(repository, story, llm=llm).generate(
        ExperienceGenerationRequest(experience_id=EXPERIENCE_ID)
    )
    assert package.activities[0].raw_generation == valid[0]
    assert "unsafe_instruction" in llm.calls[1][-1].content


def test_second_invalid_output_fails_without_free_text_fallback(repository, story):
    builder = ExperienceGenerationService(repository, story)
    context = _contexts(builder)[0]
    unsafe = _valid_activity(context).model_copy(
        update={"instruction": "请翻越护栏。"}
    )
    service = ExperienceGenerationService(
        repository, story, llm=FakeStructuredLlm([unsafe, unsafe])
    )
    with pytest.raises(ExperienceGenerationError, match="validation_failed"):
        service.generate(ExperienceGenerationRequest(experience_id=EXPERIENCE_ID))


def test_provider_failure_has_no_fallback(repository, story):
    service = ExperienceGenerationService(
        repository, story, llm=FakeStructuredLlm([RuntimeError("down")])
    )
    with pytest.raises(ExperienceGenerationError, match="structured_provider_failed"):
        service.generate(ExperienceGenerationRequest(experience_id=EXPERIENCE_ID))


def test_full_draft_aggregates_five_activities(repository, story):
    builder = ExperienceGenerationService(repository, story)
    responses = [_valid_activity(context) for context in _contexts(builder)]
    package = ExperienceGenerationService(
        repository, story, llm=FakeStructuredLlm(responses)
    ).generate(
        ExperienceGenerationRequest(
            experience_id=EXPERIENCE_ID,
            audience=ExperienceAudience.FAMILY,
            tone=ExperienceTone.WARM,
        )
    )
    assert len(package.activities) == 5
    assert all(
        isinstance(item, RenderedExperienceActivity)
        for item in package.activities
    )
    assert package.audience is ExperienceAudience.FAMILY
    assert package.validation_status.value == "passed"
    assert ExperiencePackageDraft.model_validate_json(package.model_dump_json()) == package
    assert all(item.grounding_metrics.grounding_coverage == 1.0 for item in package.activities)


def test_nuwa_full_experience_passes_deterministic_grounding(repository):
    story = _generated_story_for(repository, NUWA_STORY_ID)
    builder = ExperienceGenerationService(repository, story)
    contexts = [
        builder.build_activity_context(activity.activity_id)
        for activity in repository.list_activities(NUWA_EXPERIENCE_ID)
    ]
    responses = []
    for context in contexts:
        generated = _valid_activity(context).model_copy(
            update={
                "instruction": context.activity.instruction_intent,
                "prompt": context.activity.experience_goal,
            }
        )
        responses.append(generated)
    package = ExperienceGenerationService(
        repository,
        story,
        llm=FakeStructuredLlm(responses),
    ).generate(ExperienceGenerationRequest(experience_id=NUWA_EXPERIENCE_ID))

    assert len(package.activities) == 4
    assert package.validation_status is ExperienceValidationStatus.PASSED
    assert package.catalog_version.content_version == "0.6.0"
    assert all(activity.observation_target.target_mode.value == "none" for activity in package.activities)
    assert all(activity.grounding_metrics.grounding_coverage == 1.0 for activity in package.activities)


def test_shennong_full_experience_is_grounded_and_plant_safe(repository):
    story = _generated_story_for(repository, SHENNONG_STORY_ID)
    builder = ExperienceGenerationService(repository, story)
    contexts = [
        builder.build_activity_context(activity.activity_id)
        for activity in repository.list_activities(SHENNONG_EXPERIENCE_ID)
    ]
    responses = [
        _valid_activity(context).model_copy(
            update={
                "instruction": context.activity.instruction_intent,
                "prompt": "和家人说说你愿意遵守的安全约定。",
            }
        )
        for context in contexts
    ]
    package = ExperienceGenerationService(
        repository,
        story,
        llm=FakeStructuredLlm(responses),
    ).generate(ExperienceGenerationRequest(experience_id=SHENNONG_EXPERIENCE_ID))

    assert len(package.activities) == 4
    assert package.validation_status is ExperienceValidationStatus.PASSED
    assert all(
        activity.grounding_metrics.grounding_coverage == 1.0
        for activity in package.activities
    )
    assert all(
        activity.grounding_metrics.environmental_harm_count == 0
        for activity in package.activities
    )
    assert all(
        activity.grounding_metrics.unsafe_instruction_count == 0
        for activity in package.activities
    )


def test_houyi_full_experience_is_grounded_and_weapon_safe(repository):
    story = _generated_story_for(repository, HOUYI_STORY_ID)
    builder = ExperienceGenerationService(repository, story)
    contexts = [
        builder.build_activity_context(activity.activity_id)
        for activity in repository.list_activities(HOUYI_EXPERIENCE_ID)
    ]
    responses = [
        _valid_activity(context).model_copy(
            update={
                "instruction": context.activity.instruction_intent,
                "prompt": "和家人说说文本与传说的表达边界。",
            }
        )
        for context in contexts
    ]
    package = ExperienceGenerationService(
        repository,
        story,
        llm=FakeStructuredLlm(responses),
    ).generate(ExperienceGenerationRequest(experience_id=HOUYI_EXPERIENCE_ID))

    assert len(package.activities) == 4
    assert package.validation_status is ExperienceValidationStatus.PASSED
    assert all(
        activity.grounding_metrics.grounding_coverage == 1.0
        for activity in package.activities
    )
    assert all(
        activity.grounding_metrics.unsafe_instruction_count == 0
        for activity in package.activities
    )


def test_generation_does_not_mutate_story_or_knowledge(repository, story):
    stories_before = tuple(item.model_dump_json() for item in repository.list_stories())
    claims_before = tuple(item.model_dump_json() for item in repository.list_claims())
    story_before = deepcopy(story)
    builder = ExperienceGenerationService(repository, story)
    ExperienceGenerationService(
        repository,
        story,
        llm=FakeStructuredLlm([_valid_activity(item) for item in _contexts(builder)]),
    ).generate(ExperienceGenerationRequest(experience_id=EXPERIENCE_ID))
    assert story == story_before
    assert tuple(item.model_dump_json() for item in repository.list_stories()) == stories_before
    assert tuple(item.model_dump_json() for item in repository.list_claims()) == claims_before


def test_experience_generation_has_no_regional_special_cases():
    prohibited = {"changzhi", "jingwei", "fajiushan", "b0fff49afb"}
    found = []
    for path in sorted((PROJECT_ROOT / "app" / "experience").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for token in prohibited:
                    if token in node.value.casefold():
                        found.append((path.name, token))
    assert not found
