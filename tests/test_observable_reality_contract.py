from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    ExperienceObservationInteractionMode,
    ExperienceObservationSafetyConstraint,
    ExperienceObservationSelectionRule,
    ExperienceObservationTarget,
    ExperienceObservationTargetMode,
)
from app.experience import (
    ExperienceGenerationError,
    ExperienceGenerationRequest,
    ExperienceGenerationService,
    ExperienceValidationError,
    GeneratedExperienceActivity,
    RenderedExperienceActivity,
    evidence_safe_experience_messages,
    render_experience_activity,
    validate_generated_activity,
    validate_rendered_activity,
)
from tests.test_experience_generation import (
    EXPERIENCE_ID,
    FakeStructuredLlm,
    _contexts,
    _valid_activity,
)
from tests.test_story_binding import _generated_story


CATALOG_ROOT = Path(__file__).resolve().parents[1] / "content" / "catalog"


@pytest.fixture(scope="module")
def repository():
    return FileCatalogLoader(CATALOG_ROOT).load()


@pytest.fixture()
def story(repository):
    return _generated_story(repository)


@pytest.fixture()
def service(repository, story):
    return ExperienceGenerationService(repository, story)


def _none_target() -> ExperienceObservationTarget:
    return ExperienceObservationTarget(
        target_mode=ExperienceObservationTargetMode.NONE,
        interaction_mode=ExperienceObservationInteractionMode.NONE,
    )


def _visitor_target(target_text: str) -> ExperienceObservationTarget:
    return ExperienceObservationTarget(
        target_mode=(
            ExperienceObservationTargetMode.VISITOR_SELECTED_VISIBLE_OBJECT
        ),
        target_text=target_text,
        interaction_mode=ExperienceObservationInteractionMode.OBSERVE_ONLY,
        selection_rule=ExperienceObservationSelectionRule.CURRENTLY_VISIBLE,
        safety_constraints=tuple(ExperienceObservationSafetyConstraint),
    )


def _specific_target(claim_id: str, target_text: str) -> ExperienceObservationTarget:
    return ExperienceObservationTarget(
        target_mode=ExperienceObservationTargetMode.SPECIFIC_CURRENT_OBSERVABLE,
        target_text=target_text,
        supporting_claim_ids=(claim_id,),
        interaction_mode=ExperienceObservationInteractionMode.OBSERVE_ONLY,
    )


def _context_with_target(context, target):
    return context.model_copy(
        update={
            "activity": context.activity.model_copy(
                update={"observation_target": target}
            )
        }
    )


def _generated_with_target(context, target, instruction):
    changed = _context_with_target(context, target)
    generated = _valid_activity(changed).model_copy(
        update={"instruction": instruction, "observation_target": target}
    )
    return changed, generated


def test_no_external_target_is_valid(repository, service):
    context = _contexts(service)[2]
    generated = _valid_activity(context)
    validate_generated_activity(generated, context, repository)
    assert generated.observation_target.target_mode is ExperienceObservationTargetMode.NONE


def test_verified_entity_with_stable_identity_is_valid(repository, service):
    original = _contexts(service)[0]
    target = ExperienceObservationTarget(
        target_mode=ExperienceObservationTargetMode.VERIFIED_ENTITY,
        target_text="本次行程的策展锚点",
        entity_refs=(original.activity.anchor_ids[0],),
        interaction_mode=ExperienceObservationInteractionMode.OBSERVE_ONLY,
    )
    context, generated = _generated_with_target(
        original, target, "请观察本次行程的策展锚点。"
    )
    validate_generated_activity(generated, context, repository)


def test_verified_entity_with_name_only_is_rejected():
    with pytest.raises(ValidationError, match="stable identity"):
        ExperienceObservationTarget(
            target_mode=ExperienceObservationTargetMode.VERIFIED_ENTITY,
            target_text="某个同名地点",
            interaction_mode=ExperienceObservationInteractionMode.OBSERVE_ONLY,
        )


def test_visitor_selected_visible_object_observe_only_is_valid(repository, service):
    context = _contexts(service)[0]
    generated = _valid_activity(context)
    validate_generated_activity(generated, context, repository)
    assert (
        generated.observation_target.target_mode
        is ExperienceObservationTargetMode.VISITOR_SELECTED_VISIBLE_OBJECT
    )


def test_raw_target_omission_is_rendered_from_trusted_contract(repository, service):
    context = _contexts(service)[0]
    generated = _valid_activity(context).model_copy(
        update={
            "instruction": "请和同行家人一起完成这项互动。",
            "prompt": "说说你准备怎样一起参观。",
            "optional_hint": "没有标准答案。",
            "completion_message": "谢谢你完成这项体验。",
        }
    )
    assert context.activity.observation_target.target_text not in generated.visible_text

    validate_generated_activity(generated, context, repository)
    rendered = render_experience_activity(generated, context.activity)
    validate_rendered_activity(rendered, context, repository)

    assert rendered.observation_text == context.activity.observation_target.target_text
    assert rendered.raw_generation == generated


