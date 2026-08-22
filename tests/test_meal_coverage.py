from __future__ import annotations

import asyncio

import pytest

from app.planning.helpers import restaurant_to_dict
from app.planning.meal_coverage import (
    DEFAULT_MEAL_SEARCH_LEVELS,
    MealCoverageStatus,
    MealSearchAnchor,
    discover_meal_coverage,
)
from app.planning.nodes import (
    finalize_node,
    make_meal_recommend_node,
    meal_search_node,
)
from app.planning.schemas import SingleDayMealPick, TravelPlanState


def _candidate(
    external_poi_id: str,
    *,
    name: str = "Real Restaurant",
    provider: str = "amap",
) -> dict:
    return {
        "provider": provider,
        "external_poi_id": external_poi_id,
        "name": name,
        "location": {"lng": 112.0, "lat": 36.0},
        "rating": 4.6,
    }


def _anchor(role: str = "primary") -> MealSearchAnchor:
    return MealSearchAnchor(
        name=f"{role} spot",
        location={
            "lng": 112.1 if role == "primary" else 112.2,
            "lat": 36.1 if role == "primary" else 36.2,
        },
        role=role,
    )


def test_default_radius_candidate_stops_without_fallback():
    calls = []

    async def search(_location, radius):
        calls.append(radius)
        return [_candidate("POI-1")]

    result = asyncio.run(discover_meal_coverage([_anchor()], search))

    assert calls == [1000]
    assert result.status is MealCoverageStatus.COVERED
    assert result.candidates[0]["search_level"] == 0
    assert result.candidates[0]["search_radius_m"] == 1000


def test_empty_level_zero_advances_to_level_one():
    calls = []

    async def search(_location, radius):
        calls.append(radius)
        return [] if radius == 1000 else [_candidate("POI-1")]

    result = asyncio.run(discover_meal_coverage([_anchor()], search))

    assert calls == [1000, 3000]
    assert result.status is MealCoverageStatus.FALLBACK_EXPANDED
    assert result.candidates[0]["search_level"] == 1


def test_level_one_candidate_prevents_level_two():
    calls = []

    async def search(_location, radius):
        calls.append(radius)
        return [_candidate("POI-1")] if radius == 3000 else []

    result = asyncio.run(discover_meal_coverage([_anchor()], search))

    assert calls == [1000, 3000]
    assert all(attempt["search_level"] < 2 for attempt in result.attempts)


def test_max_radius_without_candidate_is_uncovered():
    calls = []

    async def search(_location, radius):
        calls.append(radius)
        return []

    result = asyncio.run(discover_meal_coverage([_anchor()], search))

    assert calls == [level.radius_m for level in DEFAULT_MEAL_SEARCH_LEVELS]
    assert result.status is MealCoverageStatus.UNCOVERED
    assert result.candidates == ()
    assert result.max_search_radius_m == 5000


def test_provider_identity_deduplicates_but_same_name_different_ids_remain():
    async def search(_location, _radius):
        return [
            _candidate("POI-1", name="Same Name"),
            _candidate("POI-1", name="Duplicate Response"),
            _candidate("POI-2", name="Same Name"),
        ]

    result = asyncio.run(discover_meal_coverage([_anchor()], search))

    assert [item["external_poi_id"] for item in result.candidates] == [
        "POI-1",
        "POI-2",
    ]
    assert [item["name"] for item in result.candidates] == [
        "Same Name",
        "Same Name",
    ]


def test_secondary_route_anchor_is_a_fallback_with_provenance():
    anchors = [_anchor("primary"), _anchor("secondary")]
    calls = []

    async def search(location, radius):
        calls.append((location, radius))
        return [_candidate("POI-2")] if location == anchors[1].location else []

    result = asyncio.run(discover_meal_coverage(anchors, search))

    assert len(calls) == 2
    assert result.status is MealCoverageStatus.FALLBACK_EXPANDED
    candidate = result.candidates[0]
    assert candidate["search_level"] == 0
    assert candidate["search_radius_m"] == 1000
    assert candidate["search_anchor_role"] == "secondary"
    assert candidate["search_anchor_name"] == "secondary spot"


def test_candidates_without_provider_identity_do_not_count_as_coverage():
    async def search(_location, radius):
        if radius == 1000:
            return [{"name": "Unidentified", "location": {"lng": 1, "lat": 2}}]
        return [_candidate("POI-1")]

    result = asyncio.run(discover_meal_coverage([_anchor()], search))

    assert result.status is MealCoverageStatus.FALLBACK_EXPANDED
    assert result.candidates[0]["external_poi_id"] == "POI-1"


def test_provider_failure_propagates_instead_of_becoming_uncovered():
    async def search(_location, _radius):
        raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(discover_meal_coverage([_anchor()], search))


def _raw_restaurant(external_poi_id: str, name: str = "Real Restaurant") -> dict:
    return {
        "id": external_poi_id,
        "name": name,
        "location": "112.200000,36.200000",
        "distance": "860",
        "address": "Provider address",
        "type": "餐饮服务;中餐厅;中餐厅",
        "biz_ext": {"rating": "4.6", "cost": "45.00"},
    }


