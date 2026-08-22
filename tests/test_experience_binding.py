from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import ExperienceAudience
from app.experience import (
    ExperienceBindingError,
    ExperienceBindingRequest,
    ExperienceGenerationService,
    ExperienceItineraryBinder,
    ExperiencePackage,
    ExperiencePackageDraft,
    ExperiencePackageValidationStatus,
    ExperiencePlacementType,
    ExperienceValidationStatus,
    render_experience_activity,
)
from app.story import PlacementType
from tests.test_experience_generation import _contexts, _valid_activity
from tests.test_story_binding import (
    ANCHOR_ID,
    ROUTE_ID,
    _bind as bind_story,
    _generated_story,
    _itinerary,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
EXPERIENCE_ID = "changzhi.experience.jingwei-family"


@pytest.fixture(scope="module")
def repository():
    return FileCatalogLoader(CATALOG_ROOT).load()


def _draft(repository) -> ExperiencePackageDraft:
    story = _generated_story(repository)
    service = ExperienceGenerationService(repository, story)
    activities = tuple(
        render_experience_activity(_valid_activity(context), context.activity)
        for context in _contexts(service)
    )
    blueprint = repository.get_experience(EXPERIENCE_ID)
    return ExperiencePackageDraft(
        experience_id=blueprint.experience_id,
        experience_version=blueprint.version,
        story_id=story.story_id,
        story_version=story.story_version,
        catalog_version=story.package_version,
        audience=ExperienceAudience.FAMILY,
        activities=activities,
        used_claim_ids=tuple(
            dict.fromkeys(
                claim_id for item in activities for claim_id in item.used_claim_ids
            )
        ),
        citations=tuple(
            citation for item in activities for citation in item.citations
        ),
        validation_status=ExperienceValidationStatus.PASSED,
        warnings=(),
    )


def _request(itinerary=None, **updates) -> ExperienceBindingRequest:
    values = {
        "itinerary_id": "itinerary-1",
        "run_id": "run-1",
        "route_id": ROUTE_ID,
        "itinerary": itinerary or _itinerary(),
    }
    values.update(updates)
    return ExperienceBindingRequest(**values)


def _bind(repository, itinerary=None, weather=()):
    itinerary = itinerary or _itinerary()
    story_package = bind_story(repository, itinerary=itinerary, weather=weather)
    return ExperienceItineraryBinder(repository).bind(
        _draft(repository),
        story_package,
        _request(itinerary=itinerary, weather=weather),
    )


def test_activity_follows_bound_story_chapter(repository):
    package = _bind(repository)
    story_package = bind_story(repository)
    story_bindings = {
        item.chapter_id: item for item in story_package.chapter_bindings
    }

    for binding in package.activity_bindings[:4]:
        assert len(binding.story_chapter_ids) == 1
        chapter_binding = story_bindings[binding.story_chapter_ids[0]]
        assert chapter_binding.placement_type is PlacementType.PLACED
        assert binding.itinerary_stop_ids == chapter_binding.itinerary_stop_ids


def test_activity_chapter_anchor_and_verified_poi_identity(repository):
    package = _bind(repository)
    verified = repository.list_verified_bindings_for_anchor(ANCHOR_ID)[0]

    for binding in package.activity_bindings[:4]:
        assert binding.anchor_ids == (ANCHOR_ID,)
        assert binding.resolved_poi_ids[0].provider == verified.provider
        assert (
            binding.resolved_poi_ids[0].external_poi_id
            == verified.external_poi_id
        )


def test_provider_and_external_id_are_both_required(repository):
    package = _bind(repository)

    assert all(
        item.resolved_poi_ids[0].provider.value == "amap"
        and item.resolved_poi_ids[0].external_poi_id == "B0FFF49AFB"
        for item in package.activity_bindings[:4]
    )
    assert package.binding_metrics.name_only_binding_count == 0


def test_same_name_with_different_id_is_not_matched(repository):
    itinerary = _itinerary(external_poi_id="OTHER-ID", name="发鸠山景区")
    package = _bind(repository, itinerary=itinerary)

    assert package.validation_status is ExperiencePackageValidationStatus.INCOMPLETE
    assert all(
        item.placement_type is ExperiencePlacementType.UNPLACED
        for item in package.activity_bindings[:4]
    )
    assert package.binding_metrics.name_only_binding_count == 0


def test_multiple_activities_can_share_one_verified_stop(repository):
    package = _bind(repository)

    assert {
        item.itinerary_stop_ids for item in package.activity_bindings[:4]
    } == {("day.1.timeline.0",)}
    assert len(package.activity_bindings[:4]) == 4


def test_anchorless_reflection_is_context_only(repository):
    binding = _bind(repository).activity_bindings[4]

    assert binding.placement_type is ExperiencePlacementType.CONTEXT_ONLY
    assert binding.itinerary_stop_ids == ()
    assert binding.resolved_poi_ids == ()


def test_dynamic_pois_receive_no_forced_experience(repository):
    package = _bind(repository)
    stop_ids = {
        stop_id
        for binding in package.activity_bindings
        for stop_id in binding.itinerary_stop_ids
    }

    assert "day.1.timeline.1" not in stop_ids
    assert "day.1.timeline.2" not in stop_ids
    assert package.binding_metrics.dynamic_poi_forced_experience_count == 0


def test_missing_required_anchor_makes_package_incomplete(repository):
    itinerary = _itinerary(external_poi_id="OTHER-ID")
    package = _bind(repository, itinerary=itinerary)

    assert package.validation_status is ExperiencePackageValidationStatus.INCOMPLETE
    assert len(package.unplaced_activities) == 4
    assert "required_spatial_activity_unplaced" in package.warnings


def test_bad_weather_adapts_sensitive_activities_without_outdoor_placement(
    repository,
):
    package = _bind(repository, weather=({"day": 1, "is_bad": True},))
    by_id = {item.activity_id: item for item in package.activity_bindings}

    assert by_id[
        "changzhi.experience.jingwei-family.activity.arrival-observation"
    ].placement_type is ExperiencePlacementType.WEATHER_ADAPTED
    assert by_id[
        "changzhi.experience.jingwei-family.activity.persistence-reflection"
    ].placement_type is ExperiencePlacementType.WEATHER_ADAPTED
    assert all(
        not item.itinerary_stop_ids
        for item in package.activity_bindings
        if item.placement_type is ExperiencePlacementType.WEATHER_ADAPTED
    )
    assert package.binding_metrics.unsafe_weather_placement_count == 0


def test_good_weather_keeps_spatial_activities_placed(repository):
    package = _bind(repository, weather=({"day": 1, "is_bad": False},))

    assert all(
        item.placement_type is ExperiencePlacementType.PLACED
        for item in package.activity_bindings[:4]
    )


def test_binding_does_not_mutate_inputs_or_catalog(repository):
    itinerary = _itinerary()
    draft = _draft(repository)
    story_package = bind_story(repository, itinerary=itinerary)
    before = (
        deepcopy(itinerary),
        deepcopy(draft),
        deepcopy(story_package),
        tuple(item.model_dump_json() for item in repository.list_claims()),
    )

    package = ExperienceItineraryBinder(repository).bind(
        draft, story_package, _request(itinerary=itinerary)
    )

    assert itinerary == before[0]
    assert draft == before[1]
    assert story_package == before[2]
    assert tuple(item.model_dump_json() for item in repository.list_claims()) == before[3]
    assert package.binding_metrics.itinerary_mutation_count == 0
    assert package.binding_metrics.story_mutation_count == 0
    assert package.binding_metrics.knowledge_mutation_count == 0


def test_story_package_mismatch_is_rejected(repository):
    story_package = bind_story(repository)
    changed = story_package.model_copy(update={"story_version": "other-version"})

    with pytest.raises(ExperienceBindingError, match="does not match"):
        ExperienceItineraryBinder(repository).bind(
            _draft(repository), changed, _request()
        )


def test_experience_version_mismatch_is_rejected(repository):
    draft = _draft(repository).model_copy(update={"experience_version": "other"})

    with pytest.raises(ExperienceBindingError, match="version"):
        ExperienceItineraryBinder(repository).bind(
            draft, bind_story(repository), _request()
        )


def test_package_round_trip_and_snapshots(repository):
    package = _bind(repository)

    assert ExperiencePackage.model_validate_json(package.model_dump_json()) == package
    assert package.catalog_version.content_version == "0.3.0"
    assert package.knowledge_snapshot.used_claim_ids
    assert package.completion_tracking_slots == ()
    assert package.validation_status is ExperiencePackageValidationStatus.PASSED


def test_safety_summary_is_machine_checkable_and_zero(repository):
    summary = _bind(repository).safety_summary.model_dump()

    assert summary
    assert all(value == 0 for value in summary.values())


def test_binding_has_no_gps_frontend_or_regional_special_cases():
    prohibited_tokens = {
        "changzhi",
        "jingwei",
        "fajiushan",
        "b0fff49afb",
        "gps",
        "frontend",
        "travelplanstate",
    }
    found = []
    for path in [PROJECT_ROOT / "app" / "experience" / "binding.py"]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for token in prohibited_tokens:
                    if token in node.value.casefold():
                        found.append((path.name, token))

    assert not found
