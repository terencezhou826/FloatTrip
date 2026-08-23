"""Exact-identity placement of generated Experiences onto a Story itinerary."""

from __future__ import annotations

import hashlib

from app.catalog.repository import CatalogRepository
from app.core.package_snapshots import package_snapshot_hash
from app.experience.models import (
    ActivityBinding,
    ExperienceBindingMetrics,
    ExperienceBindingRequest,
    ExperienceKnowledgeSnapshot,
    ExperiencePackage,
    ExperiencePackageDraft,
    ExperiencePackageValidationStatus,
    ExperiencePlacementType,
    ExperienceSafetySummary,
)
from app.story.binding import (
    _itinerary_stops_by_identity,
    _itinerary_stops_by_spatial_identity,
)
from app.story.models import (
    PlacementType,
    StoryPackage,
    StoryPoiIdentity,
    StoryTriggerHint,
)


class ExperienceBindingError(ValueError):
    pass


class ExperienceItineraryBinder:
    def __init__(self, repository: CatalogRepository) -> None:
        self._repository = repository

    def bind(
        self,
        draft: ExperiencePackageDraft,
        story_package: StoryPackage,
        request: ExperienceBindingRequest,
    ) -> ExperiencePackage:
        blueprint = self._repository.get_experience(draft.experience_id)
        if blueprint is None or not blueprint.enabled:
            raise ExperienceBindingError(
                f"enabled Experience not found: {draft.experience_id}"
            )
        if blueprint.version != draft.experience_version:
            raise ExperienceBindingError("Experience version does not match Blueprint")
        if request.route_id != blueprint.route_id:
            raise ExperienceBindingError("itinerary route does not match Experience")
        if (
            story_package.story_id != draft.story_id
            or story_package.story_version != draft.story_version
            or story_package.story_id != blueprint.story_id
        ):
            raise ExperienceBindingError("StoryPackage does not match Experience draft")
        if story_package.catalog_version != draft.catalog_version:
            raise ExperienceBindingError("Story and Experience catalog versions differ")
        if (
            story_package.itinerary_id != request.itinerary_id
            or story_package.run_id != request.run_id
            or story_package.route_id != request.route_id
        ):
            raise ExperienceBindingError("StoryPackage does not match itinerary request")

        activities = self._repository.list_activities(blueprint.experience_id)
        generated_by_id = {item.activity_id: item for item in draft.activities}
        if set(generated_by_id) != set(blueprint.activity_ids):
            raise ExperienceBindingError("generated Activities do not match Blueprint")

        chapter_bindings = {
            item.chapter_id: item for item in story_package.chapter_bindings
        }
        stops_by_identity = _itinerary_stops_by_identity(request.itinerary)
        stops_by_spatial_identity = _itinerary_stops_by_spatial_identity(
            request.itinerary
        )
        bad_weather = any(item.get("is_bad") is True for item in request.weather)
        bindings: list[ActivityBinding] = []
        for activity in activities:
            generated = generated_by_id[activity.activity_id]
            if generated.estimated_duration_sec != activity.estimated_duration_sec:
                raise ExperienceBindingError("generated Activity duration changed")
            if not activity.anchor_ids:
                bindings.append(
                    ActivityBinding(
                        activity_id=activity.activity_id,
                        story_chapter_ids=tuple(activity.story_chapter_ids),
                        anchor_ids=(),
                        resolved_poi_ids=(),
                        resolved_spatial_identity_ids=(),
                        itinerary_stop_ids=(),
                        placement_type=ExperiencePlacementType.CONTEXT_ONLY,
                        trigger_hint=StoryTriggerHint.AFTER_VISIT,
                        recommended_duration_sec=generated.estimated_duration_sec,
                        placement_reason="activity_has_no_spatial_anchor",
                        safety_context=tuple(activity.safety_constraints),
                    )
                )
                continue

            matched = self._match_activity(
                activity,
                chapter_bindings,
                stops_by_identity,
                stops_by_spatial_identity,
            )
            if matched is None:
                bindings.append(
                    ActivityBinding(
                        activity_id=activity.activity_id,
                        story_chapter_ids=tuple(activity.story_chapter_ids),
                        anchor_ids=tuple(activity.anchor_ids),
                        resolved_poi_ids=(),
                        resolved_spatial_identity_ids=(),
                        itinerary_stop_ids=(),
                        placement_type=ExperiencePlacementType.UNPLACED,
                        trigger_hint=StoryTriggerHint.UNAVAILABLE,
                        recommended_duration_sec=generated.estimated_duration_sec,
                        placement_reason="required_spatial_identity_not_in_itinerary",
                        safety_context=tuple(activity.safety_constraints),
                    )
                )
                continue

            identities, spatial_ids, stop_ids, trigger_hint, degraded, disclosure, safety = matched
            if bad_weather and activity.weather_sensitive:
                bindings.append(
                    ActivityBinding(
                        activity_id=activity.activity_id,
                        story_chapter_ids=tuple(activity.story_chapter_ids),
                        anchor_ids=tuple(activity.anchor_ids),
                        resolved_poi_ids=identities,
                        resolved_spatial_identity_ids=spatial_ids,
                        itinerary_stop_ids=(),
                        placement_type=ExperiencePlacementType.WEATHER_ADAPTED,
                        trigger_hint=StoryTriggerHint.AFTER_VISIT,
                        recommended_duration_sec=generated.estimated_duration_sec,
                        placement_reason="weather_sensitive_activity_adapted_to_context_only",
                        safety_context=tuple(activity.safety_constraints)
                        + safety
                        + (
                            "complete_in_a_safe_sheltered_area_or_after_the_visit_without_extra_movement",
                        ),
                        spatial_degraded=degraded,
                        location_disclosure=disclosure,
                    )
                )
                continue

            bindings.append(
                ActivityBinding(
                    activity_id=activity.activity_id,
                    story_chapter_ids=tuple(activity.story_chapter_ids),
                    anchor_ids=tuple(activity.anchor_ids),
                    resolved_poi_ids=identities,
                    resolved_spatial_identity_ids=spatial_ids,
                    itinerary_stop_ids=stop_ids,
                    placement_type=ExperiencePlacementType.PLACED,
                    trigger_hint=trigger_hint,
                    recommended_duration_sec=generated.estimated_duration_sec,
                    placement_reason=(
                        "story_chapter_verified_locality_identity_match"
                        if degraded
                        else "story_chapter_verified_spatial_identity_match"
                    ),
                    safety_context=tuple(activity.safety_constraints) + safety,
                    spatial_degraded=degraded,
                    location_disclosure=disclosure,
                )
            )

        binding_tuple = tuple(bindings)
        unplaced = tuple(
            item.activity_id
            for item in binding_tuple
            if item.placement_type
            in (ExperiencePlacementType.SKIPPED, ExperiencePlacementType.UNPLACED)
        )
        warnings = (
            ("required_spatial_activity_unplaced",) if unplaced else ()
        )
        status = (
            ExperiencePackageValidationStatus.INCOMPLETE
            if unplaced
            else ExperiencePackageValidationStatus.PASSED
        )
        return ExperiencePackage(
            package_id=(
                "experience-package."
                + hashlib.sha256(
                    f"{draft.experience_id}:{request.itinerary_id}".encode("utf-8")
                ).hexdigest()[:24]
            ),
            experience_id=draft.experience_id,
            experience_version=draft.experience_version,
            story_package_id=story_package.package_id,
            story_snapshot_hash=package_snapshot_hash(story_package),
            story_id=draft.story_id,
            story_version=draft.story_version,
            catalog_version=draft.catalog_version,
            run_id=request.run_id,
            itinerary_id=request.itinerary_id,
            audience=draft.audience,
            activities=draft.activities,
            activity_bindings=binding_tuple,
            unplaced_activities=unplaced,
            warnings=warnings,
            safety_summary=_safety_summary(draft),
            knowledge_snapshot=ExperienceKnowledgeSnapshot(
                catalog_version=draft.catalog_version,
                used_claim_ids=draft.used_claim_ids,
                citations=draft.citations,
            ),
            validation_status=status,
            media_slots=tuple(blueprint.media_slot_ids),
            completion_tracking_slots=(),
            binding_metrics=ExperienceBindingMetrics(),
        )

    def _match_activity(
        self,
        activity,
        chapter_bindings,
        stops_by_identity,
        stops_by_spatial_identity,
    ):
        allowed_identities = {
            (binding.provider, binding.external_poi_id)
            for binding in (
                self._repository.get_poi_binding(binding_id)
                for binding_id in activity.poi_binding_ids
            )
            if binding is not None
            and binding.is_runtime_eligible
            and binding.anchor_id in activity.anchor_ids
        }
        identities: list[StoryPoiIdentity] = []
        spatial_ids: list[str] = []
        stop_ids: list[str] = []
        trigger_hint = StoryTriggerHint.ARRIVAL
        for chapter_id in activity.story_chapter_ids:
            chapter_binding = chapter_bindings.get(chapter_id)
            if (
                chapter_binding is None
                or chapter_binding.placement_type is not PlacementType.PLACED
                or not set(chapter_binding.anchor_ids).intersection(activity.anchor_ids)
            ):
                return None
            matched = [
                identity
                for identity in chapter_binding.resolved_poi_ids
                if (identity.provider, identity.external_poi_id) in allowed_identities
                and stops_by_identity.get(
                    (identity.provider, identity.external_poi_id)
                )
            ]
            matched_spatial = [
                identity_id
                for identity_id in chapter_binding.resolved_spatial_identity_ids
                if any(
                    identity_id == key[1] and stops_by_spatial_identity.get(key)
                    for key in stops_by_spatial_identity
                )
            ]
            if matched:
                identity = matched[0]
                expected_stops = stops_by_identity[
                    (identity.provider, identity.external_poi_id)
                ]
                identities.append(identity)
            elif matched_spatial:
                identity_id = matched_spatial[0]
                expected_stops = [
                    stop_id
                    for key, values in stops_by_spatial_identity.items()
                    if key[1] == identity_id
                    for stop_id in values
                ]
                spatial_ids.append(identity_id)
            else:
                return None
            chapter_stops = [
                stop_id for stop_id in chapter_binding.itinerary_stop_ids
                if stop_id in expected_stops
            ]
            if not chapter_stops:
                return None
            stop_ids.extend(chapter_stops)
            trigger_hint = chapter_binding.trigger_hint
        locality_records = [
            locality
            for anchor_id in activity.anchor_ids
            for locality in self._repository.list_verified_locality_identities_for_anchor(
                anchor_id
            )
            if locality.locality_identity_id in spatial_ids
        ]
        degraded = bool(locality_records)
        disclosure = (
            locality_records[0].disclosure_text if locality_records else None
        )
        safety = tuple(
            dict.fromkeys(
                constraint.value
                for locality in locality_records
                for constraint in locality.safety_constraints
            )
        )
        return (
            tuple(dict.fromkeys(identities)),
            tuple(dict.fromkeys(spatial_ids)),
            tuple(dict.fromkeys(stop_ids)),
            trigger_hint,
            degraded,
            disclosure,
            safety,
        )


def _safety_summary(draft: ExperiencePackageDraft) -> ExperienceSafetySummary:
    fields = ExperienceSafetySummary.model_fields
    totals = {
        name: sum(
            getattr(activity.grounding_metrics, name)
            for activity in draft.activities
        )
        for name in fields
    }
    return ExperienceSafetySummary(**totals)