def _planning_state() -> TravelPlanState:
    return TravelPlanState(
        query="ordinary trip",
        route=[{
            "day": 1,
            "theme": "route",
            "spots": [
                {
                    "name": "Morning Spot",
                    "period": "morning",
                    "start_time": "09:00",
                    "end_time": "11:30",
                },
                {
                    "name": "Afternoon Spot",
                    "period": "afternoon",
                    "start_time": "14:00",
                    "end_time": "16:00",
                },
            ],
        }],
        pois=[
            {"name": "Morning Spot", "location": {"lng": 112.1, "lat": 36.1}},
            {"name": "Afternoon Spot", "location": {"lng": 112.2, "lat": 36.2}},
        ],
    )


def test_restaurant_normalization_preserves_provider_identity_and_distance():
    restaurant = restaurant_to_dict(_raw_restaurant("AMAP-1"))

    assert restaurant is not None
    assert restaurant["provider"] == "amap"
    assert restaurant["external_poi_id"] == "AMAP-1"
    assert restaurant["provider_distance_m"] == 860


def test_ordinary_non_catalog_meal_search_keeps_default_behavior(monkeypatch):
    calls = []

    async def fake_search(location, _api_key, **kwargs):
        calls.append((location, kwargs["radius"]))
        return [_raw_restaurant(f"AMAP-{len(calls)}")]

    monkeypatch.setattr("app.planning.nodes.amap_key", lambda: "key")
    monkeypatch.setattr("app.planning.nodes.search_around_pois_async", fake_search)

    result = asyncio.run(meal_search_node(_planning_state()))

    assert [radius for _location, radius in calls] == [1000, 1000]
    assert result["meal_candidates"][0]["lunch"]["coverage_status"] == "COVERED"
    assert result["meal_candidates"][0]["dinner"]["coverage_status"] == "COVERED"
    assert _planning_state().catalog_context is None


def test_route_aware_lunch_uses_secondary_anchor_before_radius_expansion(monkeypatch):
    calls = []

    async def fake_search(location, _api_key, **kwargs):
        calls.append((location, kwargs["radius"]))
        if location["lng"] == 112.2:
            return [_raw_restaurant("AMAP-SECONDARY")]
        return []

    monkeypatch.setattr("app.planning.nodes.amap_key", lambda: "key")
    monkeypatch.setattr("app.planning.nodes.search_around_pois_async", fake_search)

    result = asyncio.run(meal_search_node(_planning_state()))
    lunch = result["meal_candidates"][0]["lunch"]

    assert calls[0][1] == calls[1][1] == 1000
    assert lunch["coverage_status"] == "FALLBACK_EXPANDED"
    assert lunch["candidates"][0]["search_anchor_role"] == "secondary"
    assert lunch["candidates"][0]["search_anchor_name"] == "Afternoon Spot"


def test_meal_recommendation_preserves_fallback_metadata_and_note(monkeypatch):
    monkeypatch.setattr(
        "app.planning.nodes.build_structured_llm", lambda *_args, **_kwargs: object()
    )

    async def fake_invoke(_llm, _messages, **_kwargs):
        return SingleDayMealPick(
            lunch_name="Fallback Restaurant",
            lunch_reason="评分合适。",
            dinner_name="",
            dinner_reason="",
        )

    monkeypatch.setattr("app.planning.nodes.ainvoke_structured", fake_invoke)
    candidate = {
        **_candidate("AMAP-FALLBACK", name="Fallback Restaurant"),
        "cost": "45",
        "keytag": "中餐厅",
        "search_level": 0,
        "search_radius_m": 1000,
        "search_anchor_role": "secondary",
        "search_anchor_name": "Afternoon Spot",
    }
    state = TravelPlanState(
        query="trip",
        meal_candidates=[{
            "day": 1,
            "lunch": {
                "anchor": "Morning Spot",
                "candidates": [candidate],
                "coverage_status": "FALLBACK_EXPANDED",
                "search_attempts": [],
            },
            "dinner": {
                "anchor": None,
                "candidates": [],
                "coverage_status": "UNCOVERED",
                "search_attempts": [],
                "max_search_radius_m": 5000,
            },
        }],
    )

    result = asyncio.run(make_meal_recommend_node(None)(state))
    lunch = result["meals"][0]["lunch"]

    assert lunch["external_poi_id"] == "AMAP-FALLBACK"
    assert lunch["meal_coverage_status"] == "FALLBACK_EXPANDED"
    assert "Afternoon Spot" in lunch["reason"]
    assert "1000" in lunch["reason"]


def test_finalize_exposes_honest_uncovered_meal_note():
    state = _planning_state().model_copy(update={
        "meals": [{
            "day": 1,
            "lunch": None,
            "dinner": None,
            "lunch_coverage": {
                "status": "UNCOVERED",
                "note": "达到最大范围仍无可靠餐饮，建议提前自备补给。",
            },
            "dinner_coverage": {"status": "UNCOVERED", "note": "暂无餐饮。"},
        }],
    })

    timeline = finalize_node(state)["final_plan"]["days"][0]["timeline"]
    lunch = next(item for item in timeline if item["type"] == "lunch")

    assert lunch["no_restaurant"] is True
    assert lunch["meal_coverage_status"] == "UNCOVERED"
    assert "自备补给" in lunch["meal_coverage_note"]
