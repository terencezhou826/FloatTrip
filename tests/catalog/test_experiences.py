from __future__ import annotations

from copy import deepcopy
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    PRODUCTION_EXPERIENCE_PROHIBITED_ACTIONS,
    ExperienceActivity,
    ExperienceActivityType,
    ExperienceAudience,
    ExperienceBlueprint,
    ExperienceContentMode,
    ExperienceProhibitedAction,
    ExperienceRiskLevel,
    ExperienceType,
    ExperienceVerificationStatus,
    VisitorOutputType,
)
from app.catalog.validation import CatalogValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
PACKAGE_ROOT = Path("packages") / "shanxi" / "changzhi"
EXPERIENCE_ID = "changzhi.experience.jingwei-family"
STORY_ID = "changzhi.story.jingwei-fajiushan"
INTERNAL_CLAIM_ID = "changzhi.claim.fajiushan-yandi-residence"


def _catalog_copy(tmp_path: Path) -> Path:
    target = tmp_path / "catalog"
    shutil.copytree(CATALOG_ROOT, target)
    return target


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _blueprints_path(root: Path) -> Path:
    return root / PACKAGE_ROOT / "experiences" / "blueprints" / "jingwei-family.json"


def _activities_path(root: Path) -> Path:
    return root / PACKAGE_ROOT / "experiences" / "activities" / "jingwei-family.json"


def _stories_path(root: Path) -> Path:
    return root / PACKAGE_ROOT / "stories" / "blueprints" / "jingwei.json"


def _claims_path(root: Path) -> Path:
    return root / PACKAGE_ROOT / "knowledge" / "claims.json"


@pytest.fixture(scope="module")
def catalog():
    return FileCatalogLoader(CATALOG_ROOT).load()


def test_experience_type_is_controlled_and_theme_neutral():
    assert {item.value for item in ExperienceType} == {
        "educational", "family", "cultural", "nature", "heritage",
        "folk_culture", "food_culture", "custom",
    }


def test_activity_type_supports_general_safe_interactions():
    assert {item.value for item in ExperienceActivityType} == {
        "observation", "question", "reflection", "creative",
        "family_collaboration", "photo_prompt", "comparison",
        "seek_and_find", "sensory", "micro_challenge", "context",
    }


def test_content_risk_output_and_verification_enums():
    assert {item.value for item in ExperienceContentMode} == {
        "facilitation_only", "knowledge_grounded"
    }
    assert {item.value for item in ExperienceRiskLevel} == {
        "low", "moderate", "prohibited"
    }
    assert {item.value for item in VisitorOutputType} >= {
        "none", "spoken_response", "text_response", "photo", "drawing"
    }
    assert {item.value for item in ExperienceVerificationStatus} == {
        "draft", "review_required", "verified", "rejected"
    }


def test_global_safety_policy_covers_all_controlled_prohibitions():
    assert PRODUCTION_EXPERIENCE_PROHIBITED_ACTIONS == frozenset(
        ExperienceProhibitedAction
    )
    assert len(PRODUCTION_EXPERIENCE_PROHIBITED_ACTIONS) == 20


def test_jingwei_experience_and_five_activities_load(catalog):
    experiences = catalog.list_experiences()
    activities = catalog.list_activities(EXPERIENCE_ID)

    assert len(experiences) == 1
    assert experiences[0].experience_id == EXPERIENCE_ID
    assert experiences[0].experience_type is ExperienceType.FAMILY
    assert len(activities) == 5
    assert [item.sequence for item in activities] == list(range(5))


def test_experience_and_activity_round_trip_and_freezing(catalog):
    experience = catalog.get_experience(EXPERIENCE_ID)
    activity = catalog.list_activities(EXPERIENCE_ID)[0]

    assert ExperienceBlueprint.model_validate_json(
        experience.model_dump_json()
    ) == experience
    assert ExperienceActivity.model_validate_json(activity.model_dump_json()) == activity
    with pytest.raises(ValidationError, match="frozen"):
        experience.title = "Changed"


def test_repository_filters_by_route_story_theme_and_region(catalog):
    experience = catalog.get_experience(EXPERIENCE_ID)

    assert catalog.list_experiences(route_id=experience.route_id) == (experience,)
    assert catalog.list_experiences(story_id=experience.story_id) == (experience,)
    assert catalog.list_experiences(theme_id=experience.theme_id) == (experience,)
    assert catalog.list_experiences(region_id=experience.region_id) == (experience,)
    assert catalog.list_experiences(route_id="other.route") == ()


def test_repository_activity_get_and_ordering(catalog):
    activities = catalog.list_activities(EXPERIENCE_ID)
    assert catalog.get_activity(activities[2].activity_id) == activities[2]
    assert catalog.list_activities("other.experience") == ()


def test_family_child_student_activities_require_guardian(catalog):
    experience = catalog.get_experience(EXPERIENCE_ID)
    assert {ExperienceAudience.FAMILY, ExperienceAudience.CHILD}.issubset(
        experience.target_audiences
    )
    assert all(item.requires_guardian for item in catalog.list_activities(EXPERIENCE_ID))


