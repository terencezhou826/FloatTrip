from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.catalog.models import (
    CommercialRelationship,
    PoiProvider,
    PriceStatus,
    ResourceVerificationStatus,
)
from app.providers.amap.resources import (
    AmapRuntimeResourceProvider,
    normalize_amap_restaurants,
)
from app.resources import (
    FreshnessStatus,
    ResourceDiscoveryService,
    ResourceProvenanceType,
    classify_freshness,
)


RETRIEVED_AT = datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc)


def _raw(
    external_id: str = "B-TEST-1",
    *,
    name: str = "Synthetic Restaurant Fixture",
    location: str = "112.900000,36.100000",
    cost: str = "",
    open_time: str = "",
) -> dict:
    return {
        "id": external_id,
        "name": name,
        "location": location,
        "address": "Provider supplied test address",
        "pname": "山西省",
        "cityname": "长治市",
        "adname": "长子县",
        "adcode": "TEST-ADCODE",
        "type": "餐饮服务;中餐厅",
        "typecode": "050100",
        "distance": "1200",
        "biz_ext": {
            "rating": "4.6",
            "cost": cost,
            "opentime2": open_time,
            "comment_num": "25",
        },
    }


def test_provider_candidate_normalization_preserves_identity():
    candidate = normalize_amap_restaurants(
        [_raw()], retrieved_at=RETRIEVED_AT
    )[0]
    assert candidate.provider is PoiProvider.AMAP
    assert candidate.external_poi_id == "B-TEST-1"
    assert candidate.identity == (PoiProvider.AMAP, "B-TEST-1")
    assert candidate.runtime_resource_id.startswith("runtime-resource.amap.")


def test_runtime_candidate_remains_candidate_not_verified():
    candidate = normalize_amap_restaurants(
        [_raw()], retrieved_at=RETRIEVED_AT
    )[0]
    assert candidate.verification_status is ResourceVerificationStatus.CANDIDATE
    assert candidate.provenance_type is ResourceProvenanceType.RUNTIME_PROVIDER


def test_provider_provenance_is_complete():
    candidate = normalize_amap_restaurants(
        [_raw()], retrieved_at=RETRIEVED_AT
    )[0]
    assert candidate.provider_source == "amap.place.around.v3"
    assert candidate.retrieved_at == RETRIEVED_AT
    assert candidate.freshness_status is FreshnessStatus.FRESH


def test_missing_identity_is_not_normalized():
    payload = _raw()
    payload["id"] = ""
    assert normalize_amap_restaurants([payload], retrieved_at=RETRIEVED_AT) == ()


def test_missing_name_is_not_normalized():
    payload = _raw()
    payload["name"] = ""
    assert normalize_amap_restaurants([payload], retrieved_at=RETRIEVED_AT) == ()


def test_missing_coordinates_is_not_normalized():
    assert normalize_amap_restaurants(
        [_raw(location="")], retrieved_at=RETRIEVED_AT
    ) == ()


def test_duplicate_provider_id_is_deduplicated():
    async def search(*args, **kwargs):
        return [_raw(), _raw()]

    provider = AmapRuntimeResourceProvider(
        "test-key", search=search, clock=lambda: RETRIEVED_AT
    )
    candidates = asyncio.run(
        ResourceDiscoveryService(provider).discover_restaurants(
            {"lng": 112.9, "lat": 36.1}
        )
    )
    assert len(candidates) == 1


def test_same_name_with_different_provider_ids_is_preserved():
    async def search(*args, **kwargs):
        return [_raw("B-TEST-1"), _raw("B-TEST-2")]

    provider = AmapRuntimeResourceProvider(
        "test-key", search=search, clock=lambda: RETRIEVED_AT
    )
    candidates = asyncio.run(
        ResourceDiscoveryService(provider).discover_restaurants(
            {"lng": 112.9, "lat": 36.1}
        )
    )
    assert {item.external_poi_id for item in candidates} == {
        "B-TEST-1", "B-TEST-2"
    }


def test_amap_adapter_uses_existing_around_search_contract():
    captured = {}

    async def search(location, key, **kwargs):
        captured.update(location=location, key=key, **kwargs)
        return [_raw()]

    provider = AmapRuntimeResourceProvider(
        "test-key", search=search, clock=lambda: RETRIEVED_AT
    )
    asyncio.run(
        provider.discover_restaurants(
            {"lng": 112.9, "lat": 36.1}, radius_m=4000, limit=12
        )
    )
    assert captured == {
        "location": {"lng": 112.9, "lat": 36.1},
        "key": "test-key",
        "types": "餐饮服务",
        "radius": 4000,
        "offset": 12,
    }


def test_price_absence_remains_unknown():
    price = normalize_amap_restaurants(
        [_raw(cost="")], retrieved_at=RETRIEVED_AT
    )[0].price_info
    assert price.price_status is PriceStatus.UNKNOWN
    assert price.amount is None
    assert price.provider is None


def test_provider_reported_cost_has_price_provenance():
    price = normalize_amap_restaurants(
        [_raw(cost="38")], retrieved_at=RETRIEVED_AT
    )[0].price_info
    assert price.price_status is PriceStatus.PER_PERSON
    assert price.amount == 38
    assert price.provider is PoiProvider.AMAP
    assert price.source_field == "amap.biz_ext.cost"
    assert price.retrieved_at == RETRIEVED_AT


def test_invalid_provider_cost_does_not_become_a_price():
    price = normalize_amap_restaurants(
        [_raw(cost="price unavailable")], retrieved_at=RETRIEVED_AT
    )[0].price_info
    assert price.price_status is PriceStatus.UNKNOWN


def test_provider_business_hours_are_sourced_but_not_open_status():
    candidate = normalize_amap_restaurants(
        [_raw(open_time="Provider reported hours")], retrieved_at=RETRIEVED_AT
    )[0]
    assert candidate.business_hours.provider is PoiProvider.AMAP
    assert candidate.business_hours.retrieved_at == RETRIEVED_AT
    assert candidate.operational_status.value == "unknown"


def test_freshness_classification_is_explicit():
    assert classify_freshness(
        RETRIEVED_AT,
        as_of=RETRIEVED_AT + timedelta(hours=12),
        max_age=timedelta(days=1),
    ) is FreshnessStatus.FRESH
    assert classify_freshness(
        RETRIEVED_AT,
        as_of=RETRIEVED_AT + timedelta(days=2),
        max_age=timedelta(days=1),
    ) is FreshnessStatus.STALE
    assert classify_freshness(
        None,
        as_of=RETRIEVED_AT,
        max_age=timedelta(days=1),
    ) is FreshnessStatus.UNKNOWN


def test_runtime_candidate_has_no_invented_commercial_relationship():
    candidate = normalize_amap_restaurants(
        [_raw()], retrieved_at=RETRIEVED_AT
    )[0]
    assert candidate.commercial_relationship is CommercialRelationship.UNKNOWN


def test_normalization_is_deterministic_for_same_provider_identity():
    first = normalize_amap_restaurants([_raw()], retrieved_at=RETRIEVED_AT)[0]
    second = normalize_amap_restaurants([_raw()], retrieved_at=RETRIEVED_AT)[0]
    assert first.runtime_resource_id == second.runtime_resource_id
    assert first == second
