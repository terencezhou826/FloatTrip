"""Deterministic contextual recommendation for optional local resources."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import Field, StrictBool, model_validator

from app.catalog.models import (
    CatalogModel,
    CommercialRelationship,
    CurrencyCode,
    LocalResource,
    LocalResourceType,
    PoiProvider,
    PriceStatus,
    ResourceOperationalStatus,
    ResourceVerificationStatus,
    StableId,
)
from app.catalog.repository import CatalogRepository
from app.experience.models import ExperiencePackage
from app.planning.route_feasibility import (
    MealDetourPolicy,
    TravelTimeMatrix,
    assess_meal_detour,
    scheduled_gap_seconds,
    travel_point_from_item,
)
from app.providers.travel_time import TravelPoint, TravelRoutingError
from app.resources.models import (
    FreshnessStatus,
    ResourceProvenanceType,
    RuntimeResourceCandidate,
    classify_freshness,
)
from app.story.models import StoryPackage


class BudgetPreference(StrEnum):
    UNSPECIFIED = "unspecified"
    ECONOMY = "economy"
    BALANCED = "balanced"
    PREMIUM = "premium"


class RecommendationStatus(StrEnum):
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"
    NOT_SUITABLE = "NOT_SUITABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class MatchReason(StrEnum):
    SELECTED_MEAL = "selected_meal"
    NEAR_ITINERARY_STOP = "near_itinerary_stop"
    LOW_DETOUR = "low_detour"
    MEAL_TIME_MATCH = "meal_time_match"
    USER_PREFERENCE_MATCH = "user_preference_match"
    PRICE_DATA_AVAILABLE = "price_data_available"
    PROVIDER_RATING_AVAILABLE = "provider_rating_available"
    ROUTE_FEASIBLE = "route_feasible"
    STALE_DATA = "stale_data"
    ROUTE_NOT_FEASIBLE = "route_not_feasible"
    ROUTING_UNAVAILABLE = "routing_unavailable"


class ContextualRelation(StrEnum):
    SELECTED_MEAL = "selected_meal"
    NEARBY = "nearby"


class LocalResourceRecommendationRequest(CatalogModel):
    run_id: str = Field(min_length=1, max_length=256)
    itinerary_id: str = Field(min_length=1, max_length=256)
    story_package_id: StableId | None = None
    experience_package_id: StableId | None = None
    resource_types: tuple[LocalResourceType, ...] = ()
    user_preferences: tuple[str, ...] = ()
    budget_preference: BudgetPreference = BudgetPreference.UNSPECIFIED
    max_results: int = Field(default=5, ge=1, le=50)


class RecommendationPriceSnapshot(CatalogModel):
    price_status: PriceStatus
    currency: CurrencyCode | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    min_amount: Decimal | None = Field(default=None, ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)
    unit: str | None = None
    source_type: ResourceProvenanceType | None = None
    source_ref: str | None = None
    updated_at: datetime | None = None
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN


class RecommendationCandidate(CatalogModel):
    resource_id: StableId
    provenance_type: ResourceProvenanceType
    resource_type: LocalResourceType
    name: str = Field(min_length=1, max_length=256)
    provider: PoiProvider
    external_poi_id: str = Field(min_length=1, max_length=256)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    discovery_stop_id: str | None = None
    provider_distance_m: int | None = Field(default=None, ge=0)
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    tags: tuple[str, ...] = ()
    price_info: RecommendationPriceSnapshot
    freshness_status: FreshnessStatus
    operational_status: ResourceOperationalStatus
    verification_status: ResourceVerificationStatus
    commercial_relationship: CommercialRelationship
    disclosure_required: StrictBool = False
    disclosure_text: str | None = None

    @model_validator(mode="after")
    def validate_candidate_source(self) -> "RecommendationCandidate":
        if (
            self.provenance_type is ResourceProvenanceType.RUNTIME_PROVIDER
            and self.verification_status is not ResourceVerificationStatus.CANDIDATE
        ):
            raise ValueError("runtime recommendation input must remain candidate")
        if (
            self.provenance_type is ResourceProvenanceType.CURATED_CATALOG
            and self.verification_status is not ResourceVerificationStatus.VERIFIED
        ):
            raise ValueError("curated recommendation input must be verified")
        if self.commercial_relationship in {
            CommercialRelationship.PARTNER,
            CommercialRelationship.SPONSORED,
        } and (not self.disclosure_required or not self.disclosure_text):
            raise ValueError("commercial candidate requires disclosure")
        return self

    @property
    def identity(self) -> tuple[PoiProvider, str]:
        return self.provider, self.external_poi_id


class ResourceRecommendation(CatalogModel):
    resource_id: StableId
    resource_type: LocalResourceType
    name: str
    provider: PoiProvider
    external_poi_id: str
    related_itinerary_stop_ids: tuple[str, ...]
    related_story_chapter_ids: tuple[StableId, ...]
    related_experience_activity_ids: tuple[StableId, ...]
    contextual_relation: ContextualRelation
    cultural_identity: StrictBool = False
    recommendation_status: RecommendationStatus
    match_reasons: tuple[MatchReason, ...]
    editorial_score: float
    distance_m: int | None = Field(default=None, ge=0)
    detour_minutes: float | None = Field(default=None, ge=0)
    price_info: RecommendationPriceSnapshot
    resource_freshness: FreshnessStatus
    operational_status: ResourceOperationalStatus
    commercial_relationship: CommercialRelationship
    disclosure: str | None = None
    optional: StrictBool = True

    @model_validator(mode="after")
    def validate_optional_commerce(self) -> "ResourceRecommendation":
        if not self.optional:
            raise ValueError("local resource recommendations must be optional")
        if self.commercial_relationship in {
            CommercialRelationship.PARTNER,
            CommercialRelationship.SPONSORED,
        } and self.disclosure is None:
            raise ValueError("commercial recommendation requires disclosure")
        if self.cultural_identity:
            raise ValueError("contextual resource cannot assert cultural identity")
        return self


class RecommendationMetrics(CatalogModel):
    fake_resource_count: int = Field(default=0, ge=0)
    name_only_identity_count: int = Field(default=0, ge=0)
    price_hallucination_count: int = Field(default=0, ge=0)
    sponsorship_ranking_influence_count: int = Field(default=0, ge=0)
    hidden_sponsorship_count: int = Field(default=0, ge=0)
    mandatory_commerce_count: int = Field(default=0, ge=0)
    knowledge_mutation_count: int = Field(default=0, ge=0)
    story_mutation_count: int = Field(default=0, ge=0)
    experience_mutation_count: int = Field(default=0, ge=0)
    itinerary_mutation_count: int = Field(default=0, ge=0)


class RecommendationResult(CatalogModel):
    recommendations: tuple[ResourceRecommendation, ...]
    warnings: tuple[str, ...]
    metrics: RecommendationMetrics = Field(default_factory=RecommendationMetrics)


def recommendation_candidate_from_runtime(
    resource: RuntimeResourceCandidate,
) -> RecommendationCandidate:
    price = resource.price_info
    return RecommendationCandidate(
        resource_id=resource.runtime_resource_id,
        provenance_type=resource.provenance_type,
        resource_type=resource.resource_type,
        name=resource.name,
        provider=resource.provider,
        external_poi_id=resource.external_poi_id,
        longitude=resource.coordinates.longitude,
        latitude=resource.coordinates.latitude,
        discovery_stop_id=resource.discovery_stop_id,
        provider_distance_m=resource.provider_distance_m,
        rating=resource.rating,
        review_count=resource.review_count,
        tags=tuple(filter(None, (resource.poi_type,))),
        price_info=RecommendationPriceSnapshot(
            price_status=price.price_status,
            currency=price.currency,
            amount=price.amount,
            unit=price.unit,
            source_type=(
                ResourceProvenanceType.RUNTIME_PROVIDER
                if price.price_status is not PriceStatus.UNKNOWN
                else None
            ),
            source_ref=price.source_field,
            updated_at=price.retrieved_at,
            freshness_status=price.freshness_status,
        ),
        freshness_status=resource.freshness_status,
        operational_status=resource.operational_status,
        verification_status=resource.verification_status,
        commercial_relationship=resource.commercial_relationship,
    )


def recommendation_candidate_from_catalog(
    resource: LocalResource,
    repository: CatalogRepository,
    *,
    as_of: datetime,
    freshness_max_age: timedelta,
) -> RecommendationCandidate | None:
    if not repository.is_resource_recommendation_eligible(
        resource.resource_id, as_of=as_of.date()
    ) or resource.coordinates is None:
        return None
    bindings = sorted(
        (
            binding
            for binding in resource.provider_bindings
            if binding.provider.value in {item.value for item in PoiProvider}
        ),
        key=lambda item: (item.provider.value, item.external_id),
    )
    if not bindings:
        return None
    binding = bindings[0]
    provider = PoiProvider(binding.provider.value)
    price = resource.price_info
    price_freshness = classify_freshness(
        price.updated_at,
        as_of=as_of,
        max_age=freshness_max_age,
    )
    return RecommendationCandidate(
        resource_id=resource.resource_id,
        provenance_type=ResourceProvenanceType.CURATED_CATALOG,
        resource_type=resource.resource_type,
        name=resource.name,
        provider=provider,
        external_poi_id=binding.external_id,
        longitude=resource.coordinates.longitude,
        latitude=resource.coordinates.latitude,
        tags=tuple(resource.tags),
        price_info=RecommendationPriceSnapshot(
            price_status=price.price_status,
            currency=price.currency,
            amount=price.amount,
            min_amount=price.min_amount,
            max_amount=price.max_amount,
            unit=price.unit,
            source_type=(
                ResourceProvenanceType.CURATED_CATALOG
                if price.price_status is not PriceStatus.UNKNOWN
                else None
            ),
            source_ref=price.source_ref,
            updated_at=price.updated_at,
            freshness_status=price_freshness,
        ),
        freshness_status=classify_freshness(
            resource.last_verified_at,
            as_of=as_of,
            max_age=freshness_max_age,
        ),
        operational_status=resource.operational_status,
        verification_status=resource.verification_status,
        commercial_relationship=resource.commercial_relationship,
        disclosure_required=resource.disclosure_required,
        disclosure_text=resource.disclosure_text,
    )


def itinerary_stop_id(day_number: int, timeline_index: int) -> str:
    return f"day.{day_number}.timeline.{timeline_index}"


def _itinerary_stops(itinerary: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any]]] = []
    for day in itinerary.get("days", []):
        day_number = int(day.get("day") or 0)
        for index, item in enumerate(day.get("timeline", [])):
            if travel_point_from_item(item) is not None:
                result.append((itinerary_stop_id(day_number, index), item))
    return result


class LocalResourceRecommendationEngine:
    def __init__(
        self,
        matrix: TravelTimeMatrix,
        *,
        detour_policy: MealDetourPolicy = MealDetourPolicy(),
    ) -> None:
        self._matrix = matrix
        self._detour_policy = detour_policy

    async def recommend(
        self,
        request: LocalResourceRecommendationRequest,
        *,
        itinerary: dict[str, Any],
        candidates: tuple[RecommendationCandidate, ...],
        story_package: StoryPackage | None = None,
        experience_package: ExperiencePackage | None = None,
    ) -> RecommendationResult:
        stops = _itinerary_stops(itinerary)
        stops_by_id = dict(stops)
        meal_ids = {
            travel_point_from_item(item).identity: stop_id
            for stop_id, item in stops
            if item.get("type") in {"lunch", "dinner"}
            and travel_point_from_item(item) is not None
        }
        filtered = [
            candidate
            for candidate in candidates
            if not request.resource_types
            or candidate.resource_type in request.resource_types
        ]
        evaluated = []
        for candidate in filtered:
            evaluated.append(
                await self._evaluate(
                    candidate,
                    stops,
                    stops_by_id,
                    meal_ids,
                    request.user_preferences,
                    story_package,
                    experience_package,
                )
            )
        status_order = {
            RecommendationStatus.RECOMMENDED: 0,
            RecommendationStatus.OPTIONAL: 1,
            RecommendationStatus.INSUFFICIENT_DATA: 2,
            RecommendationStatus.NOT_SUITABLE: 3,
        }
        evaluated.sort(
            key=lambda item: (
                status_order[item.recommendation_status],
                -item.editorial_score,
                item.provider.value,
                item.external_poi_id,
            )
        )
        selected = tuple(evaluated[: request.max_results])
        warnings = tuple(
            dict.fromkeys(
                "resource data is stale"
                for item in selected
                if item.resource_freshness is FreshnessStatus.STALE
            )
        )
        return RecommendationResult(recommendations=selected, warnings=warnings)

    async def _evaluate(
        self,
        candidate: RecommendationCandidate,
        stops: list[tuple[str, dict[str, Any]]],
        stops_by_id: dict[str, dict[str, Any]],
        meal_ids: dict[tuple[PoiProvider, str], str],
        preferences: tuple[str, ...],
        story_package: StoryPackage | None,
        experience_package: ExperiencePackage | None,
    ) -> ResourceRecommendation:
        match_reasons: list[MatchReason] = []
        related_stop_ids: tuple[str, ...] = ()
        contextual_relation = ContextualRelation.NEARBY
        distance_m = candidate.provider_distance_m
        detour_minutes: float | None = None
        status = RecommendationStatus.INSUFFICIENT_DATA
        score = 0.0

        selected_meal_id = meal_ids.get(candidate.identity)
        if selected_meal_id is not None:
            related_stop_ids = (selected_meal_id,)
            contextual_relation = ContextualRelation.SELECTED_MEAL
            status = RecommendationStatus.RECOMMENDED
            match_reasons.extend((MatchReason.SELECTED_MEAL, MatchReason.MEAL_TIME_MATCH))
            distance_m = 0
            detour_minutes = 0.0
            score = 10_000.0
        elif candidate.operational_status is ResourceOperationalStatus.INACTIVE:
            status = RecommendationStatus.NOT_SUITABLE
            match_reasons.append(MatchReason.ROUTE_NOT_FEASIBLE)
        elif candidate.discovery_stop_id in stops_by_id:
            related_stop_ids = (candidate.discovery_stop_id,)
            match_reasons.append(MatchReason.NEAR_ITINERARY_STOP)
            previous_item = stops_by_id[candidate.discovery_stop_id]
            previous = travel_point_from_item(previous_item)
            following_item = self._next_attraction(
                candidate.discovery_stop_id, stops
            )
            following = (
                travel_point_from_item(following_item)
                if following_item is not None
                else None
            )
            candidate_point = TravelPoint(
                provider=candidate.provider,
                external_poi_id=candidate.external_poi_id,
                name=candidate.name,
                longitude=candidate.longitude,
                latitude=candidate.latitude,
            )
            try:
                assessment = await assess_meal_detour(
                    previous,
                    candidate_point,
                    following,
                    self._matrix,
                    available_gap_s=(
                        scheduled_gap_seconds(previous_item, following_item)
                        if following_item is not None
                        else None
                    ),
                    policy=self._detour_policy,
                )
            except TravelRoutingError:
                match_reasons.append(MatchReason.ROUTING_UNAVAILABLE)
            else:
                distance_m = assessment.total_distance_m
                detour_minutes = round(assessment.extra_duration_s / 60, 1)
                if assessment.route_feasible:
                    match_reasons.append(MatchReason.ROUTE_FEASIBLE)
                    if assessment.extra_duration_s <= 15 * 60:
                        status = RecommendationStatus.RECOMMENDED
                        match_reasons.append(MatchReason.LOW_DETOUR)
                    else:
                        status = RecommendationStatus.OPTIONAL
                    score = 1000.0 - assessment.extra_duration_s / 60
                else:
                    status = RecommendationStatus.NOT_SUITABLE
                    match_reasons.append(MatchReason.ROUTE_NOT_FEASIBLE)
                    score = -1000.0

        if candidate.rating is not None:
            score += candidate.rating * 10
            match_reasons.append(MatchReason.PROVIDER_RATING_AVAILABLE)
        if candidate.review_count is not None:
            score += min(candidate.review_count, 1000) / 100
        if candidate.price_info.price_status is not PriceStatus.UNKNOWN:
            match_reasons.append(MatchReason.PRICE_DATA_AVAILABLE)
        if candidate.freshness_status is FreshnessStatus.STALE:
            score -= 20
            match_reasons.append(MatchReason.STALE_DATA)
        normalized_preferences = {
            item.casefold().strip() for item in preferences if item.strip()
        }
        searchable = " ".join((candidate.name, *candidate.tags)).casefold()
        if any(value in searchable for value in normalized_preferences):
            score += 10
            match_reasons.append(MatchReason.USER_PREFERENCE_MATCH)

        story_ids, activity_ids = _related_package_context(
            related_stop_ids, story_package, experience_package
        )
        disclosure = (
            candidate.disclosure_text
            if candidate.commercial_relationship
            in {CommercialRelationship.PARTNER, CommercialRelationship.SPONSORED}
            else None
        )
        return ResourceRecommendation(
            resource_id=candidate.resource_id,
            resource_type=candidate.resource_type,
            name=candidate.name,
            provider=candidate.provider,
            external_poi_id=candidate.external_poi_id,
            related_itinerary_stop_ids=related_stop_ids,
            related_story_chapter_ids=story_ids,
            related_experience_activity_ids=activity_ids,
            contextual_relation=contextual_relation,
            recommendation_status=status,
            match_reasons=tuple(dict.fromkeys(match_reasons)),
            editorial_score=round(score, 6),
            distance_m=distance_m,
            detour_minutes=detour_minutes,
            price_info=candidate.price_info,
            resource_freshness=candidate.freshness_status,
            operational_status=candidate.operational_status,
            commercial_relationship=candidate.commercial_relationship,
            disclosure=disclosure,
        )

    @staticmethod
    def _next_attraction(
        stop_id: str,
        stops: list[tuple[str, dict[str, Any]]],
    ) -> dict[str, Any] | None:
        found = False
        for current_id, item in stops:
            if current_id == stop_id:
                found = True
                continue
            if found and item.get("type") == "attraction":
                return item
        return None


def _related_package_context(
    stop_ids: tuple[str, ...],
    story_package: StoryPackage | None,
    experience_package: ExperiencePackage | None,
) -> tuple[tuple[StableId, ...], tuple[StableId, ...]]:
    stop_set = set(stop_ids)
    chapters = (
        tuple(
            binding.chapter_id
            for binding in story_package.chapter_bindings
            if stop_set.intersection(binding.itinerary_stop_ids)
        )
        if story_package is not None
        else ()
    )
    activities = (
        tuple(
            binding.activity_id
            for binding in experience_package.activity_bindings
            if stop_set.intersection(binding.itinerary_stop_ids)
        )
        if experience_package is not None
        else ()
    )
    return chapters, activities
