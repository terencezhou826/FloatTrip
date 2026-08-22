from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    StoryAudience,
    StoryBlueprint,
    StoryChapter,
    StoryChapterType,
    StoryType,
    StoryVerificationStatus,
)
from app.catalog.validation import CatalogValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
PACKAGE_ROOT = Path("packages") / "shanxi" / "changzhi"
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
    return root / PACKAGE_ROOT / "stories" / "blueprints" / "jingwei.json"


def _chapters_path(root: Path) -> Path:
    return root / PACKAGE_ROOT / "stories" / "chapters" / "jingwei.json"


def _claims_path(root: Path) -> Path:
    return root / PACKAGE_ROOT / "knowledge" / "claims.json"


@pytest.fixture(scope="module")
def catalog():
    return FileCatalogLoader(CATALOG_ROOT).load()


def test_story_type_is_controlled_and_theme_neutral():
    assert {item.value for item in StoryType} == {
        "mythology",
        "historical",
        "heritage",
        "biographical",
        "educational",
        "nature",
        "folk_culture",
        "food_culture",
        "red_culture",
        "custom",
    }


def test_chapter_type_supports_non_fixed_narrative_shapes():
    assert {item.value for item in StoryChapterType} == {
        "prologue",
        "context",
        "origin",
        "development",
        "turning_point",
        "climax",
        "reflection",
        "epilogue",
    }


def test_story_verification_and_audience_enums():
    assert {item.value for item in StoryVerificationStatus} == {
        "draft",
        "review_required",
        "verified",
        "rejected",
    }
    assert {item.value for item in StoryAudience} >= {
        "family",
        "student",
        "culture",
    }


def test_jingwei_story_and_five_chapters_load(catalog):
    stories = catalog.list_stories()
    chapters = catalog.list_story_chapters(STORY_ID)

    assert len(stories) == 1
    assert stories[0].story_id == STORY_ID
    assert stories[0].story_type is StoryType.MYTHOLOGY
    assert len(chapters) == 5
    assert [chapter.sequence for chapter in chapters] == list(range(5))


def test_story_and_chapter_json_round_trip(catalog):
    story = catalog.get_story(STORY_ID)
    chapter = catalog.list_story_chapters(STORY_ID)[0]

    assert StoryBlueprint.model_validate_json(story.model_dump_json()) == story
    assert StoryChapter.model_validate_json(chapter.model_dump_json()) == chapter
    with pytest.raises(ValidationError, match="frozen"):
        story.title = "Changed"


def test_repository_route_filter_and_ordering(catalog):
    assert catalog.list_stories("changzhi.route.jingwei-fajiushan") == (
        catalog.get_story(STORY_ID),
    )
    assert catalog.list_stories("changzhi.route.nuwa-tiantaishan") == ()
    chapters = catalog.list_story_chapters(STORY_ID)
    assert catalog.get_story_chapter(chapters[2].chapter_id) == chapters[2]


def test_multiple_chapters_may_share_one_anchor_and_binding(catalog):
    spatial = catalog.list_story_chapters(STORY_ID)[:4]

    assert {tuple(chapter.anchor_ids) for chapter in spatial} == {
        ("changzhi.anchor.fajiushan",)
    }
    assert {tuple(chapter.poi_binding_ids) for chapter in spatial} == {
        ("changzhi.binding.fajiushan.amap",)
    }


def test_context_chapter_without_anchor_or_poi_is_valid(catalog):
    chapter = catalog.list_story_chapters(STORY_ID)[4]

    assert chapter.anchor_ids == []
    assert chapter.poi_binding_ids == []


def test_all_bound_claims_are_production_eligible(catalog):
    for chapter in catalog.list_story_chapters(STORY_ID):
        for claim_id in chapter.required_claim_ids + chapter.optional_claim_ids:
            assert catalog.is_claim_production_eligible(claim_id)


def test_qualified_claim_is_valid_story_content(catalog):
    chapter = catalog.list_story_chapters(STORY_ID)[3]
    claim = catalog.get_claim(chapter.required_claim_ids[0])

    assert catalog.is_claim_production_eligible(claim.claim_id)
    assert claim.promotion_policy.required_qualifier


def test_old_package_without_stories_loads_empty(tmp_path):
    root = _catalog_copy(tmp_path)
    shutil.rmtree(root / PACKAGE_ROOT / "stories")
    shutil.rmtree(root / PACKAGE_ROOT / "experiences")

    catalog = FileCatalogLoader(root).load()

    assert catalog.list_stories() == ()
    assert catalog.list_story_chapters(STORY_ID) == ()


def test_duplicate_story_id_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _blueprints_path(root)
    payload = _read(path)
    payload["blueprints"].append(dict(payload["blueprints"][0]))
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="duplicate id"):
        FileCatalogLoader(root).load()


def test_duplicate_chapter_id_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _chapters_path(root)
    payload = _read(path)
    payload["chapters"].append(dict(payload["chapters"][0]))
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="duplicate id"):
        FileCatalogLoader(root).load()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("route_id", "missing.route", "missing route"),
        ("theme_id", "missing.theme", "missing theme"),
        ("region_id", "missing.region", "missing region"),
    ],
)
def test_story_catalog_references_must_exist(tmp_path, field, value, message):
    root = _catalog_copy(tmp_path)
    path = _blueprints_path(root)
    payload = _read(path)
    payload["blueprints"][0][field] = value
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match=message):
        FileCatalogLoader(root).load()


def test_story_package_id_must_match_owner(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _blueprints_path(root)
    payload = _read(path)
    payload["blueprints"][0]["package_id"] = "other.package"
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="does not match owning package"):
        FileCatalogLoader(root).load()


