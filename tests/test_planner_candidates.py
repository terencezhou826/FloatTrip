from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from app.catalog.loader import FileCatalogLoader
from app.planning.catalog_context import CatalogContextResolver
from app.planning.mandatory_spatial import MandatorySpatialResolver
from app.planning.nodes import make_planner_node, mandatory_check_node
from app.planning.planner_candidates import (
    PlannerCandidateReferenceError,
    build_planner_candidate_index,
    hydrate_planner_route,
    planner_candidate_ref,
)
from app.planning.schemas import (
    PlannerDayRoute,
    PlannerSpotSelection,
    PlannerTravelRoute,
    TravelPlanState,
)


CATALOG_ROOT = Path(__file__).resolve().parents[1] / "content" / "catalog"
PACKAGE_ID = "shanxi.changzhi"


def _provider_candidate(
    external_poi_id: str = "B0FFF49AFB",
    *,
    name: str = "发鸠山景区",
    anchor_id: str = "changzhi.anchor.fajiushan",
) -> dict:
    return {
        "provider": "amap",
        "external_poi_id": external_poi_id,
        "name": name,
        "location": {"lng": 112.640827, "lat": 36.146452},
        "region_name": "长子县",
        "address": "326省道附近",
        "curated_anchor_id": anchor_id,
        "is_mandatory": True,
        "spatial_identity_type": "provider_poi",
        "spatial_identity_id": f"binding.{external_poi_id}",
        "provenance_id": f"binding.{external_poi_id}",
        "cultural_anchor_location": {"lng": 112.640827, "lat": 36.146452},
        "navigation_location": {"lng": 112.640827, "lat": 36.146452},
        "navigation_name": name,
        "resolution_level": "exact_provider_poi",
        "placement_status": "exactly_placed",
        "cultural_identity": {
            "anchor_id": anchor_id,
            "anchor_name": name,
            "location": {"lng": 112.640827, "lat": 36.146452},
            "exact_location_available": True,
        },
        "navigation_identity": {
            "name": name,
            "location": {"lng": 112.640827, "lat": 36.146452},
            "identity_type": "provider_poi",
            "provider": "amap",
            "external_poi_id": external_poi_id,
        },
        "precision": "precise",
        "confidence": "high",
        "exact_anchor_location_available": True,
    }


def _selection(candidate_ref: str, *, name: str = "发鸠山景区") -> PlannerTravelRoute:
    return PlannerTravelRoute(
        reasoning="checked",
        days=[
            PlannerDayRoute(
                day=1,
                theme="theme",
                spots=[
                    PlannerSpotSelection(
                        candidate_ref=candidate_ref,
                        name=name,
                        period="morning",
                        start_time="09:00",
                        end_time="11:00",
                    )
                ],
            )
        ],
        notes="done",
        modification_concern="",
    )


def _only_spot(candidate: dict, *, selected_name: str | None = None) -> dict:
    candidate_ref = planner_candidate_ref(candidate)
    route = hydrate_planner_route(
        _selection(candidate_ref, name=selected_name or candidate["name"]),
        build_planner_candidate_index([candidate]),
    )
    return route.days[0].spots[0].model_dump(mode="json")


def _assert_all_objects_forbid_extra(node) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            assert node.get("additionalProperties") is False
        for value in node.values():
            _assert_all_objects_forbid_extra(value)
    elif isinstance(node, list):
        for value in node:
            _assert_all_objects_forbid_extra(value)


def test_planner_schema_is_recursively_strict_without_free_form_objects():
    schema = PlannerTravelRoute.model_json_schema()

    _assert_all_objects_forbid_extra(schema)
    assert schema["additionalProperties"] is False
    serialized = str(schema)
    assert "cultural_identity" not in serialized
    assert "navigation_reference" not in serialized


def test_provider_and_non_provider_candidate_refs():
    assert planner_candidate_ref(_provider_candidate()) == "poi:amap:B0FFF49AFB"
    locality = {
        **_provider_candidate("B0H1P64PGR"),
        "spatial_identity_type": "verified_locality",
        "spatial_identity_id": "changzhi.locality.tiantaishan.shanghao-village",
    }
    assert planner_candidate_ref(locality) == (
        "spatial:verified_locality:"
        "changzhi.locality.tiantaishan.shanghao-village"
    )


def test_legacy_candidate_ref_is_stable_and_not_name_only():
    candidate = {
        "name": "Legacy",
        "location": {"lng": 1.25, "lat": 2.5},
        "address": "Road 1",
        "adname": "District A",
    }
    reordered = {
        "adname": "District A",
        "address": "Road 1",
        "location": {"lat": 2.5, "lng": 1.25},
        "name": "Legacy",
    }

    assert planner_candidate_ref(candidate) == planner_candidate_ref(reordered)
    assert planner_candidate_ref(candidate).startswith("legacy:")
    assert planner_candidate_ref({**candidate, "address": "Road 2"}) != (
        planner_candidate_ref(candidate)
    )


def test_duplicate_candidate_ref_is_rejected():
    first = _provider_candidate()
    second = {**first, "name": "Conflicting Anchor"}

    with pytest.raises(PlannerCandidateReferenceError, match="Duplicate"):
        build_planner_candidate_index([first, second])


