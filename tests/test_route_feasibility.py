from __future__ import annotations

import asyncio

import pytest

from app.catalog.models import PoiProvider
from app.planning.graph import (
    build_graph,
    build_modification_graph,
    build_runtime_revision_graph,
)
from app.planning.nodes import route_feasibility_node
from app.planning.nodes import finalize_node
from app.planning.route_feasibility import (
    MealDetourPolicy,
    RouteFeasibilityPolicy,
    RouteFeasibilityStatus,
    TravelTimeMatrix,
    assess_meal_detour,
    evaluate_route_feasibility,
)
from app.planning.runtime_worker import snapshot_to_state
from app.planning.schemas import TravelPlanState
from app.providers.amap.travel_time import AmapTravelTimeProvider
from app.providers.travel_time import (
    TransportMode,
    TravelLeg,
    TravelPoint,
    TravelRoutingError,
)


def _point(
    external_poi_id: str,
    *,
    name: str | None = None,
    lng: float = 112.0,
    lat: float = 36.0,
) -> TravelPoint:
    return TravelPoint(
        provider=PoiProvider.AMAP,
        external_poi_id=external_poi_id,
        name=name or external_poi_id,
        longitude=lng,
        latitude=lat,
    )


class FakeTravelTimeProvider:
    provider = PoiProvider.AMAP

    def __init__(self, routes: dict[tuple[str, str], tuple[int, int] | Exception]):
        self.routes = routes
        self.calls: list[tuple[str, str]] = []

    async def get_travel_time(
        self,
        origin: TravelPoint,
        destination: TravelPoint,
        transport_mode: TransportMode,
    ) -> TravelLeg:
        assert transport_mode is TransportMode.DRIVING
        pair = (origin.external_poi_id, destination.external_poi_id)
        self.calls.append(pair)
        response = self.routes[pair]
        if isinstance(response, Exception):
            raise response
        distance_m, duration_s = response
        return TravelLeg(
            from_poi=origin,
            to_poi=destination,
            distance_m=distance_m,
            duration_s=duration_s,
            provider=self.provider,
            transport_mode=transport_mode,
            source="fake-road-routing",
        )


def _matrix(
    routes: dict[tuple[str, str], tuple[int, int] | Exception],
    *,
    cache: dict | None = None,
) -> tuple[TravelTimeMatrix, FakeTravelTimeProvider]:
    provider = FakeTravelTimeProvider(routes)
    return (
        TravelTimeMatrix({PoiProvider.AMAP: provider}, cache=cache),
        provider,
    )


def _spot(point: TravelPoint, start: str, end: str, *, mandatory: bool = False) -> dict:
    return {
        "name": point.name,
        "period": "morning",
        "start_time": start,
        "end_time": end,
        "provider": point.provider.value,
        "external_poi_id": point.external_poi_id,
        "curated_anchor_id": "route.anchor.required" if mandatory else None,
        "is_mandatory": mandatory,
    }


def _poi(point: TravelPoint, *, mandatory: bool = False) -> dict:
    return {
        "name": point.name,
        "provider": point.provider.value,
        "external_poi_id": point.external_poi_id,
        "location": {"lng": point.longitude, "lat": point.latitude},
        "curated_anchor_id": "route.anchor.required" if mandatory else None,
        "is_mandatory": mandatory,
    }


def _route(points: list[TravelPoint], times: list[tuple[str, str]]) -> list[dict]:
    return [{
        "day": 1,
        "theme": "generic route",
        "spots": [
            _spot(point, start, end, mandatory=(index == 0))
            for index, (point, (start, end)) in enumerate(zip(points, times))
        ],
    }]


def test_short_route_with_sufficient_gap_is_feasible():
    a, b = _point("A"), _point("B", lng=112.01)
    matrix, provider = _matrix({("A", "B"): (3200, 900)})

    result = asyncio.run(evaluate_route_feasibility(
        _route([a, b], [("09:00", "10:00"), ("10:30", "11:30")]),
        [_poi(a, mandatory=True), _poi(b)],
        matrix,
    ))

    assert result.status is RouteFeasibilityStatus.FEASIBLE
    assert result.legs[0].scheduled_gap_s == 1800
    assert result.legs[0].required_gap_s == 1500
    assert result.legs[0].feasibility == "PASS"
    assert provider.calls == [("A", "B")]