def test_facilitation_and_knowledge_modes_are_both_used(catalog):
    activities = catalog.list_activities(EXPERIENCE_ID)
    assert {item.content_mode for item in activities} == {
        ExperienceContentMode.FACILITATION_ONLY,
        ExperienceContentMode.KNOWLEDGE_GROUNDED,
    }
    assert all(
        not item.required_claim_ids
        for item in activities
        if item.content_mode is ExperienceContentMode.FACILITATION_ONLY
    )


def test_multiple_activities_may_share_one_anchor_and_binding(catalog):
    spatial = catalog.list_activities(EXPERIENCE_ID)[:4]
    assert {tuple(item.anchor_ids) for item in spatial} == {
        ("changzhi.anchor.fajiushan",)
    }
    assert {tuple(item.poi_binding_ids) for item in spatial} == {
        ("changzhi.binding.fajiushan.amap",)
    }


def test_context_activity_without_anchor_or_poi_is_valid(catalog):
    activity = catalog.list_activities(EXPERIENCE_ID)[4]
    assert activity.anchor_ids == []
    assert activity.poi_binding_ids == []


def test_all_bound_claims_are_production_eligible(catalog):
    for activity in catalog.list_activities(EXPERIENCE_ID):
        for claim_id in activity.required_claim_ids + activity.optional_claim_ids:
            assert catalog.is_claim_production_eligible(claim_id)


def test_qualified_claim_is_valid_experience_content(catalog):
    activity = catalog.list_activities(EXPERIENCE_ID)[1]
    claim = catalog.get_claim("changzhi.claim.fajiushan-zhemu")
    assert claim.claim_id in activity.required_claim_ids
    assert claim.promotion_policy.required_qualifier


def test_first_version_has_no_purchase_staff_or_required_materials(catalog):
    activities = catalog.list_activities(EXPERIENCE_ID)
    assert all(not item.requires_purchase for item in activities)
    assert all(not item.requires_staff for item in activities)
    assert all(item.materials_required == [] for item in activities)


def test_old_package_without_experiences_loads_empty(tmp_path):
    root = _catalog_copy(tmp_path)
    shutil.rmtree(root / PACKAGE_ROOT / "experiences")

    loaded = FileCatalogLoader(root).load()

    assert loaded.list_experiences() == ()
    assert loaded.list_activities(EXPERIENCE_ID) == ()


def test_duplicate_experience_id_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _blueprints_path(root)
    payload = _read(path)
    payload["blueprints"].append(deepcopy(payload["blueprints"][0]))
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="duplicate id"):
        FileCatalogLoader(root).load()


def test_duplicate_activity_id_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"].append(deepcopy(payload["activities"][0]))
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="duplicate id"):
        FileCatalogLoader(root).load()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("route_id", "missing.route", "missing route"),
        ("theme_id", "missing.theme", "missing theme"),
        ("region_id", "missing.region", "missing region"),
        ("story_id", "missing.story", "missing story"),
    ],
)
def test_experience_catalog_references_must_exist(
    tmp_path, field, value, message
):
    root = _catalog_copy(tmp_path)
    path = _blueprints_path(root)
    payload = _read(path)
    payload["blueprints"][0][field] = value
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match=message):
        FileCatalogLoader(root).load()


def test_experience_package_id_must_match_owner(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _blueprints_path(root)
    payload = _read(path)
    payload["blueprints"][0]["package_id"] = "other.package"
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="does not match owning package"):
        FileCatalogLoader(root).load()


def test_experience_scope_must_match_story(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _blueprints_path(root)
    payload = _read(path)
    payload["blueprints"][0]["route_id"] = "changzhi.route.nuwa-tiantaishan"
    payload["blueprints"][0]["theme_id"] = "changzhi.nuwa"
    payload["blueprints"][0]["region_id"] = "cn.shanxi.changzhi.shangdang"
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="does not match Story scope"):
        FileCatalogLoader(root).load()


def test_missing_activity_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"].pop()
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="missing activity"):
        FileCatalogLoader(root).load()


def test_orphan_activity_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _blueprints_path(root)
    payload = _read(path)
    payload["blueprints"][0]["activity_ids"].pop()
    payload["blueprints"][0]["estimated_total_duration_sec"] -= 120
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="orphan experience activity"):
        FileCatalogLoader(root).load()


def test_duplicate_activity_sequence_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][1]["sequence"] = 0
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="duplicate activity sequence"):
        FileCatalogLoader(root).load()


def test_missing_story_chapter_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][0]["story_chapter_ids"] = ["missing.chapter"]
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="missing story chapter"):
        FileCatalogLoader(root).load()


def test_missing_anchor_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][0]["anchor_ids"] = ["missing.anchor"]
    payload["activities"][0]["poi_binding_ids"] = []
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="missing anchor"):
        FileCatalogLoader(root).load()


def test_missing_poi_binding_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][0]["poi_binding_ids"] = ["missing.binding"]
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="missing POI binding"):
        FileCatalogLoader(root).load()