def test_raw_output_may_ignore_target_while_rendered_output_remains_complete(
    repository, service
):
    context = _contexts(service)[0]
    generated = _valid_activity(context).model_copy(
        update={
            "instruction": "请和同行家人一起完成下面的互动。",
            "prompt": "和家人说说你的想法。",
            "optional_hint": None,
            "completion_message": "本项互动已完成。",
        }
    )

    validate_generated_activity(generated, context, repository)
    rendered = render_experience_activity(generated, context.activity)
    validate_rendered_activity(rendered, context, repository)

    assert rendered.observation_text in rendered.visible_text


def test_none_target_renders_no_observation_text(repository, service):
    context = _contexts(service)[2]
    generated = _valid_activity(context)
    rendered = render_experience_activity(generated, context.activity)

    validate_rendered_activity(rendered, context, repository)
    assert rendered.observation_text is None


def test_verified_entity_renders_trusted_target_after_identity_validation(
    repository, service
):
    original = _contexts(service)[0]
    target = ExperienceObservationTarget(
        target_mode=ExperienceObservationTargetMode.VERIFIED_ENTITY,
        target_text="本次行程的策展锚点",
        entity_refs=(original.activity.anchor_ids[0],),
        interaction_mode=ExperienceObservationInteractionMode.OBSERVE_ONLY,
    )
    context, generated = _generated_with_target(
        original, target, "请和家人完成这项互动。"
    )

    rendered = render_experience_activity(generated, context.activity)
    validate_rendered_activity(rendered, context, repository)

    assert rendered.observation_text == target.target_text


def test_observation_visibility_validator_rejects_rendered_target_tampering(
    repository, service
):
    context = _contexts(service)[0]
    generated = _valid_activity(context)
    rendered = render_experience_activity(generated, context.activity).model_copy(
        update={"observation_text": "被改写的目标"}
    )

    with pytest.raises(
        ExperienceValidationError, match="observation_target_not_visible"
    ):
        validate_rendered_activity(rendered, context, repository)


@pytest.mark.parametrize(
    ("instruction", "issue"),
    [
        ("选择一个当前能看到的自然景物，捡起对象。", "environmental_harm"),
        ("选择一个当前能看到的自然景物，带走石块。", "environmental_harm"),
        ("选择一个当前能看到的自然景物，采集植物。", "environmental_harm"),
        ("选择一个当前能看到的自然景物，闻未知植物。", "wild_plant_consumption"),
        ("选择一个当前能看到的自然景物，品尝未知植物。", "wild_plant_consumption"),
        ("选择一个当前能看到的自然景物，食用野生植物。", "wild_plant_consumption"),
        ("选择一个当前能看到的自然景物，模仿尝百草。", "wild_plant_consumption"),
        ("选择一个当前能看到的自然景物，使用弓箭射击。", "weapon_activity"),
        ("选择一个当前能看到的自然景物，投掷石块。", "dangerous_projectile"),
        ("选择一个当前能看到的自然景物，站在崖边。", "cliff_risk"),
        ("让儿童单独寻找当前能看到的自然景物。", "child_unsupervised"),
    ],
)
def test_visitor_selected_visible_object_rejects_unsafe_actions(
    repository, service, instruction, issue
):
    original = _contexts(service)[0]
    target = _visitor_target("当前能看到的自然景物")
    context, generated = _generated_with_target(original, target, instruction)
    with pytest.raises(ExperienceValidationError, match=issue):
        validate_generated_activity(generated, context, repository)


@pytest.mark.parametrize(
    ("target_text", "issue"),
    [
        ("捡起一个当前可见的物品", "environmental_harm"),
        ("带走石块", "environmental_harm"),
        ("采摘一种当前可见的植物", "environmental_harm"),
        ("让儿童单独行动", "child_unsupervised"),
    ],
)
def test_renderer_rejects_unsafe_curated_visitor_target(
    repository, service, target_text, issue
):
    original = _contexts(service)[0]
    target = _visitor_target(target_text)
    context, generated = _generated_with_target(
        original, target, "请和同行家人一起完成这项互动。"
    )
    validate_generated_activity(generated, context, repository)
    rendered = render_experience_activity(generated, context.activity)

    with pytest.raises(ExperienceValidationError, match=issue):
        validate_rendered_activity(rendered, context, repository)


def test_specific_current_observable_with_verified_presence_evidence_is_valid(
    repository, service
):
    original = _contexts(service)[1]
    claim_id = original.activity.required_claim_ids[0]
    target = _specific_target(claim_id, "经当前证据确认的可观察对象")
    context, generated = _generated_with_target(
        original, target, "请观察经当前证据确认的可观察对象。"
    )
    evidence = repository.list_evidence_for_claim(claim_id)[0]
    wrapped = Mock(wraps=repository)
    wrapped.list_evidence_for_claim.return_value = (
        evidence.model_copy(update={"metadata": {"current_presence_verified": True}}),
    )
    validate_generated_activity(generated, context, wrapped)