def test_real_driving_time_over_scheduled_gap_requires_replan():
    a, b = _point("A"), _point("B", lng=112.4)
    matrix, _provider = _matrix({("A", "B"): (56000, 4200)})

    result = asyncio.run(evaluate_route_feasibility(
        _route([a, b], [("09:00", "12:30"), ("13:00", "15:00")]),
        [_poi(a, mandatory=True), _poi(b)],
        matrix,
    ))

    assert result.status is RouteFeasibilityStatus.REPLAN_REQUIRED
    assert result.legs[0].scheduled_gap_s == 1800
    assert result.legs[0].duration_s == 4200
    assert result.violations[0].kind == "insufficient_travel_gap"


def test_planner_time_correction_passes_without_requerying_same_pair():
    a, b = _point("A"), _point("B")
    matrix, provider = _matrix({("A", "B"): (12000, 2400)})
    pois = [_poi(a, mandatory=True), _poi(b)]

    failed = asyncio.run(evaluate_route_feasibility(
        _route([a, b], [("09:00", "12:00"), ("12:30", "14:00")]),
        pois,
        matrix,
    ))
    corrected = asyncio.run(evaluate_route_feasibility(
        _route([a, b], [("09:00", "12:00"), ("13:00", "14:30")]),
        pois,
        matrix,
    ))

    assert failed.status is RouteFeasibilityStatus.REPLAN_REQUIRED
    assert corrected.status is RouteFeasibilityStatus.FEASIBLE
    assert provider.calls == [("A", "B")]


def test_replacing_dynamic_poi_only_queries_new_od_pair():
    a, b, c, d = (_point(item) for item in ("A", "B", "C", "D"))
    matrix, provider = _matrix({
        ("A", "B"): (1000, 300),
        ("B", "C"): (1000, 300),
        ("B", "D"): (1200, 360),
    })
    times = [("09:00", "10:00"), ("10:30", "11:30"), ("12:00", "13:00")]

    first = asyncio.run(evaluate_route_feasibility(
        _route([a, b, c], times), [_poi(a, mandatory=True), _poi(b), _poi(c)], matrix
    ))
    second = asyncio.run(evaluate_route_feasibility(
        _route([a, b, d], times), [_poi(a, mandatory=True), _poi(b), _poi(d)], matrix
    ))

    assert first.status is second.status is RouteFeasibilityStatus.FEASIBLE
    assert provider.calls == [("A", "B"), ("B", "C"), ("B", "D")]


def test_provider_error_propagates_as_explicit_routing_failure():
    a, b = _point("A"), _point("B")
    matrix, _provider = _matrix({
        ("A", "B"): TravelRoutingError("provider unavailable")
    })

    with pytest.raises(TravelRoutingError, match="provider unavailable"):
        asyncio.run(evaluate_route_feasibility(
            _route([a, b], [("09:00", "10:00"), ("11:00", "12:00")]),
            [_poi(a, mandatory=True), _poi(b)],
            matrix,
        ))


def test_same_od_pair_is_cached_and_not_called_twice():
    a, b = _point("A"), _point("B")
    matrix, provider = _matrix({("A", "B"): (1000, 300)})

    first = asyncio.run(matrix.get_leg(a, b))
    second = asyncio.run(matrix.get_leg(a, b))

    assert first == second
    assert provider.calls == [("A", "B")]


def test_same_identity_is_zero_leg_without_provider_call():
    a1 = _point("A", name="First display")
    a2 = _point("A", name="Second display")
    matrix, provider = _matrix({})

    leg = asyncio.run(matrix.get_leg(a1, a2))

    assert leg.distance_m == 0
    assert leg.duration_s == 0
    assert leg.source == "same_poi_identity"
    assert provider.calls == []


def test_same_name_different_ids_are_not_treated_as_same_identity():
    a = _point("A", name="Same Name")
    b = _point("B", name="Same Name")
    matrix, provider = _matrix({("A", "B"): (800, 240)})

    leg = asyncio.run(matrix.get_leg(a, b))

    assert leg.distance_m == 800
    assert provider.calls == [("A", "B")]


