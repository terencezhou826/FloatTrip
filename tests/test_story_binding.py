from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    NavigationAccessPoint,
    PromotionPolicyStatus,
    StoryAudience,
)
from app.knowledge.models import KnowledgeCitation
from app.story import (
    GeneratedStory,
    GeneratedStoryChapter,
    GroundedStoryFact,
    PlacementType,
    StoryBindingError,
    StoryBindingRequest,
    StoryGenerationService,
    StoryGenerationStatus,
    StoryItineraryBinder,
    StoryPackage,
    StoryPackageValidationStatus,
    StoryTriggerHint,
    StoryValidationStatus,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
STORY_ID = "changzhi.story.jingwei-fajiushan"
ROUTE_ID = "changzhi.route.jingwei-fajiushan"
ANCHOR_ID = "changzhi.anchor.fajiushan"
BINDING_ID = "changzhi.binding.fajiushan.amap"


@pytest.fixture(scope="module")
def repository():
    return FileCatalogLoader(CATALOG_ROOT).load()


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


def _generated_story(repository) -> GeneratedStory:
    service = StoryGenerationService(repository)
    blueprint = repository.get_story(STORY_ID)
    chapters = []
    for chapter in repository.list_story_chapters(STORY_ID):
        context = service.build_chapter_context(chapter.chapter_id)
        required = set(chapter.required_claim_ids)
        hits = [hit for hit in context.claim_hits if hit.claim_id in required]
        chapters.append(
            GeneratedStoryChapter(
                chapter_id=chapter.chapter_id,
                title=chapter.title,
                opening_text=chapter.opening_hook,
                factual_content=tuple(
                    GroundedStoryFact(
                        text=hit.approved_wording or hit.statement,
                        claim_id=hit.claim_id,
                    )
                    for hit in hits
                ),
                transition_text=chapter.transition_goal,
                closing_text=chapter.visitor_takeaway,
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
                visitor_takeaway=chapter.visitor_takeaway,
                generation_status=StoryGenerationStatus.GENERATED,
                warnings=(),
            )
        )
    used_claim_ids = tuple(
        dict.fromkeys(
            claim_id for chapter in chapters for claim_id in chapter.used_claim_ids
        )
    )
    citations = tuple(citation for chapter in chapters for citation in chapter.citations)
    package = repository.get_package(blueprint.package_id)
    return GeneratedStory(
        story_id=blueprint.story_id,
        title=blueprint.title,
        story_version=blueprint.version,
        package_version={
            "package_id": package.manifest.package_id,
            "schema_version": package.manifest.schema_version,
            "content_version": package.manifest.content_version,
        },
        audience=StoryAudience.FAMILY,
        chapters=tuple(chapters),
        used_claim_ids=used_claim_ids,
        citations=citations,
        validation_status=StoryValidationStatus.PASSED,
        warnings=(),
    )


def _itinerary(*, external_poi_id: str = "B0FFF49AFB", name: str = "发鸠山景区"):
    return {
        "destination": "长治",
        "days": [
            {
                "day": 1,
                "timeline": [
                    {
                        "type": "attraction",
                        "name": name,
                        "provider": "amap",
                        "external_poi_id": external_poi_id,
                        "curated_anchor_id": ANCHOR_ID,
                        "start_time": "09:00",
                        "end_time": "15:00",
                    },
                    {
                        "type": "lunch",
                        "name": "Dynamic Restaurant",
                        "provider": "amap",
                        "external_poi_id": "DYNAMIC-MEAL",
                    },
                    {
                        "type": "attraction",
                        "name": "Dynamic Attraction",
                        "provider": "amap",
                        "external_poi_id": "DYNAMIC-SPOT",
                    },
                ],
            }
        ],
    }


def _bind(repository, itinerary=None, **updates):
    values = {
        "itinerary_id": "itinerary-1",
        "run_id": "run-1",
        "route_id": ROUTE_ID,
        "itinerary": itinerary or _itinerary(),
    }
    values.update(updates)
    return StoryItineraryBinder(repository).bind(
        _generated_story(repository), StoryBindingRequest(**values)
    )


def test_mandatory_anchor_is_placed_by_verified_provider_identity(repository):
    package = _bind(repository)
    placed = [
        item
        for item in package.chapter_bindings
        if item.placement_type is PlacementType.PLACED
    ]

    assert len(placed) == 4
    assert all(item.anchor_ids == (ANCHOR_ID,) for item in placed)
    assert all(item.resolved_poi_ids[0].provider.value == "amap" for item in placed)
    assert all(item.resolved_poi_ids[0].external_poi_id == "B0FFF49AFB" for item in placed)


def test_binding_uses_repository_verified_binding(repository):
    binding = repository.get_poi_binding(BINDING_ID)
    package = _bind(repository)

    assert binding.is_runtime_eligible
    assert package.chapter_bindings[0].resolved_poi_ids[0].external_poi_id == binding.external_poi_id


def test_multiple_chapters_share_one_itinerary_stop(repository):
    package = _bind(repository)
    placed = package.chapter_bindings[:4]

    assert {item.itinerary_stop_ids for item in placed} == {("day.1.timeline.0",)}
    assert [item.trigger_hint for item in placed] == [
        StoryTriggerHint.ARRIVAL,
        StoryTriggerHint.EARLY_VISIT,
        StoryTriggerHint.MID_VISIT,
        StoryTriggerHint.LATE_VISIT,
    ]


def test_dynamic_pois_receive_no_forced_story(repository):
    package = _bind(repository)
    stop_ids = {
        stop_id for binding in package.chapter_bindings for stop_id in binding.itinerary_stop_ids
    }

    assert "day.1.timeline.1" not in stop_ids
    assert "day.1.timeline.2" not in stop_ids
    assert package.binding_metrics.dynamic_poi_forced_story_count == 0


def test_missing_required_spatial_anchor_is_incomplete(repository):
    package = _bind(repository, itinerary=_itinerary(external_poi_id="OTHER-ID"))

    assert package.validation_status is StoryPackageValidationStatus.INCOMPLETE
    assert len(package.unplaced_chapters) == 4
    assert "required_spatial_chapter_unplaced" in package.warnings


def test_same_name_with_different_identity_is_not_matched(repository):
    package = _bind(
        repository,
        itinerary=_itinerary(external_poi_id="OTHER-ID", name="发鸠山景区"),
    )

    assert package.chapter_bindings[0].placement_type is PlacementType.UNPLACED
    assert package.binding_metrics.name_only_binding_count == 0


def test_chapter_without_anchor_is_context_only(repository):
    package = _bind(repository)
    binding = package.chapter_bindings[4]

    assert binding.placement_type is PlacementType.CONTEXT_ONLY
    assert binding.trigger_hint is StoryTriggerHint.AFTER_VISIT
    assert binding.itinerary_stop_ids == ()


def test_blueprint_remains_independent_of_itinerary(repository):
    before = repository.get_story(STORY_ID).model_dump_json()

    _bind(repository, itinerary_id="different-itinerary", run_id="different-run")

    after = repository.get_story(STORY_ID).model_dump_json()
    assert after == before
    assert "itinerary" not in type(repository.get_story(STORY_ID)).model_fields


def test_binding_does_not_mutate_itinerary(repository):
    itinerary = _itinerary()
    before = deepcopy(itinerary)

    package = _bind(repository, itinerary=itinerary)

    assert itinerary == before
    assert package.binding_metrics.itinerary_mutation_count == 0


def test_binding_does_not_mutate_knowledge(repository):
    before = tuple(item.model_dump_json() for item in repository.list_claims())

    package = _bind(repository)

    assert tuple(item.model_dump_json() for item in repository.list_claims()) == before
    assert package.binding_metrics.knowledge_mutation_count == 0


def test_weather_only_adds_presentation_hint(repository):
    plain = _bind(repository)
    weather = _bind(repository, weather=({"day": 1, "condition": "rain"},))

    assert plain.chapters == weather.chapters
    assert plain.presentation_hints == ()
    assert weather.presentation_hints == ("weather_context_available",)


def test_route_mismatch_is_rejected(repository):
    with pytest.raises(StoryBindingError, match="route does not match"):
        _bind(repository, route_id="other.route")


def test_story_package_is_serializable(repository):
    package = _bind(repository)

    assert StoryPackage.model_validate_json(package.model_dump_json()) == package
    assert package.validation_status is StoryPackageValidationStatus.PASSED
    assert package.media_slots == ()
    assert package.experience_slots == ()


def test_navigation_access_placement_keeps_cultural_anchor_identity(repository):
    access = NavigationAccessPoint.model_validate(
        {
            "access_point_id": "spatial.access.story-test",
            "anchor_id": ANCHOR_ID,
            "name": "Navigation entrance",
            "location": {"longitude": 112.1, "latitude": 36.1},
            "access_type": "general_access",
            "verification_status": "verified",
            "provenance": {
                "provenance_id": "spatial.provenance.story-test",
                "verification_method": "field_survey",
                "verified_at": "2026-08-22T10:00:00+08:00",
                "source_reference": "field-record:story-test",
                "verification_note": "Verified navigation-only test fixture.",
            },
            "accuracy": "precise",
            "confidence": "high",
            "note": "Navigation target only.",
        }
    )

    class AccessRepository:
        def __getattr__(self, name):
            return getattr(repository, name)

        def get_poi_binding(self, _binding_id):
            return None

        def list_verified_bindings_for_anchor(self, _anchor_id):
            return ()

        def list_verified_spatial_identities_for_anchor(self, _anchor_id):
            return ()

        def list_verified_navigation_access_points_for_anchor(self, anchor_id):
            return (access,) if anchor_id == ANCHOR_ID else ()

    itinerary = _itinerary()
    itinerary["days"][0]["timeline"][0].update(
        provider=None,
        external_poi_id=None,
        name="Navigation entrance",
        spatial_identity_type="navigation_access_point",
        spatial_identity_id=access.access_point_id,
    )
    package = StoryItineraryBinder(AccessRepository()).bind(
        _generated_story(repository),
        StoryBindingRequest(
            itinerary_id="itinerary-access",
            route_id=ROUTE_ID,
            itinerary=itinerary,
        ),
    )
    placed = package.chapter_bindings[0]

    assert placed.anchor_ids == (ANCHOR_ID,)
    assert placed.resolved_poi_ids == ()
    assert placed.resolved_spatial_identity_ids == (access.access_point_id,)
    assert placed.placement_reason == "verified_navigation_access_match"


def test_story_binding_core_has_no_regional_or_planning_special_cases():
    prohibited_tokens = {
        "changzhi",
        "jingwei",
        "fajiushan",
        "b0fff49afb",
        "travelplanstate",
    }
    found = []
    for path in sorted((PROJECT_ROOT / "app" / "story").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for token in prohibited_tokens:
                    if token in node.value.casefold():
                        found.append((path.name, token))

    assert not found
