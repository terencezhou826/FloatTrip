from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    CommercialRelationship,
    LocalResourceType,
    PoiProvider,
    PriceStatus,
    ResourceOperationalStatus,
    ResourceVerificationStatus,
)
from app.planning.route_feasibility import TravelTimeMatrix
from app.providers.travel_time import TransportMode, TravelLeg
from app.resources import (
    FreshnessStatus,
    LocalResourceRecommendationEngine,
    LocalResourceRecommendationRequest,
    MatchReason,
    RecommendationCandidate,
    RecommendationPriceSnapshot,
    RecommendationStatus,
    ResourceProvenanceType,
)
from tests.test_experience_binding import _bind as bind_experience
from tests.test_story_binding import _bind as bind_story


CATALOG_ROOT = Path(__file__).resolve().parents[1] / "content" / "catalog"


def _itinerary() -> dict:
    return {
        "destination": "Test Destination",
        "days": [
            {
                "day": 1,
                "timeline": [
                    {
                        "type": "attraction",
                        "name": "First Stop",
                        "provider": "amap",
                        "external_poi_id": "STOP-A",
                        "location": {"lng": 112.0, "lat": 36.0},
                        "start_time": "09:00",
                        "end_time": "11:00",
                    },
                    {
                        "type": "lunch",
                        "name": "Selected Meal",
                        "provider": "amap",
                        "external_poi_id": "MEAL-SELECTED",
                        "location": {"lng": 112.01, "lat": 36.01},
                    },
                    {
                        "type": "attraction",
                        "name": "Second Stop",
                        "provider": "amap",
                        "external_poi_id": "STOP-B",
                        "location": {"lng": 112.1, "lat": 36.1},
                        "start_time": "14:00",
                        "end_time": "16:00",
                    },
                ],
            }
        ],
    }


def _candidate(
    external_id: str = "RESOURCE-NEAR",
    *,
    resource_id: str | None = None,
    name: str = "Nearby Restaurant",
    discovery_stop_id: str = "day.1.timeline.0",
    freshness: FreshnessStatus = FreshnessStatus.FRESH,
    relationship: CommercialRelationship = CommercialRelationship.NONE,
    price_status: PriceStatus = PriceStatus.UNKNOWN,
) -> RecommendationCandidate:
    price = RecommendationPriceSnapshot(price_status=price_status)
    if price_status is not PriceStatus.UNKNOWN:
        price = RecommendationPriceSnapshot(
            price_status=price_status,
            currency="CNY",
            amount="30",
            unit="person",
            source_type="runtime_provider",
            source_ref="amap.biz_ext.cost",
            updated_at="2026-08-22T10:00:00Z",
            freshness_status=freshness,
        )
    return RecommendationCandidate(
        resource_id=resource_id or f"runtime-resource.{external_id.casefold()}",
        provenance_type=ResourceProvenanceType.RUNTIME_PROVIDER,
        resource_type=LocalResourceType.RESTAURANT,
        name=name,
        provider=PoiProvider.AMAP,
        external_poi_id=external_id,
        longitude=112.01,
        latitude=36.01,
        discovery_stop_id=discovery_stop_id,
        provider_distance_m=500,
        rating=4.0,
        review_count=100,
        tags=("中餐厅",),
        price_info=price,
        freshness_status=freshness,
        operational_status=ResourceOperationalStatus.UNKNOWN,
        verification_status=ResourceVerificationStatus.CANDIDATE,
        commercial_relationship=relationship,
        disclosure_required=relationship in {
            CommercialRelationship.PARTNER,
            CommercialRelationship.SPONSORED,
        },
        disclosure_text=(
            "Test commercial disclosure"
            if relationship
            in {CommercialRelationship.PARTNER, CommercialRelationship.SPONSORED}
            else None
        ),
    )


class FakeTravelTimeProvider:
    provider = PoiProvider.AMAP

    async def get_travel_time(self, origin, destination, transport_mode):
        assert transport_mode is TransportMode.DRIVING
        if any(
            "FAR" in external_id
            for external_id in (origin.external_poi_id, destination.external_poi_id)
        ):
            duration, distance = 40 * 60, 40_000
        elif origin.external_poi_id == "STOP-A" and destination.external_poi_id == "STOP-B":
            duration, distance = 8 * 60, 8_000
        else:
            duration, distance = 5 * 60, 2_000
        return TravelLeg(
            from_poi=origin,
            to_poi=destination,
            distance_m=distance,
            duration_s=duration,
            provider=PoiProvider.AMAP,
            transport_mode=transport_mode,
            source="fake.travel-time",
        )


def _engine() -> LocalResourceRecommendationEngine:
    return LocalResourceRecommendationEngine(
        TravelTimeMatrix({PoiProvider.AMAP: FakeTravelTimeProvider()})
    )


def _request(max_results: int = 10) -> LocalResourceRecommendationRequest:
    return LocalResourceRecommendationRequest(
        run_id="run-test",
        itinerary_id="itinerary-test",
        resource_types=(LocalResourceType.RESTAURANT,),
        max_results=max_results,
    )


def _recommend(*candidates, itinerary=None, **kwargs):
    return asyncio.run(
        _engine().recommend(
            _request(),
            itinerary=itinerary or _itinerary(),
            candidates=tuple(candidates),
            **kwargs,
        )
    )


def test_nearby_restaurant_ranks_well():
    recommendation = _recommend(_candidate()).recommendations[0]
    assert recommendation.recommendation_status is RecommendationStatus.RECOMMENDED
    assert MatchReason.LOW_DETOUR in recommendation.match_reasons


