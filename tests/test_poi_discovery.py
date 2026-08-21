from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.catalog.discovery import (
    AnchorPoiDiscovery,
    AnchorPoiDiscoveryError,
    ExternalPoiCandidate,
)
from app.catalog.models import Anchor, PoiProvider, Region, RegionType
from app.catalog.repository import InMemoryCatalogRepository
from app.providers.amap.discovery import AmapPoiDiscoveryProvider


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _repository() -> InMemoryCatalogRepository:
    return InMemoryCatalogRepository(
        regions=(
            Region(
                id="sample.province",
                name="Sample Province",
                region_type=RegionType.PROVINCE,
            ),
            Region(
                id="sample.province.city",
                name="Sample City",
                parent_id="sample.province",
                region_type=RegionType.PREFECTURE_CITY,
            ),
            Region(
                id="sample.province.city.county",
                name="Sample County",
                parent_id="sample.province.city",
                region_type=RegionType.COUNTY,
            ),
        ),
        themes=(),
        routes=(),
        anchors=(
            Anchor(
                id="sample.anchor.mountain",
                name="Sample Mountain",
                region_id="sample.province.city.county",
            ),
        ),
        manifests=(),
    )


class FakeDiscoveryProvider:
    provider = PoiProvider.CUSTOM

    def __init__(self):
        self.query = None

    def search_candidates(self, query):
        self.query = query
        return (
            ExternalPoiCandidate(
                provider=self.provider,
                external_poi_id="custom-1",
                name="A differently named provider result",
            ),
        )


def test_discovery_uses_anchor_and_complete_region_path_without_persisting():
    repository = _repository()
    provider = FakeDiscoveryProvider()

    candidates = AnchorPoiDiscovery(repository).discover(
        "sample.anchor.mountain", provider
    )

    assert candidates[0].external_poi_id == "custom-1"
    assert provider.query.anchor_name == "Sample Mountain"
    assert [item.id for item in provider.query.region_path] == [
        "sample.province",
        "sample.province.city",
        "sample.province.city.county",
    ]
    assert repository.list_poi_bindings() == ()


def test_missing_anchor_is_rejected_before_provider_call():
    provider = FakeDiscoveryProvider()

    with pytest.raises(AnchorPoiDiscoveryError, match="anchor .* not found"):
        AnchorPoiDiscovery(_repository()).discover("missing.anchor", provider)

    assert provider.query is None


def test_amap_adapter_maps_provider_identity_and_review_fields():
    captured = {}

    def fake_search(city, api_key, *, keywords, types, offset):
        captured.update(
            city=city,
            api_key=api_key,
            keywords=keywords,
            types=types,
            offset=offset,
        )
        return [
            {
                "id": "B0SAMPLE",
                "name": "Provider Mountain Result",
                "address": ["Road", "Number 1"],
                "adcode": "sample-adcode",
                "location": "112.1001,36.2002",
                "type": "Scenic",
                "typecode": "110000",
                "pname": "Sample Province",
                "cityname": "Sample City",
                "adname": "Sample County",
                "tel": "sample-tel",
            },
            {"name": "Result without stable id"},
        ]

    provider = AmapPoiDiscoveryProvider("test-key", search=fake_search)

    candidates = AnchorPoiDiscovery(_repository()).discover(
        "sample.anchor.mountain", provider
    )

    assert captured == {
        "city": "Sample City",
        "api_key": "test-key",
        "keywords": "Sample Mountain",
        "types": "风景名胜",
        "offset": 10,
    }
    assert len(candidates) == 1
    assert candidates[0].model_dump(mode="json") == {
        "provider": "amap",
        "external_poi_id": "B0SAMPLE",
        "name": "Provider Mountain Result",
        "address": "Road Number 1",
        "provider_region_code": "sample-adcode",
        "location": {"lng": 112.1001, "lat": 36.2002},
        "raw_fields": {
            "type": "Scenic",
            "typecode": "110000",
            "pname": "Sample Province",
            "cityname": "Sample City",
            "adname": "Sample County",
            "tel": "sample-tel",
        },
    }


def test_discovery_python_has_no_regional_or_route_special_cases():
    prohibited = {"changzhi", "jingwei", "fajiushan", "mythology"}
    found = set()

    for relative in (
        "app/catalog/discovery.py",
        "app/providers/amap/discovery.py",
    ):
        tree = ast.parse((PROJECT_ROOT / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for token in prohibited:
                    if token in node.value.casefold():
                        found.add((relative, token))

    assert not found
