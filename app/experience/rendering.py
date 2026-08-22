"""Deterministic assembly of trusted and LLM-generated Experience content."""

from __future__ import annotations

from app.catalog.models import (
    ExperienceActivity,
    ExperienceObservationSafetyConstraint,
    ExperienceObservationTargetMode,
)
from app.experience.models import (
    GeneratedExperienceActivity,
    RenderedExperienceActivity,
)


_SAFETY_TEXT = {
    ExperienceObservationSafetyConstraint.NO_TOUCH: "仅观察，不触碰。",
    ExperienceObservationSafetyConstraint.NO_MOVE: "不得移动观察对象。",
    ExperienceObservationSafetyConstraint.NO_COLLECT: "不得采集观察对象。",
    ExperienceObservationSafetyConstraint.NO_REMOVE: "不得带走观察对象。",
    ExperienceObservationSafetyConstraint.NO_CROSS_BARRIER: "不得跨越护栏或障碍。",
    ExperienceObservationSafetyConstraint.NORMAL_VISITOR_AREA_ONLY: (
        "仅在正常游客可达区域内完成。"
    ),
    ExperienceObservationSafetyConstraint.GUARDIAN_SUPERVISION: (
        "儿童须在同行成年人陪同下完成并保持在其视线内。"
    ),
    ExperienceObservationSafetyConstraint.SKIPPABLE: (
        "没有合适的可见对象时可以跳过，不影响体验完成。"
    ),
}

_GUARDIAN_SAFETY_TEXT = "儿童须在同行成年人陪同下完成并保持在其视线内。"


def render_experience_activity(
    generated: GeneratedExperienceActivity,
    activity: ExperienceActivity,
) -> RenderedExperienceActivity:
    target = activity.observation_target
    observation_text = (
        None
        if target.target_mode is ExperienceObservationTargetMode.NONE
        else target.target_text
    )
    trusted_safety = [*activity.safety_constraints]
    trusted_safety.extend(
        _SAFETY_TEXT[item] for item in target.safety_constraints
    )
    if activity.requires_guardian and not any(
        marker in text
        for text in trusted_safety
        for marker in ("同行成年人", "监护")
    ):
        trusted_safety.append(_GUARDIAN_SAFETY_TEXT)
    safety_notice = " ".join(
        dict.fromkeys((*trusted_safety, generated.safety_notice))
    )
    return RenderedExperienceActivity(
        raw_generation=generated,
        activity_id=generated.activity_id,
        title=generated.title,
        observation_text=observation_text,
        instruction=generated.instruction,
        factual_content=generated.factual_content,
        prompt=generated.prompt,
        optional_hint=generated.optional_hint,
        completion_message=generated.completion_message,
        observation_target=target,
        used_claim_ids=generated.used_claim_ids,
        citations=generated.citations,
        qualifiers_used=generated.qualifiers_used,
        safety_notice=safety_notice,
        estimated_duration_sec=generated.estimated_duration_sec,
        visitor_output_type=generated.visitor_output_type,
        generation_status=generated.generation_status,
        warnings=generated.warnings,
    )