def test_specific_current_observable_with_only_ancient_claim_is_rejected(
    repository, service
):
    original = _contexts(service)[1]
    claim_id = original.activity.required_claim_ids[0]
    target = _specific_target(claim_id, "古籍叙事对象")
    context, generated = _generated_with_target(
        original, target, "请观察古籍叙事对象。"
    )
    with pytest.raises(
        ExperienceValidationError, match="current_observation_claim_not_verified"
    ):
        validate_generated_activity(generated, context, repository)


def test_seeking_specific_plant_from_ancient_claim_is_rejected(repository, service):
    original = _contexts(service)[1]
    claim_id = original.activity.required_claim_ids[1]
    target = _specific_target(claim_id, "现场柘木")
    context, generated = _generated_with_target(
        original, target, "请寻找现场柘木。"
    )
    with pytest.raises(
        ExperienceValidationError, match="current_observation_claim_not_verified"
    ):
        validate_generated_activity(generated, context, repository)


def test_seeking_story_character_stone_is_rejected(repository, service):
    context = _contexts(service)[2]
    generated = _valid_activity(context).model_copy(
        update={"instruction": "请寻找精卫当年使用过的石头。"}
    )
    with pytest.raises(
        ExperienceValidationError, match="current_observation_hallucination"
    ):
        validate_generated_activity(generated, context, repository)


def test_visitor_may_choose_already_visible_untouched_natural_object(
    repository, service
):
    original = _contexts(service)[0]
    text = "当前已经能看到且无需触碰的自然景物"
    target = _visitor_target(text)
    context, generated = _generated_with_target(
        original,
        target,
        "选择一个你当前已经能看到且无需触碰的自然景物进行观察。",
    )
    validate_generated_activity(generated, context, repository)


def test_hard_observation_safety_is_visible_in_rendered_output(repository, service):
    context = _contexts(service)[0]
    rendered = render_experience_activity(_valid_activity(context), context.activity)

    validate_rendered_activity(rendered, context, repository)
    assert "仅观察，不触碰。" in rendered.safety_notice
    assert "不得移动观察对象。" in rendered.safety_notice


def test_guardian_requirement_is_rendered_without_curated_guardian_prose(
    repository, service
):
    original = _contexts(service)[1]
    activity = original.activity.model_copy(
        update={"safety_constraints": ["问题只依据已提供的古籍内容。"]}
    )
    context = original.model_copy(update={"activity": activity})
    rendered = render_experience_activity(_valid_activity(context), activity)

    validate_rendered_activity(rendered, context, repository)
    assert "同行成年人" in rendered.safety_notice


def test_reflection_without_external_object_uses_none(service):
    context = _contexts(service)[4]
    assert context.activity.observation_target == _none_target()


def test_question_without_external_object_accepts_none(repository, service):
    context = _contexts(service)[1]
    generated = _valid_activity(context)
    validate_generated_activity(generated, context, repository)
    assert generated.observation_target == _none_target()


def test_prompt_requires_explicit_four_mode_observation_structure(service):
    messages = evidence_safe_experience_messages(
        ExperienceGenerationRequest(experience_id=EXPERIENCE_ID),
        _contexts(service)[0],
    )
    text = "\n".join(message.content for message in messages)
    assert "target_mode=none" in text
    assert "verified_entity" in text
    assert "visitor_selected_visible_object" in text
    assert "specific_current_observable" in text


def test_observation_contract_round_trip(service):
    generated = _valid_activity(_contexts(service)[0])
    assert (
        GeneratedExperienceActivity.model_validate_json(generated.model_dump_json())
        == generated
    )


def test_rendered_activity_round_trip_preserves_raw_and_trusted_layers(service):
    context = _contexts(service)[0]
    rendered = render_experience_activity(_valid_activity(context), context.activity)

    restored = RenderedExperienceActivity.model_validate_json(
        rendered.model_dump_json()
    )

    assert restored == rendered
    assert restored.raw_generation == rendered.raw_generation
    assert restored.observation_text == context.activity.observation_target.target_text


def test_renderer_does_not_mutate_inputs(service):
    context = _contexts(service)[0]
    generated = _valid_activity(context)
    generated_before = deepcopy(generated)
    activity_before = deepcopy(context.activity)

    render_experience_activity(generated, context.activity)

    assert generated == generated_before
    assert context.activity == activity_before


def test_repair_output_runs_through_same_observation_validator(repository, story):
    builder = ExperienceGenerationService(repository, story)
    context = _contexts(builder)[2]
    invalid = _valid_activity(context).model_copy(
        update={"instruction": "请寻找现场的一种具体对象。"}
    )
    service = ExperienceGenerationService(
        repository, story, llm=FakeStructuredLlm([invalid, invalid])
    )
    with pytest.raises(
        ExperienceGenerationError, match="observation_target_unstructured"
    ):
        service.generate(ExperienceGenerationRequest(experience_id=EXPERIENCE_ID))


def test_negated_seeking_does_not_create_an_observation_target(repository, service):
    context = _contexts(service)[2]
    generated = _valid_activity(context).model_copy(
        update={"instruction": "儿童不单独行动，也不分头寻找线索。"}
    )
    validate_generated_activity(generated, context, repository)
