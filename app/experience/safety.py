"""Deterministic visitor-safety and observable-reality checks."""

from __future__ import annotations

import re

from app.catalog.models import (
    EvidenceRelation,
    ExperienceActivity,
    ExperienceObservationSafetyConstraint,
    ExperienceObservationTargetMode,
    KnowledgeVerificationStatus,
)
from app.catalog.repository import CatalogRepository
from app.experience.models import (
    GeneratedExperienceActivity,
    RenderedExperienceActivity,
)


_NEGATIONS = ("不", "不得", "不要", "禁止", "无需", "无须", "避免", "不能")
_CLAUSE_SPLIT = re.compile(r"[。！？；，\n]")

_CATEGORIES = {
    "unsafe_instruction": (
        "攀爬", "翻越", "跨过护栏", "离开官方步道", "离开步道",
        "奔跑竞赛", "奔跑比赛", "危险自拍",
    ),
    "environmental_harm": (
        "采摘", "折树枝", "捡起", "拾取", "采集自然标本", "采集植物", "带走石块",
        "带走植物", "移动石块",
    ),
    "cultural_property_harm": (
        "触摸文物", "触摸古建", "攀爬文物", "攀爬古建", "刻字",
        "涂写", "移动景区设施",
    ),
    "child_unsupervised": (
        "孩子自己", "儿童自己", "孩子单独", "儿童单独", "单独行动",
        "离开成年人", "离开监护人", "分头行动", "脱离监护",
    ),
    "forced_purchase": ("购买商品", "付费购买", "买一", "消费后"),
    "restricted_area": ("进入限制区域", "进入封闭区域", "进入未开放区域"),
    "water_hazard": ("进入水域", "去水边", "靠近水边", "靠近危险水边"),
    "road_hazard": ("穿越道路", "横穿马路", "到马路中间"),
    "wildlife_interaction": (
        "接触野生动物", "触摸野生动物", "投喂野生动物", "喂野生动物",
    ),
}

_OBSERVATION_VERBS = re.compile(r"(?:观察|寻找|找到|看看|拍摄|辨认)")
_UNSUPPORTED_REALITY_ASSERTIONS = (
    re.compile(r"(?:曾|当年).{0,6}(?:住|居住|生活).{0,8}(?:这里|此地|现场)"),
    re.compile(r"(?:当年|曾经).{0,8}(?:使用过|留下).{0,8}(?:石头|物件|遗迹)"),
    re.compile(r"(?:这里|此处|现场).{0,8}(?:溺水地点|发生地点|历史现场)"),
)


def safety_issues(text: str) -> tuple[str, ...]:
    issues: list[str] = []
    for clause in _CLAUSE_SPLIT.split(text):
        for category, markers in _CATEGORIES.items():
            for marker in markers:
                index = clause.find(marker)
                if index < 0:
                    continue
                if any(negation in clause[:index] for negation in _NEGATIONS):
                    continue
                issues.append(category)
                break
    return tuple(dict.fromkeys(issues))


def observable_reality_issues(
    generated: GeneratedExperienceActivity,
    activity: ExperienceActivity,
    repository: CatalogRepository,
) -> tuple[str, ...]:
    issues: list[str] = []
    interaction_text = "\n".join(
        value
        for value in (
            generated.instruction,
            generated.prompt,
            generated.optional_hint,
        )
        if value
    )
    target = generated.observation_target
    if target != activity.observation_target:
        issues.append("observation_target_contract_mismatch")
    if target.target_mode is ExperienceObservationTargetMode.VERIFIED_ENTITY:
        allowed_refs = set(activity.anchor_ids + activity.poi_binding_ids)
        if not target.entity_refs or not set(target.entity_refs).issubset(allowed_refs):
            issues.append("verified_entity_identity_not_bound")
    elif (
        target.target_mode
        is ExperienceObservationTargetMode.VISITOR_SELECTED_VISIBLE_OBJECT
    ):
        if (
            activity.requires_guardian
            and ExperienceObservationSafetyConstraint.GUARDIAN_SUPERVISION
            not in target.safety_constraints
        ):
            issues.append("visitor_selected_guardian_constraint_missing")
    elif (
        target.target_mode
        is ExperienceObservationTargetMode.SPECIFIC_CURRENT_OBSERVABLE
    ):
        for claim_id in target.supporting_claim_ids:
            claim = repository.get_claim(claim_id)
            if (
                claim is None
                or not repository.is_claim_production_eligible(claim_id)
                or claim_id not in generated.used_claim_ids
                or not _has_verified_current_presence_evidence(
                    repository, claim_id
                )
            ):
                issues.append("current_observation_claim_not_verified")

    for clause in _CLAUSE_SPLIT.split(interaction_text):
        match = _OBSERVATION_VERBS.search(clause)
        if match is None:
            continue
        if any(negation in clause[: match.start()] for negation in _NEGATIONS):
            continue
        if target.target_mode is ExperienceObservationTargetMode.NONE:
            issues.append("observation_target_unstructured")
    if any(
        pattern.search(interaction_text)
        for pattern in _UNSUPPORTED_REALITY_ASSERTIONS
    ):
        issues.append("current_observation_hallucination")
    return tuple(dict.fromkeys(issues))


def rendered_observable_reality_issues(
    rendered: RenderedExperienceActivity,
    activity: ExperienceActivity,
    repository: CatalogRepository,
) -> tuple[str, ...]:
    issues = list(
        observable_reality_issues(
            rendered.raw_generation,
            activity,
            repository,
        )
    )
    target = rendered.observation_target
    if target.target_mode is ExperienceObservationTargetMode.NONE:
        if rendered.observation_text is not None:
            issues.append("unexpected_observation_text")
    elif rendered.observation_text != target.target_text:
        issues.append("observation_target_not_visible")
    return tuple(dict.fromkeys(issues))


def _has_verified_current_presence_evidence(
    repository: CatalogRepository,
    claim_id: str,
) -> bool:
    for evidence in repository.list_evidence_for_claim(claim_id):
        source = repository.get_source(evidence.source_id)
        if (
            evidence.verification_status is KnowledgeVerificationStatus.VERIFIED
            and evidence.evidence_relation is EvidenceRelation.SUPPORTS
            and evidence.metadata.get("current_presence_verified") is True
            and source is not None
            and source.verification_status is KnowledgeVerificationStatus.VERIFIED
        ):
            return True
    return False