def test_unknown_ref_is_rejected_without_name_fallback():
    candidate = _provider_candidate()
    selection = _selection("poi:amap:UNKNOWN", name=candidate["name"])

    with pytest.raises(PlannerCandidateReferenceError, match="Unknown"):
        hydrate_planner_route(selection, build_planner_candidate_index([candidate]))


def test_name_mismatch_uses_canonical_candidate_name(caplog):
    candidate = _provider_candidate()
    with caplog.at_level(logging.WARNING, logger="app.planning.planner_candidates"):
        spot = _only_spot(candidate, selected_name="模型改写名称")

    assert spot["name"] == "发鸠山景区"
    assert "name mismatch" in caplog.text


def test_jingwei_provider_identity_is_restored_before_mandatory_check():
    candidate = _provider_candidate()
    spot = _only_spot(candidate)
    route = [{"day": 1, "theme": "theme", "spots": [spot]}]
    state = TravelPlanState(
        query="精卫线路",
        days=1,
        pois=[candidate],
        mandatory_pois=[candidate],
        mandatory_spatial_candidates=[candidate],
        route=route,
    )

    assert spot["provider"] == "amap"
    assert spot["external_poi_id"] == "B0FFF49AFB"
    assert spot["curated_anchor_id"] == "changzhi.anchor.fajiushan"
    assert spot["is_mandatory"] is True
    assert mandatory_check_node(state)["missing_mandatory_pois"] == []


def test_nuwa_locality_hydration_restores_disclosure_and_safety():
    repository = FileCatalogLoader(CATALOG_ROOT).load()
    context = CatalogContextResolver(repository).resolve(
        PACKAGE_ID, "changzhi.route.nuwa-tiantaishan"
    )
    candidate = asyncio.run(
        MandatorySpatialResolver(repository, {}).resolve(context)
    )[0].model_dump(mode="json")

    spot = _only_spot(candidate)

    assert spot["candidate_ref"] == (
        "spatial:verified_locality:"
        "changzhi.locality.tiantaishan.shanghao-village"
    )
    assert spot["resolution_level"] == "verified_locality"
    assert spot["placement_status"] == "locality_placed"
    assert spot["degraded"] is True
    assert spot["disclosure_required"] is True
    assert spot["navigation_name"] == "上郝村民委员会"
    assert spot["navigation_reference"]["external_poi_id"] == "B0H1P64PGR"
    assert spot["safety_constraints"]
    assert spot["exact_anchor_location_available"] is False
    assert spot["cultural_anchor_location"] is None


@pytest.mark.parametrize(
    ("external_poi_id", "name", "anchor_id"),
    [
        ("B016300684", "老顶山国家森林公园", "changzhi.anchor.laodingshan"),
        ("B0FFG79UY3", "屯留老爷山风景区", "changzhi.anchor.laoyeshan"),
    ],
)
def test_other_verified_provider_identities_hydrate_stably(
    external_poi_id, name, anchor_id
):
    candidate = _provider_candidate(
        external_poi_id, name=name, anchor_id=anchor_id
    )

    spot = _only_spot(candidate)

    assert spot["provider"] == "amap"
    assert spot["external_poi_id"] == external_poi_id
    assert spot["curated_anchor_id"] == anchor_id


def test_planner_revision_uses_compact_previous_route_and_rehydrates(monkeypatch):
    candidate = _provider_candidate()
    first_spot = _only_spot(candidate)
    captured = {}
    monkeypatch.setattr("app.planning.nodes.build_structured_llm", lambda *_a, **_k: object())

    async def fake_invoke(_llm, messages, **_kwargs):
        captured["prompt"] = str(messages)
        return _selection(planner_candidate_ref(candidate))

    monkeypatch.setattr("app.planning.nodes.ainvoke_structured", fake_invoke)
    state = TravelPlanState(
        query="修改路线",
        destination="长治市",
        days=1,
        pois=[candidate],
        mandatory_pois=[candidate],
        mandatory_spatial_candidates=[candidate],
        route=[{"day": 1, "theme": "old", "spots": [first_spot]}],
        route_modify_opinion="保留地点，调整时间",
    )

    result = asyncio.run(make_planner_node(None)(state))

    assert result["route"][0]["spots"][0]["external_poi_id"] == "B0FFF49AFB"
    assert planner_candidate_ref(candidate) in captured["prompt"]
    assert "exact_location_available" not in captured["prompt"]


def test_planner_unknown_ref_gets_one_bounded_ref_only_correction(monkeypatch):
    candidate = _provider_candidate()
    calls = []
    monkeypatch.setattr("app.planning.nodes.build_structured_llm", lambda *_a, **_k: object())

    async def fake_invoke(_llm, messages, **_kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return _selection("poi:amap:UNKNOWN", name=candidate["name"])
        return _selection(planner_candidate_ref(candidate))

    monkeypatch.setattr("app.planning.nodes.ainvoke_structured", fake_invoke)
    state = TravelPlanState(
        query="精卫线路",
        destination="长治市",
        days=1,
        pois=[candidate],
        mandatory_pois=[candidate],
        mandatory_spatial_candidates=[candidate],
    )

    result = asyncio.run(make_planner_node(None)(state))

    assert len(calls) == 2
    assert result["route"][0]["spots"][0]["external_poi_id"] == "B0FFF49AFB"
    correction = str(calls[1][-1])
    assert planner_candidate_ref(candidate) in correction
    assert "不得按名称猜测" in correction