def test_binding_must_be_verified_and_belong_to_activity_anchor(tmp_path):
    root = _catalog_copy(tmp_path)
    binding_path = root / PACKAGE_ROOT / "poi_bindings.json"
    payload = _read(binding_path)
    payload["poi_bindings"][0]["verification_status"] = "candidate"
    payload["poi_bindings"][0]["verification_method"] = None
    payload["poi_bindings"][0]["verified_at"] = None
    _write(binding_path, payload)
    with pytest.raises(CatalogValidationError, match="is not verified"):
        FileCatalogLoader(root).load()


def test_binding_anchor_mismatch_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][0]["anchor_ids"] = ["changzhi.anchor.tiantaishan"]
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="does not belong"):
        FileCatalogLoader(root).load()


def test_missing_claim_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][1]["required_claim_ids"].append("missing.claim")
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="missing Claim"):
        FileCatalogLoader(root).load()


def test_internal_only_claim_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][1]["required_claim_ids"].append(INTERNAL_CLAIM_ID)
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="not production eligible"):
        FileCatalogLoader(root).load()


@pytest.mark.parametrize("status", ["review_required", "rejected"])
def test_non_verified_claim_is_rejected(tmp_path, status):
    root = _catalog_copy(tmp_path)
    path = _claims_path(root)
    payload = _read(path)
    claim = next(
        item for item in payload["claims"]
        if item["claim_id"] == "changzhi.claim.fajiushan-zhemu"
    )
    claim["verification_status"] = status
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="not production eligible"):
        FileCatalogLoader(root).load()


def test_forbidden_claim_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _claims_path(root)
    payload = _read(path)
    claim = next(
        item for item in payload["claims"]
        if item["claim_id"] == "changzhi.claim.fajiushan-zhemu"
    )
    claim["promotion_policy"]["status"] = "forbidden"
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="not production eligible"):
        FileCatalogLoader(root).load()


def test_knowledge_grounded_activity_requires_claim(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][1]["required_claim_ids"] = []
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="requires a Claim"):
        FileCatalogLoader(root).load()


def test_facilitation_only_activity_with_no_claim_is_valid(catalog):
    activity = catalog.list_activities(EXPERIENCE_ID)[0]
    assert activity.content_mode is ExperienceContentMode.FACILITATION_ONLY
    assert activity.required_claim_ids == []
    assert activity.optional_claim_ids == []


def test_enabled_experience_and_activities_must_be_verified(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _blueprints_path(root)
    payload = _read(path)
    payload["blueprints"][0]["verification_status"] = "review_required"
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="must be verified"):
        FileCatalogLoader(root).load()


def test_enabled_activity_must_be_verified(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][0]["content_status"] = "review_required"
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="in enabled experience"):
        FileCatalogLoader(root).load()


@pytest.mark.parametrize("risk", ["moderate", "prohibited"])
def test_non_low_risk_cannot_be_production(tmp_path, risk):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][0]["risk_level"] = risk
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="must have low risk"):
        FileCatalogLoader(root).load()


def test_purchase_requirement_cannot_be_production(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][0]["requires_purchase"] = True
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="cannot require purchase"):
        FileCatalogLoader(root).load()


def test_child_activity_requires_guardian(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][0]["requires_guardian"] = False
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="requires guardian"):
        FileCatalogLoader(root).load()


@pytest.mark.parametrize(
    "instruction",
    [
        "请攀爬非正式设施。",
        "请翻越护栏完成任务。",
        "进入水域寻找线索。",
        "离开官方步道拍照。",
        "请采摘一朵花。",
        "请带走石块作为纪念。",
        "请触摸文物。",
        "让孩子自己去寻找。",
        "请分头行动。",
        "购买商品才能完成任务。",
    ],
)
def test_unsafe_instruction_intent_is_rejected(tmp_path, instruction):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][0]["instruction_intent"] = instruction
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="unsafe instruction"):
        FileCatalogLoader(root).load()


@pytest.mark.parametrize(
    "instruction",
    [
        "现在寻找一棵柘木。",
        "找到精卫当年使用过的石头。",
        "看看女娃溺水的地点。",
        "观察炎帝居住的位置。",
    ],
)
def test_narrative_cannot_become_current_observable_reality(tmp_path, instruction):
    root = _catalog_copy(tmp_path)
    path = _activities_path(root)
    payload = _read(path)
    payload["activities"][0]["instruction_intent"] = instruction
    _write(path, payload)
    with pytest.raises(CatalogValidationError, match="observable reality"):
        FileCatalogLoader(root).load()


def test_loading_experience_does_not_mutate_story_or_knowledge(catalog):
    stories_before = tuple(item.model_dump_json() for item in catalog.list_stories())
    claims_before = tuple(item.model_dump_json() for item in catalog.list_claims())

    catalog.get_experience(EXPERIENCE_ID)
    catalog.list_activities(EXPERIENCE_ID)

    assert tuple(item.model_dump_json() for item in catalog.list_stories()) == stories_before
    assert tuple(item.model_dump_json() for item in catalog.list_claims()) == claims_before
    assert INTERNAL_CLAIM_ID not in {
        claim_id
        for item in catalog.list_activities(EXPERIENCE_ID)
        for claim_id in item.required_claim_ids + item.optional_claim_ids
    }