def test_huge_detour_is_rejected():
    recommendation = _recommend(_candidate("RESOURCE-FAR")).recommendations[0]
    assert recommendation.recommendation_status is RecommendationStatus.NOT_SUITABLE
    assert MatchReason.ROUTE_NOT_FEASIBLE in recommendation.match_reasons


def test_far_restaurant_ranks_after_nearby_restaurant():
    result = _recommend(_candidate("RESOURCE-FAR"), _candidate("RESOURCE-NEAR"))
    assert [item.external_poi_id for item in result.recommendations] == [
        "RESOURCE-NEAR", "RESOURCE-FAR"
    ]


def test_selected_meal_is_recognized_by_exact_identity():
    recommendation = _recommend(
        _candidate("MEAL-SELECTED", discovery_stop_id="day.1.timeline.2")
    ).recommendations[0]
    assert recommendation.recommendation_status is RecommendationStatus.RECOMMENDED
    assert recommendation.related_itinerary_stop_ids == ("day.1.timeline.1",)
    assert MatchReason.SELECTED_MEAL in recommendation.match_reasons
    assert recommendation.detour_minutes == 0


def test_same_name_different_provider_ids_remain_distinct():
    result = _recommend(
        _candidate("RESOURCE-ONE", name="Same Name"),
        _candidate("RESOURCE-TWO", name="Same Name"),
    )
    assert len(result.recommendations) == 2
    assert {item.external_poi_id for item in result.recommendations} == {
        "RESOURCE-ONE", "RESOURCE-TWO"
    }


def test_sponsorship_does_not_boost_editorial_score():
    none = _candidate("RESOURCE-ONE", relationship=CommercialRelationship.NONE)
    sponsored = _candidate(
        "RESOURCE-TWO", relationship=CommercialRelationship.SPONSORED
    )
    result = _recommend(none, sponsored)
    scores = {item.external_poi_id: item.editorial_score for item in result.recommendations}
    assert scores["RESOURCE-ONE"] == scores["RESOURCE-TWO"]


def test_partner_disclosure_is_preserved():
    recommendation = _recommend(
        _candidate("RESOURCE-PARTNER", relationship=CommercialRelationship.PARTNER)
    ).recommendations[0]
    assert recommendation.disclosure == "Test commercial disclosure"


def test_unknown_price_is_preserved():
    recommendation = _recommend(_candidate()).recommendations[0]
    assert recommendation.price_info.price_status is PriceStatus.UNKNOWN
    assert recommendation.price_info.amount is None


def test_real_provider_price_is_not_invented_or_changed():
    recommendation = _recommend(
        _candidate(price_status=PriceStatus.PER_PERSON)
    ).recommendations[0]
    assert recommendation.price_info.amount == 30
    assert recommendation.price_info.source_ref == "amap.biz_ext.cost"
    assert MatchReason.PRICE_DATA_AVAILABLE in recommendation.match_reasons


def test_stale_resource_has_warning_and_score_penalty():
    fresh, stale = _recommend(
        _candidate("RESOURCE-FRESH"),
        _candidate("RESOURCE-STALE", freshness=FreshnessStatus.STALE),
    ).recommendations
    assert fresh.editorial_score > stale.editorial_score
    assert MatchReason.STALE_DATA in stale.match_reasons


def test_every_resource_recommendation_is_optional():
    result = _recommend(_candidate(), _candidate("RESOURCE-FAR"))
    assert all(item.optional is True for item in result.recommendations)
    assert result.metrics.mandatory_commerce_count == 0


def test_deterministic_ranking():
    candidates = (_candidate("RESOURCE-TWO"), _candidate("RESOURCE-ONE"))
    first = _recommend(*candidates)
    second = _recommend(*reversed(candidates))
    assert first == second


def test_max_results_is_respected():
    result = asyncio.run(
        _engine().recommend(
            _request(max_results=1),
            itinerary=_itinerary(),
            candidates=(_candidate("RESOURCE-ONE"), _candidate("RESOURCE-TWO")),
        )
    )
    assert len(result.recommendations) == 1


def test_itinerary_is_not_mutated():
    itinerary = _itinerary()
    before = deepcopy(itinerary)
    _recommend(_candidate(), itinerary=itinerary)
    assert itinerary == before


def test_story_and_experience_are_context_only_and_not_mutated():
    repository = FileCatalogLoader(CATALOG_ROOT).load()
    story = bind_story(repository)
    experience = bind_experience(repository)
    story_before = story.model_dump_json()
    experience_before = experience.model_dump_json()
    itinerary = _itinerary()
    itinerary["days"][0]["timeline"][0].update(
        name="发鸠山景区", external_poi_id="B0FFF49AFB"
    )
    recommendation = _recommend(
        _candidate(),
        itinerary=itinerary,
        story_package=story,
        experience_package=experience,
    ).recommendations[0]
    assert story.model_dump_json() == story_before
    assert experience.model_dump_json() == experience_before
    assert len(recommendation.related_story_chapter_ids) == 4
    assert len(recommendation.related_experience_activity_ids) == 4
    assert recommendation.cultural_identity is False


def test_inactive_candidate_is_not_suitable():
    candidate = _candidate().model_copy(
        update={"operational_status": ResourceOperationalStatus.INACTIVE}
    )
    recommendation = _recommend(candidate).recommendations[0]
    assert recommendation.recommendation_status is RecommendationStatus.NOT_SUITABLE


def test_metrics_remain_zero_for_valid_recommendations():
    metrics = _recommend(_candidate()).metrics
    assert all(value == 0 for value in metrics.model_dump().values())