def test_missing_provider_identity_is_unresolved_not_feasible():
    route = [{
        "day": 1,
        "theme": "legacy",
        "spots": [
            {"name": "A", "start_time": "09:00", "end_time": "10:00"},
            {"name": "B", "start_time": "11:00", "end_time": "12:00"},
        ],
    }]
    matrix, provider = _matrix({})

    result = asyncio.run(evaluate_route_feasibility(
        route,
        [
            {"name": "A", "location": {"lng": 112.0, "lat": 36.0}},
            {"name": "B", "location": {"lng": 112.1, "lat": 36.1}},
        ],
        matrix,
    ))

    assert result.status is RouteFeasibilityStatus.UNRESOLVED
    assert provider.calls == []
    assert result.violations[0].kind == "missing_routing_identity"


def test_high_daily_driving_is_a_soft_warning_not_hard_failure():
    a, b, c = _point("A"), _point("B"), _point("C")
    matrix, _provider = _matrix({
        ("A", "B"): (45000, 4500),
        ("B", "C"): (45000, 4500),
    })
    policy = RouteFeasibilityPolicy(soft_max_daily_driving_s=7200)

    result = asyncio.run(evaluate_route_feasibility(
        _route(
            [a, b, c],
            [("08:00", "09:00"), ("10:30", "11:30"), ("13:00", "14:00")],
        ),
        [_poi(a, mandatory=True), _poi(b), _poi(c)],
        matrix,
        policy=policy,
    ))

    assert result.status is RouteFeasibilityStatus.FEASIBLE
    assert result.total_duration_s == 9000
    assert any("daily driving" in warning for warning in result.warnings)


def test_meal_near_next_spot_but_far_from_previous_is_rejected():
    previous = _point("PREVIOUS")
    meal = _point("MEAL", name="Real Restaurant")
    next_spot = _point("NEXT")
    matrix, _provider = _matrix({
        ("PREVIOUS", "NEXT"): (50000, 3600),
        ("PREVIOUS", "MEAL"): (52000, 4200),
        ("MEAL", "NEXT"): (500, 180),
    })

    result = asyncio.run(assess_meal_detour(
        previous,
        meal,
        next_spot,
        matrix,
        available_gap_s=10800,
        policy=MealDetourPolicy(max_single_leg_duration_s=3600),
    ))

    assert result.route_feasible is False
    assert result.total_duration_s == 4380
    assert "single_leg_duration" in result.rejection_reasons


def test_meal_in_reasonable_corridor_is_accepted():
    previous = _point("PREVIOUS")
    meal = _point("MEAL", name="Real Restaurant")
    next_spot = _point("NEXT")
    matrix, _provider = _matrix({
        ("PREVIOUS", "NEXT"): (18000, 1800),
        ("PREVIOUS", "MEAL"): (9000, 1000),
        ("MEAL", "NEXT"): (10000, 1100),
    })

    result = asyncio.run(assess_meal_detour(
        previous,
        meal,
        next_spot,
        matrix,
        available_gap_s=7200,
    ))

    assert result.route_feasible is True
    assert result.extra_duration_s == 300
    assert result.total_duration_s == 2100
    assert len(result.travel_legs) == 2


def test_feasibility_node_feedback_preserves_mandatory_and_requests_generic_fix():
    mandatory, dynamic = _point("MANDATORY"), _point("DYNAMIC")
    matrix, _provider = _matrix({("MANDATORY", "DYNAMIC"): (70000, 4800)})
    state = TravelPlanState(
        query="ordinary or curated trip",
        approved=True,
        route=_route(
            [mandatory, dynamic],
            [("09:00", "12:30"), ("13:00", "15:00")],
        ),
        pois=[_poi(mandatory, mandatory=True), _poi(dynamic)],
        mandatory_pois=[_poi(mandatory, mandatory=True)],
    )

    update = asyncio.run(route_feasibility_node(state, matrix=matrix))

    assert update["route_feasibility_status"] == "REPLAN_REQUIRED"
    assert "不得删除 mandatory POI" in update["route_modify_opinion"]
    assert "调整景点时间" in update["route_modify_opinion"]
    assert "非 mandatory POI" in update["route_modify_opinion"]
    assert "approved" not in update


