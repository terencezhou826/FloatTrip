from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import PoiProvider
from app.planning.catalog_context import CatalogContextResolver
from app.planning.graph import (
    build_graph,
    build_modification_graph,
    build_runtime_revision_graph,
)
from app.planning.mandatory_pois import (
    MandatoryConstraintUnsatisfied,
    MandatoryPoiResolver,
    merge_poi_candidates,
)
from app.planning.nodes import (
    attraction_search_node,
    finalize_node,
    make_planner_node,
    make_reviewer_node,
    make_time_check_node,
    mandatory_check_node,
    route_after_mandatory_check,
)
from app.planning.runtime_worker import snapshot_to_state
from app.planning.schemas import (
    DayRoute,
    RouteReview,
    SpotPlan,
    TimeCheckResult,
    TravelPlanState,
    TravelRoute,
)
from app.providers.poi_identity import ExternalPoiRecord


CATALOG_ROOT = Path(__file__).resolve().parents[1] / "content" / "catalog"
PACKAGE_ID = "shanxi.changzhi"
ROUTE_ID = "changzhi.route.jingwei-fajiushan"
ANCHOR_ID = "changzhi.anchor.fajiushan"
EXTERNAL_POI_ID = "B0FFF49AFB"


def _mandatory() -> dict:
    return {
        "provider": "amap",
        "external_poi_id": EXTERNAL_POI_ID,
        "name": "发鸠山景区",
        "location": {"lng": 112.640827, "lat": 36.146452},
        "rating": 4.7,
        "open_time": "08:00-18:00",
        "photo": None,
        "region_name": "长子县",
        "address": "326省道附近",
        "tel": None,
        "cost": None,
        "binding_id": "changzhi.binding.fajiushan.amap",
        "curated_anchor_id": ANCHOR_ID,
        "is_mandatory": True,
    }


def _route(*, include_mandatory: bool = True) -> list[dict]:
    identity = (
        {
            "provider": "amap",
            "external_poi_id": EXTERNAL_POI_ID,
            "curated_anchor_id": ANCHOR_ID,
            "is_mandatory": True,
        }
        if include_mandatory
        else {}
    )
    return [{
        "day": 1,
        "theme": "route",
        "spots": [{
            "name": "发鸠山景区" if include_mandatory else "Ordinary",
            "period": "morning",
            "start_time": "09:00",
            "end_time": "11:00",
            **identity,
        }],
    }]


def _state(**updates) -> TravelPlanState:
    values = {
        "query": "one day trip",
        "destination": "destination",
        "days": 1,
        "pois": [_mandatory()],
        "mandatory_pois": [_mandatory()],
        "route": _route(),
    }
    values.update(updates)
    return TravelPlanState(**values)


def test_ordinary_attraction_pool_is_unchanged_without_catalog_context(monkeypatch):
    ordinary = [{"name": "Ordinary", "rating": 4.8, "location": {"lng": 1, "lat": 2}}]

    async def fake_fetch(*_args, **_kwargs):
        return ordinary

    monkeypatch.setattr("app.planning.nodes.amap_key", lambda: "key")
    monkeypatch.setattr("app.planning.nodes.fetch_city_spots_async", fake_fetch)

    result = asyncio.run(attraction_search_node(_state(pois=[], mandatory_pois=[], route=[])))

    assert result["pois"] == ordinary
    assert result["mandatory_pois"] == []


def test_mandatory_candidate_is_injected_and_identity_deduplicated(monkeypatch):
    context = CatalogContextResolver(FileCatalogLoader(CATALOG_ROOT).load()).resolve(
        PACKAGE_ID, ROUTE_ID
    )
    ordinary = [{**_mandatory(), "rating": 4.9, "is_mandatory": False}]

    async def fake_fetch(*_args, **_kwargs):
        return ordinary

    async def fake_resolve(_context, _api_key):
        return [_mandatory()]

    monkeypatch.setattr("app.planning.nodes.amap_key", lambda: "key")
    monkeypatch.setattr("app.planning.nodes.fetch_city_spots_async", fake_fetch)
    monkeypatch.setattr(
        "app.planning.nodes._resolve_mandatory_pois_for_planning", fake_resolve
    )

    result = asyncio.run(
        attraction_search_node(
            _state(catalog_context=context, pois=[], mandatory_pois=[], route=[])
        )
    )

    assert len(result["pois"]) == 1
    assert result["pois"][0]["external_poi_id"] == EXTERNAL_POI_ID
    assert result["pois"][0]["is_mandatory"] is True


def test_planner_prompt_carries_constraint_and_output_identity(monkeypatch):
    captured = {}
    monkeypatch.setattr("app.planning.nodes.build_structured_llm", lambda *_a, **_k: object())

    async def fake_invoke(_llm, messages, **_kwargs):
        captured["messages"] = messages
        return TravelRoute(
            reasoning="kept mandatory identity",
            days=[DayRoute(
                day=1,
                theme="route",
                spots=[SpotPlan(**_route()[0]["spots"][0])],
            )],
            notes="done",
        )

    monkeypatch.setattr("app.planning.nodes.ainvoke_structured", fake_invoke)

    result = asyncio.run(make_planner_node(None)(_state(route=[])))

    assert result["route"][0]["spots"][0]["external_poi_id"] == EXTERNAL_POI_ID
    prompt = str(captured["messages"])
    assert "mandatory POI" in prompt
    assert EXTERNAL_POI_ID in prompt


