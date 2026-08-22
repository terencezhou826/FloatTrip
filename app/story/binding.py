"""Provider-identity binding from a generated Story to a finished itinerary."""

from __future__ import annotations

from collections import defaultdict
import hashlib

from app.catalog.models import PoiProvider, SpatialIdentityType
from app.catalog.repository import CatalogRepository
from app.story.models import (
    ChapterBinding,
    GeneratedStory,
    PlacementType,
    StoryBindingMetrics,
    StoryBindingRequest,
    StoryKnowledgeSnapshot,
    StoryPackage,
    StoryPackageValidationStatus,
    StoryPoiIdentity,
    StoryTriggerHint,
)


class StoryBindingError(ValueError):
    pass


class StoryItineraryBinder:
    def __init__(self, repository: CatalogRepository) -> None:
        self._repository = repository

    def bind(
        self,
        story: GeneratedStory,
        request: StoryBindingRequest,
    ) -> StoryPackage:
        blueprint = self._repository.get_story(story.story_id)
        if blueprint is None or not blueprint.enabled:
            raise StoryBindingError(f"enabled Story not found: {story.story_id}")
        if request.route_id != blueprint.route_id:
            raise StoryBindingError("itinerary route does not match Story Blueprint")
        generated_by_id = {item.chapter_id: item for item in story.chapters}
        if set(generated_by_id) != set(blueprint.chapter_ids):
            raise StoryBindingError("generated Story chapters do not match Blueprint")

        stops_by_identity = _itinerary_stops_by_identity(request.itinerary)
        stops_by_spatial_identity = _itinerary_stops_by_spatial_identity(
            request.itinerary
        )
        chapters = self._repository.list_story_chapters(blueprint.story_id)
        provisional: list[ChapterBinding] = []
        placed_by_stop: dict[str, list[str]] = defaultdict(list)
        for chapter in chapters:
            if not chapter.anchor_ids:
                provisional.append(
                    ChapterBinding(
                        chapter_id=chapter.chapter_id,
                        anchor_ids=(),
                        resolved_poi_ids=(),
                        itinerary_stop_ids=(),
                        placement_type=PlacementType.CONTEXT_ONLY,
                        trigger_hint=StoryTriggerHint.AFTER_VISIT,
                        recommended_playback_duration=chapter.recommended_duration_sec,
                        placement_reason="chapter_has_no_spatial_anchor",
                    )
                )
                continue

            identities = self._verified_identities(chapter)
            spatial_identities = self._verified_spatial_identities(chapter)
            matched = [
                (identity, stops_by_identity[identity][0])
                for identity in identities
                if stops_by_identity.get(identity)
            ]
            matched_spatial = [
                (identity, stops_by_spatial_identity[identity][0])
                for identity in spatial_identities
                if stops_by_spatial_identity.get(identity)
            ]
            if not matched and not matched_spatial:
                provisional.append(
                    ChapterBinding(
                        chapter_id=chapter.chapter_id,
                        anchor_ids=tuple(chapter.anchor_ids),
                        resolved_poi_ids=tuple(
                            StoryPoiIdentity(
                                provider=provider,
                                external_poi_id=external_poi_id,
                            )
                            for provider, external_poi_id in identities
                        ),
                        resolved_spatial_identity_ids=tuple(
                            identity_id for _, identity_id in spatial_identities
                        ),
                        itinerary_stop_ids=(),
                        placement_type=PlacementType.UNPLACED,
                        trigger_hint=StoryTriggerHint.UNAVAILABLE,
                        recommended_playback_duration=chapter.recommended_duration_sec,
                        placement_reason="required_spatial_anchor_identity_not_in_itinerary",
                    )
                )
                continue

            if matched:
                identity, stop_id = matched[0]
                resolved_poi_ids = (
                    StoryPoiIdentity(
                        provider=identity[0], external_poi_id=identity[1]
                    ),
                )
                resolved_spatial_ids: tuple[str, ...] = ()
                placement_reason = "verified_provider_identity_match"
            else:
                spatial_identity, stop_id = matched_spatial[0]
                resolved_poi_ids = ()
                resolved_spatial_ids = (spatial_identity[1],)
                placement_reason = (
                    "verified_navigation_access_match"
                    if spatial_identity[0]
                    is SpatialIdentityType.NAVIGATION_ACCESS_POINT
                    else "verified_cultural_coordinate_match"
                )
            placed_by_stop[stop_id].append(chapter.chapter_id)
            provisional.append(
                ChapterBinding(
                    chapter_id=chapter.chapter_id,
                    anchor_ids=tuple(chapter.anchor_ids),
                    resolved_poi_ids=resolved_poi_ids,
                    resolved_spatial_identity_ids=resolved_spatial_ids,
                    itinerary_stop_ids=(stop_id,),
                    placement_type=PlacementType.PLACED,
                    trigger_hint=StoryTriggerHint.ARRIVAL,
                    recommended_playback_duration=chapter.recommended_duration_sec,
                    placement_reason=placement_reason,
                )
            )

        bindings = tuple(
            binding.model_copy(
                update={
                    "trigger_hint": _trigger_for_shared_stop(
                        binding,
                        placed_by_stop,
                    )
                }
            )
            for binding in provisional
        )
        unplaced = tuple(
            item.chapter_id
            for item in bindings
            if item.placement_type is PlacementType.UNPLACED
        )
        validation_status = (
            StoryPackageValidationStatus.INCOMPLETE
            if unplaced
            else StoryPackageValidationStatus.PASSED
        )
        warnings = (
            ("required_spatial_chapter_unplaced",) if unplaced else ()
        )
        presentation_hints = (
            ("weather_context_available",) if request.weather else ()
        )
        return StoryPackage(
            package_id=(
                "story-package."
                + hashlib.sha256(
                    f"{story.story_id}:{request.itinerary_id}".encode("utf-8")
                ).hexdigest()[:24]
            ),
            story_id=story.story_id,
            story_version=story.story_version,
            catalog_version=story.package_version,
            itinerary_id=request.itinerary_id,
            run_id=request.run_id,
            audience=story.audience,
            route_id=blueprint.route_id,
            chapters=story.chapters,
            chapter_bindings=bindings,
            unplaced_chapters=unplaced,
            warnings=warnings,
            knowledge_snapshot=StoryKnowledgeSnapshot(
                catalog_version=story.package_version,
                used_claim_ids=story.used_claim_ids,
                citations=story.citations,
            ),
            media_slots=tuple(blueprint.media_slot_ids),
            experience_slots=tuple(blueprint.experience_slot_ids),
            presentation_hints=presentation_hints,
            validation_status=validation_status,
            binding_metrics=StoryBindingMetrics(),
        )

    def _verified_identities(self, chapter) -> tuple[tuple[PoiProvider, str], ...]:
        explicit = {
            item.binding_id
            for item in (
                self._repository.get_poi_binding(binding_id)
                for binding_id in chapter.poi_binding_ids
            )
            if item is not None and item.is_runtime_eligible
        }
        identities: list[tuple[PoiProvider, str]] = []
        for anchor_id in chapter.anchor_ids:
            for binding in self._repository.list_verified_bindings_for_anchor(anchor_id):
                if explicit and binding.binding_id not in explicit:
                    continue
                identities.append((binding.provider, binding.external_poi_id))
        return tuple(dict.fromkeys(identities))

    def _verified_spatial_identities(
        self, chapter
    ) -> tuple[tuple[SpatialIdentityType, str], ...]:
        identities: list[tuple[SpatialIdentityType, str]] = []
        for anchor_id in chapter.anchor_ids:
            identities.extend(
                (
                    SpatialIdentityType.VERIFIED_COORDINATE,
                    item.spatial_identity_id,
                )
                for item in self._repository.list_verified_spatial_identities_for_anchor(
                    anchor_id
                )
            )
            identities.extend(
                (
                    SpatialIdentityType.NAVIGATION_ACCESS_POINT,
                    item.access_point_id,
                )
                for item in self._repository.list_verified_navigation_access_points_for_anchor(
                    anchor_id
                )
            )
        return tuple(dict.fromkeys(identities))