def test_missing_chapter_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _chapters_path(root)
    payload = _read(path)
    payload["chapters"].pop()
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="missing chapter"):
        FileCatalogLoader(root).load()


def test_orphan_chapter_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _blueprints_path(root)
    payload = _read(path)
    payload["blueprints"][0]["chapter_ids"].pop()
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="orphan story chapter"):
        FileCatalogLoader(root).load()


def test_duplicate_chapter_sequence_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _chapters_path(root)
    payload = _read(path)
    payload["chapters"][1]["sequence"] = 0
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="duplicate chapter sequence"):
        FileCatalogLoader(root).load()


def test_chapter_sequence_must_be_contiguous(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _chapters_path(root)
    payload = _read(path)
    payload["chapters"][4]["sequence"] = 8
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="contiguous from 0"):
        FileCatalogLoader(root).load()


def test_missing_anchor_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _chapters_path(root)
    payload = _read(path)
    payload["chapters"][0]["anchor_ids"] = ["missing.anchor"]
    payload["chapters"][0]["poi_binding_ids"] = []
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="missing anchor"):
        FileCatalogLoader(root).load()


def test_missing_poi_binding_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _chapters_path(root)
    payload = _read(path)
    payload["chapters"][0]["poi_binding_ids"] = ["missing.binding"]
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="missing POI binding"):
        FileCatalogLoader(root).load()


def test_unverified_poi_binding_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    binding_path = root / PACKAGE_ROOT / "poi_bindings.json"
    payload = _read(binding_path)
    payload["poi_bindings"][0]["verification_status"] = "candidate"
    payload["poi_bindings"][0]["verification_method"] = None
    payload["poi_bindings"][0]["verified_at"] = None
    _write(binding_path, payload)

    with pytest.raises(CatalogValidationError, match="is not verified"):
        FileCatalogLoader(root).load()


def test_binding_must_belong_to_chapter_anchor(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _chapters_path(root)
    payload = _read(path)
    payload["chapters"][0]["anchor_ids"] = ["changzhi.anchor.tiantaishan"]
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="does not belong"):
        FileCatalogLoader(root).load()


def test_missing_claim_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    blueprint_path = _blueprints_path(root)
    chapter_path = _chapters_path(root)
    blueprint = _read(blueprint_path)
    chapter = _read(chapter_path)
    blueprint["blueprints"][0]["knowledge_claim_ids"].append("missing.claim")
    chapter["chapters"][0]["optional_claim_ids"].append("missing.claim")
    _write(blueprint_path, blueprint)
    _write(chapter_path, chapter)

    with pytest.raises(CatalogValidationError, match="missing Claim"):
        FileCatalogLoader(root).load()


def test_review_required_and_internal_only_claim_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    blueprint_path = _blueprints_path(root)
    chapter_path = _chapters_path(root)
    blueprint = _read(blueprint_path)
    chapter = _read(chapter_path)
    blueprint["blueprints"][0]["knowledge_claim_ids"].append(INTERNAL_CLAIM_ID)
    chapter["chapters"][0]["optional_claim_ids"].append(INTERNAL_CLAIM_ID)
    _write(blueprint_path, blueprint)
    _write(chapter_path, chapter)

    with pytest.raises(CatalogValidationError, match="not production eligible"):
        FileCatalogLoader(root).load()


def test_forbidden_claim_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _claims_path(root)
    payload = _read(path)
    claim = next(
        item
        for item in payload["claims"]
        if item["claim_id"] == "changzhi.claim.jingwei-fills-sea"
    )
    claim["promotion_policy"]["status"] = "forbidden"
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="not production eligible"):
        FileCatalogLoader(root).load()


def test_enabled_story_must_be_verified(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _blueprints_path(root)
    payload = _read(path)
    payload["blueprints"][0]["verification_status"] = "review_required"
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="must be verified"):
        FileCatalogLoader(root).load()


def test_enabled_story_chapter_must_be_verified(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _chapters_path(root)
    payload = _read(path)
    payload["chapters"][0]["content_status"] = "review_required"
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="in enabled story"):
        FileCatalogLoader(root).load()


def test_required_and_optional_claims_must_not_overlap(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _chapters_path(root)
    payload = _read(path)
    payload["chapters"][0]["optional_claim_ids"].append(
        payload["chapters"][0]["required_claim_ids"][0]
    )
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="required Claim as optional"):
        FileCatalogLoader(root).load()


def test_chapter_claim_must_be_declared_by_blueprint(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _blueprints_path(root)
    payload = _read(path)
    payload["blueprints"][0]["knowledge_claim_ids"].remove(
        "changzhi.claim.jingwei-fills-sea"
    )
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="outside blueprint"):
        FileCatalogLoader(root).load()


def test_curatorial_intent_rejects_unsupported_precision(tmp_path):
    root = _catalog_copy(tmp_path)
    path = _chapters_path(root)
    payload = _read(path)
    payload["chapters"][0]["opening_hook"] = "请记住这里的经纬度。"
    _write(path, payload)

    with pytest.raises(CatalogValidationError, match="curatorial intent"):
        FileCatalogLoader(root).load()


def test_story_loading_does_not_mutate_knowledge(catalog):
    before = tuple(claim.model_dump_json() for claim in catalog.list_claims())

    catalog.get_story(STORY_ID)
    catalog.list_story_chapters(STORY_ID)

    after = tuple(claim.model_dump_json() for claim in catalog.list_claims())
    assert after == before
    assert INTERNAL_CLAIM_ID not in catalog.get_story(STORY_ID).knowledge_claim_ids