def test_feasibility_state_round_trip_preserves_legs_and_cache():
    a, b = _point("A"), _point("B")
    matrix, _provider = _matrix({("A", "B"): (1200, 360)})
    result = asyncio.run(evaluate_route_feasibility(
        _route([a, b], [("09:00", "10:00"), ("11:00", "12:00")]),
        [_poi(a, mandatory=True), _poi(b)],
        matrix,
    ))
    state = TravelPlanState(
        query="trip",
        route_feasibility_status=result.status.value,
        travel_legs=[leg.model_dump(mode="json") for leg in result.legs],
        travel_leg_cache=matrix.export_cache(),
    )

    restored = snapshot_to_state(state.model_dump(mode="json"))

    assert restored.route_feasibility_status == "FEASIBLE"
    assert restored.travel_legs[0]["distance_m"] == 1200
    assert restored.travel_leg_cache == state.travel_leg_cache


def test_finalize_totals_follow_selected_meal_corridor_not_direct_leg():
    a = _point("A", name="Morning")
    meal = _point("MEAL", name="Lunch")
    b = _point("B", name="Afternoon")
    matrix, _provider = _matrix({
        ("A", "B"): (18000, 1800),
        ("A", "MEAL"): (9000, 1000),
        ("MEAL", "B"): (10000, 1100),
    })
    direct = asyncio.run(matrix.get_leg(a, b))
    first = asyncio.run(matrix.get_leg(a, meal))
    second = asyncio.run(matrix.get_leg(meal, b))
    route = _route([a, b], [("09:00", "11:30"), ("14:00", "16:00")])
    route[0]["spots"][1]["period"] = "afternoon"
    state = TravelPlanState(
        query="trip",
        route=route,
        pois=[_poi(a, mandatory=True), _poi(b)],
        meals=[{
            "day": 1,
            "lunch": {
                "name": meal.name,
                "provider": "amap",
                "external_poi_id": meal.external_poi_id,
                "location": {"lng": meal.longitude, "lat": meal.latitude},
                "meal_route_feasible": True,
                "meal_available_gap_minutes": 150.0,
            },
            "dinner": None,
        }],
        route_feasibility_status="FEASIBLE",
        travel_legs=[{
            "day": 1,
            **direct.model_dump(mode="json"),
            "scheduled_gap_s": 9000,
            "required_gap_s": 2400,
            "feasibility": "PASS",
        }],
        travel_leg_cache=matrix.export_cache(),
    )

    plan = finalize_node(state)["final_plan"]
    summary = plan["travel_summary"]

    assert [item["external_poi_id"] for item in [
        summary["legs"][0]["from_poi"],
        summary["legs"][0]["to_poi"],
        summary["legs"][1]["to_poi"],
    ]] == ["A", "MEAL", "B"]
    assert summary["total_driving_distance_m"] == first.distance_m + second.distance_m
    assert summary["total_driving_duration_s"] == first.duration_s + second.duration_s
    assert summary["total_driving_distance_m"] != direct.distance_m


def test_all_planning_graphs_put_feasibility_after_route_review_path():
    graphs = [build_graph(), build_modification_graph(), build_runtime_revision_graph()]

    for graph in graphs:
        nodes = set(graph.get_graph().nodes)
        edges = {(edge.source, edge.target) for edge in graph.get_graph().edges}
        assert "route_feasibility" in nodes
        assert any(target == "route_feasibility" for _source, target in edges)
        assert ("route_feasibility", "planner") in edges


def test_amap_adapter_projects_real_road_fields_and_provenance():
    async def lookup(_origin, _destination, api_key):
        assert api_key == "secret"
        return {
            "status": "1",
            "route": {"paths": [{"distance": "12345", "duration": "2345"}]},
        }

    provider = AmapTravelTimeProvider("secret", lookup=lookup)
    leg = asyncio.run(provider.get_travel_time(
        _point("A"), _point("B"), TransportMode.DRIVING
    ))

    assert leg.distance_m == 12345
    assert leg.duration_s == 2345
    assert leg.provider is PoiProvider.AMAP
    assert leg.transport_mode is TransportMode.DRIVING
    assert leg.source == "amap.direction.driving.v3"


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "0", "info": "INVALID_USER_KEY"},
        {"status": "1", "route": {"paths": []}},
        {"status": "1", "route": {"paths": [{"distance": "", "duration": ""}]}},
    ],
)
def test_amap_adapter_rejects_provider_or_incomplete_results(payload):
    async def lookup(_origin, _destination, _api_key):
        return payload

    provider = AmapTravelTimeProvider("secret", lookup=lookup)

    with pytest.raises(TravelRoutingError):
        asyncio.run(provider.get_travel_time(
            _point("A"), _point("B"), TransportMode.DRIVING
        ))