def _itinerary_stops_by_identity(
    itinerary: dict,
) -> dict[tuple[PoiProvider, str], list[str]]:
    stops: dict[tuple[PoiProvider, str], list[str]] = defaultdict(list)
    for day in itinerary.get("days") or []:
        day_number = day.get("day")
        for index, item in enumerate(day.get("timeline") or []):
            if item.get("type") != "attraction":
                continue
            provider_raw = item.get("provider")
            external_poi_id = str(item.get("external_poi_id") or "").strip()
            if not provider_raw or not external_poi_id:
                continue
            try:
                provider = PoiProvider(str(getattr(provider_raw, "value", provider_raw)))
            except ValueError:
                continue
            stop_id = str(item.get("stop_id") or f"day.{day_number}.timeline.{index}")
            stops[(provider, external_poi_id)].append(stop_id)
    return stops


def _itinerary_stops_by_spatial_identity(
    itinerary: dict,
) -> dict[tuple[SpatialIdentityType, str], list[str]]:
    stops: dict[tuple[SpatialIdentityType, str], list[str]] = defaultdict(list)
    for day in itinerary.get("days") or []:
        day_number = day.get("day")
        for index, item in enumerate(day.get("timeline") or []):
            if item.get("type") != "attraction":
                continue
            identity_id = str(item.get("spatial_identity_id") or "").strip()
            identity_type_raw = item.get("spatial_identity_type")
            if not identity_id or not identity_type_raw:
                continue
            try:
                identity_type = SpatialIdentityType(
                    str(getattr(identity_type_raw, "value", identity_type_raw))
                )
            except ValueError:
                continue
            if identity_type is SpatialIdentityType.PROVIDER_POI:
                continue
            stop_id = str(item.get("stop_id") or f"day.{day_number}.timeline.{index}")
            stops[(identity_type, identity_id)].append(stop_id)
    return stops


def _trigger_for_shared_stop(
    binding: ChapterBinding,
    placed_by_stop: dict[str, list[str]],
) -> StoryTriggerHint:
    if binding.placement_type is not PlacementType.PLACED:
        return binding.trigger_hint
    stop_id = binding.itinerary_stop_ids[0]
    siblings = placed_by_stop[stop_id]
    index = siblings.index(binding.chapter_id)
    if len(siblings) == 1:
        return StoryTriggerHint.ARRIVAL
    hints = (
        StoryTriggerHint.ARRIVAL,
        StoryTriggerHint.EARLY_VISIT,
        StoryTriggerHint.MID_VISIT,
        StoryTriggerHint.LATE_VISIT,
        StoryTriggerHint.DEPARTURE,
    )
    return hints[min(index, len(hints) - 1)]