def test_deterministic_check_rejects_then_accepts_correction():
    rejected = mandatory_check_node(_state(route=_route(include_mandatory=False)))
    assert rejected["approved"] is False
    assert rejected["missing_mandatory_pois"][0]["external_poi_id"] == EXTERNAL_POI_ID

    corrected_state = _state(**rejected, route=_route())
    accepted = mandatory_check_node(corrected_state)
    assert accepted["missing_mandatory_pois"] == []
    assert accepted["mandatory_check_round"] == 0


def test_deterministic_check_fails_after_max_rounds():
    state = _state(
        route=_route(include_mandatory=False),
        mandatory_check_round=3,
        max_mandatory_check_rounds=3,
    )
    with pytest.raises(MandatoryConstraintUnsatisfied, match="constraint unsatisfied"):
        mandatory_check_node(state)


def test_reviewer_cannot_approve_or_recommend_removing_missing_mandatory(monkeypatch):
    captured = {}
    monkeypatch.setattr("app.planning.nodes.build_structured_llm", lambda *_a, **_k: object())

    async def fake_invoke(_llm, messages, **_kwargs):
        captured["messages"] = messages
        return RouteReview(
            reasoning="all ordinary checks pass",
            approved=True,
            score=100,
            route_modify_opinion="",
            issues=[],
        )

    monkeypatch.setattr("app.planning.nodes.ainvoke_structured", fake_invoke)
    result = asyncio.run(
        make_reviewer_node(None)(_state(route=_route(include_mandatory=False)))
    )

    assert result["approved"] is False
    assert "mandatory POI" in result["route_modify_opinion"]
    assert "不得建议删除" in str(captured["messages"])


def test_time_check_still_processes_mandatory_poi(monkeypatch):
    captured = {}
    monkeypatch.setattr("app.planning.nodes.build_structured_llm", lambda *_a, **_k: object())

    async def fake_invoke(_llm, messages, **_kwargs):
        captured["messages"] = messages
        return TimeCheckResult(reasoning="checked", violations=[])

    monkeypatch.setattr("app.planning.nodes.ainvoke_structured", fake_invoke)
    result = asyncio.run(make_time_check_node(None)(_state()))

    assert result["time_violations"] == []
    assert "发鸠山景区" in str(captured["messages"])


def test_time_check_correction_cannot_delete_mandatory_identity():
    state = _state(
        route=_route(include_mandatory=False),
        time_check_done=True,
    )
    rejected = mandatory_check_node(state)
    rejected_state = state.model_copy(update=rejected)
    assert route_after_mandatory_check(rejected_state) == "planner"

    corrected_state = rejected_state.model_copy(update={"route": _route()})
    accepted_state = corrected_state.model_copy(
        update=mandatory_check_node(corrected_state)
    )
    assert route_after_mandatory_check(accepted_state) == "time_check"


def test_finalize_uses_provider_identity_before_same_name_fallback():
    first = {**_mandatory(), "external_poi_id": "OTHER", "rating": 1.0}
    second = {**_mandatory(), "rating": 4.9}
    state = _state(pois=[first, second])

    attraction = finalize_node(state)["final_plan"]["days"][0]["timeline"][0]

    assert attraction["external_poi_id"] == EXTERNAL_POI_ID
    assert attraction["rating"] == 4.9
    assert attraction["is_mandatory"] is True


def test_checkpoint_projection_preserves_mandatory_identity():
    restored = snapshot_to_state(_state().model_dump(mode="json"))

    assert restored.mandatory_pois[0]["external_poi_id"] == EXTERNAL_POI_ID
    assert restored.route[0]["spots"][0]["curated_anchor_id"] == ANCHOR_ID


def test_all_planner_graphs_route_through_internal_mandatory_check(monkeypatch):
    monkeypatch.setattr("app.planning.nodes.build_structured_llm", lambda *_a, **_k: object())

    graphs = [build_graph(), build_modification_graph(), build_runtime_revision_graph()]

    for graph in graphs:
        edges = {(edge.source, edge.target) for edge in graph.get_graph().edges}
        assert ("planner", "mandatory_check") in edges


def test_jingwei_context_to_binding_to_planner_identity(monkeypatch):
    catalog = FileCatalogLoader(CATALOG_ROOT).load()
    context = CatalogContextResolver(catalog).resolve(PACKAGE_ID, ROUTE_ID)

    class FakeProvider:
        provider = PoiProvider.AMAP

        async def get_poi(self, external_poi_id):
            return ExternalPoiRecord(
                provider=self.provider,
                external_poi_id=external_poi_id,
                name="发鸠山景区",
                location={"lng": 112.640827, "lat": 36.146452},
            )

    resolved = asyncio.run(
        MandatoryPoiResolver(catalog, {PoiProvider.AMAP: FakeProvider()}).resolve(context)
    )
    pool = merge_poi_candidates([], resolved)
    route = _route()

    assert pool[0]["curated_anchor_id"] == ANCHOR_ID
    assert mandatory_check_node(_state(pois=pool, mandatory_pois=pool, route=route))[
        "missing_mandatory_pois"
    ] == []
