from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    ExternalPoiBinding,
    PoiProvider,
    PoiVerificationMethod,
    PoiVerificationStatus,
)
from app.catalog.repository import InMemoryCatalogRepository
from app.planning.catalog_context import CatalogContext, CatalogContextResolver
from app.planning.mandatory_pois import (
    MandatoryPoiResolutionError,
    MandatoryPoiResolver,
    merge_poi_candidates,
    missing_mandatory_pois,
)
from app.providers.amap.identity import AmapExactPoiProvider
from app.providers.amap.poi import get_poi_by_id_async
from app.providers.poi_identity import ExternalPoiRecord


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
PACKAGE_ID = "shanxi.changzhi"
ROUTE_ID = "changzhi.route.jingwei-fajiushan"
ANCHOR_ID = "changzhi.anchor.fajiushan"
EXTERNAL_POI_ID = "B0FFF49AFB"


@pytest.fixture
def catalog():
    return FileCatalogLoader(CATALOG_ROOT).load()


@pytest.fixture
def context(catalog):
    return CatalogContextResolver(catalog).resolve(PACKAGE_ID, ROUTE_ID)


def _binding(
    binding_id: str = "binding.test",
    *,
    anchor_id: str = ANCHOR_ID,
    provider: PoiProvider = PoiProvider.AMAP,
    external_poi_id: str = EXTERNAL_POI_ID,
    status: PoiVerificationStatus = PoiVerificationStatus.VERIFIED,
) -> ExternalPoiBinding:
    payload = {
        "binding_id": binding_id,
        "anchor_id": anchor_id,
        "provider": provider,
        "external_poi_id": external_poi_id,
        "external_name": "Provider place",
        "verification_status": status,
    }
    if status is PoiVerificationStatus.VERIFIED:
        payload.update(
            verification_method=PoiVerificationMethod.MANUAL_REVIEW,
            verified_at="2026-08-21T20:00:00+08:00",
        )
    return ExternalPoiBinding.model_validate(payload)


def _repository_with_bindings(catalog, bindings) -> InMemoryCatalogRepository:
    package = catalog.get_package(PACKAGE_ID)
    package = package.model_copy(update={"poi_bindings": list(bindings)})
    return InMemoryCatalogRepository(
        regions=catalog.list_regions(),
        themes=package.themes,
        routes=package.routes,
        anchors=package.anchors,
        manifests=(package.manifest,),
        poi_bindings=package.poi_bindings,
        packages=(package,),
    )


def _record(
    *,
    provider: PoiProvider = PoiProvider.AMAP,
    external_poi_id: str = EXTERNAL_POI_ID,
    name: str = "Provider place",
) -> ExternalPoiRecord:
    return ExternalPoiRecord(
        provider=provider,
        external_poi_id=external_poi_id,
        name=name,
        location={"lng": 112.640827, "lat": 36.146452},
        address="Provider address",
        region_name="Sample District",
    )


class FakeExactProvider:
    provider = PoiProvider.AMAP

    def __init__(self, record=None, error: Exception | None = None):
        self.record = record or _record()
        self.error = error
        self.requested_ids: list[str] = []

    async def get_poi(self, external_poi_id: str) -> ExternalPoiRecord:
        self.requested_ids.append(external_poi_id)
        if self.error:
            raise self.error
        return self.record


def test_formal_fajiushan_binding_is_unique_verified_amap(catalog):
    bindings = catalog.list_verified_bindings_for_anchor(ANCHOR_ID)

    assert len(bindings) == 1
    binding = bindings[0]
    assert binding.provider is PoiProvider.AMAP
    assert binding.external_poi_id == EXTERNAL_POI_ID
    assert binding.verification_method is PoiVerificationMethod.MANUAL_REVIEW
    assert binding.verified_at is not None
    assert binding.verification_note


def test_changzhi_provider_bindings_match_current_spatial_rollout(catalog):
    package = catalog.get_package(PACKAGE_ID)
    other_anchor_ids = {item.id for item in package.anchors} - {ANCHOR_ID}

    assert len(other_anchor_ids) == 3
    assert not catalog.list_verified_bindings_for_anchor(
        "changzhi.anchor.tiantaishan"
    )
    for anchor_id in (
        "changzhi.anchor.laodingshan",
        "changzhi.anchor.laoyeshan",
    ):
        bindings = catalog.list_verified_bindings_for_anchor(anchor_id)
        assert len(bindings) == 1
        assert bindings[0].provider is PoiProvider.AMAP


def test_verified_binding_resolves_exact_provider_identity(catalog, context):
    repository = _repository_with_bindings(catalog, [_binding()])
    provider = FakeExactProvider()

    resolved = asyncio.run(
        MandatoryPoiResolver(
            repository, {PoiProvider.AMAP: provider}
        ).resolve(context)
    )

    assert provider.requested_ids == [EXTERNAL_POI_ID]
    assert len(resolved) == 1
    assert resolved[0].curated_anchor_id == ANCHOR_ID
    assert resolved[0].provider is PoiProvider.AMAP
    assert resolved[0].external_poi_id == EXTERNAL_POI_ID
    assert resolved[0].is_mandatory is True


@pytest.mark.parametrize(
    "status",
    [PoiVerificationStatus.CANDIDATE, PoiVerificationStatus.REJECTED],
)
def test_non_verified_binding_is_not_runtime_eligible(catalog, context, status):
    repository = _repository_with_bindings(
        catalog, [_binding(status=status)]
    )

    with pytest.raises(MandatoryPoiResolutionError, match="verified binding"):
        asyncio.run(
            MandatoryPoiResolver(
                repository, {PoiProvider.AMAP: FakeExactProvider()}
            ).resolve(context)
        )


def test_missing_verified_binding_fails_without_name_search(catalog, context):
    repository = _repository_with_bindings(catalog, [])
    provider = FakeExactProvider()

    with pytest.raises(MandatoryPoiResolutionError, match="verified binding"):
        asyncio.run(
            MandatoryPoiResolver(
                repository, {PoiProvider.AMAP: provider}
            ).resolve(context)
        )

    assert provider.requested_ids == []


def test_unsupported_verified_provider_fails(catalog, context):
    repository = _repository_with_bindings(
        catalog, [_binding(provider=PoiProvider.BAIDU)]
    )

    with pytest.raises(MandatoryPoiResolutionError, match="unsupported provider"):
        asyncio.run(MandatoryPoiResolver(repository, {}).resolve(context))


def test_provider_lookup_error_is_explicit(catalog, context):
    repository = _repository_with_bindings(catalog, [_binding()])
    provider = FakeExactProvider(error=RuntimeError("provider unavailable"))

    with pytest.raises(MandatoryPoiResolutionError, match="provider lookup failed"):
        asyncio.run(
            MandatoryPoiResolver(
                repository, {PoiProvider.AMAP: provider}
            ).resolve(context)
        )


def test_provider_returned_identity_mismatch_fails(catalog, context):
    repository = _repository_with_bindings(catalog, [_binding()])
    provider = FakeExactProvider(record=_record(external_poi_id="OTHER-ID"))

    with pytest.raises(MandatoryPoiResolutionError, match="identity mismatch"):
        asyncio.run(
            MandatoryPoiResolver(
                repository, {PoiProvider.AMAP: provider}
            ).resolve(context)
        )


def test_multiple_verified_bindings_for_anchor_are_ambiguous(catalog, context):
    repository = _repository_with_bindings(
        catalog,
        [
            _binding("binding.first"),
            _binding("binding.second", external_poi_id="SECOND-ID"),
        ],
    )
    provider = FakeExactProvider()

    with pytest.raises(MandatoryPoiResolutionError, match="multiple verified"):
        asyncio.run(
            MandatoryPoiResolver(
                repository, {PoiProvider.AMAP: provider}
            ).resolve(context)
        )

    assert provider.requested_ids == []


def test_no_catalog_context_skips_resolution(catalog):
    provider = FakeExactProvider()

    resolved = asyncio.run(
        MandatoryPoiResolver(
            catalog, {PoiProvider.AMAP: provider}
        ).resolve(None)
    )

    assert resolved == ()
    assert provider.requested_ids == []


def test_catalog_context_with_no_mandatory_anchors_skips_resolution(
    catalog, context
):
    empty_context = context.model_copy(update={"mandatory_anchor_ids": ()})
    provider = FakeExactProvider()

    resolved = asyncio.run(
        MandatoryPoiResolver(
            catalog, {PoiProvider.AMAP: provider}
        ).resolve(empty_context)
    )

    assert resolved == ()
    assert provider.requested_ids == []


def test_candidate_merge_deduplicates_by_provider_identity():
    ordinary = [
        {
            "provider": "amap",
            "external_poi_id": EXTERNAL_POI_ID,
            "name": "Ordinary result name",
            "rating": 4.8,
            "location": {"lng": 1.0, "lat": 2.0},
        }
    ]
    mandatory = [
        {
            **_record(name="Exact provider name").model_dump(mode="json"),
            "curated_anchor_id": ANCHOR_ID,
            "is_mandatory": True,
        }
    ]

    merged = merge_poi_candidates(ordinary, mandatory)

    assert len(merged) == 1
    assert merged[0]["name"] == "Exact provider name"
    assert merged[0]["rating"] == 4.8
    assert merged[0]["curated_anchor_id"] == ANCHOR_ID
    assert merged[0]["is_mandatory"] is True


def test_candidate_merge_does_not_deduplicate_by_name():
    ordinary = [
        {
            "provider": "amap",
            "external_poi_id": "FIRST-ID",
            "name": "Same display name",
        }
    ]
    mandatory = [
        {
            **_record(
                external_poi_id="SECOND-ID", name="Same display name"
            ).model_dump(mode="json"),
            "curated_anchor_id": ANCHOR_ID,
            "is_mandatory": True,
        }
    ]

    merged = merge_poi_candidates(ordinary, mandatory)

    assert len(merged) == 2


def test_candidate_merge_without_mandatory_pois_preserves_ordinary_pool():
    ordinary = [{"name": "Ordinary", "rating": 4.8}]

    assert merge_poi_candidates(ordinary, []) == ordinary


def test_mandatory_validator_uses_provider_identity_not_name():
    mandatory = [
        {
            **_record().model_dump(mode="json"),
            "curated_anchor_id": ANCHOR_ID,
            "is_mandatory": True,
        }
    ]
    wrong_identity_route = [
        {
            "day": 1,
            "spots": [
                {
                    "name": "Provider place",
                    "provider": "amap",
                    "external_poi_id": "OTHER-ID",
                }
            ],
        }
    ]
    correct_identity_route = [
        {
            "day": 1,
            "spots": [
                {
                    "name": "Different display name",
                    "provider": "amap",
                    "external_poi_id": EXTERNAL_POI_ID,
                }
            ],
        }
    ]

    assert len(missing_mandatory_pois(wrong_identity_route, mandatory)) == 1
    assert missing_mandatory_pois(correct_identity_route, mandatory) == []


def test_amap_exact_adapter_maps_detail_response_without_keyword_search():
    captured = {}

    async def fake_lookup(external_poi_id, api_key):
        captured.update(external_poi_id=external_poi_id, api_key=api_key)
        return [
            {
                "id": external_poi_id,
                "name": "Exact provider place",
                "location": "112.640827,36.146452",
                "address": "Provider address",
                "adname": "Sample District",
                "biz_ext": {"rating": "4.7", "opentime": "08:00-18:00"},
            }
        ]

    record = asyncio.run(
        AmapExactPoiProvider("test-key", lookup=fake_lookup).get_poi(
            EXTERNAL_POI_ID
        )
    )

    assert captured == {
        "external_poi_id": EXTERNAL_POI_ID,
        "api_key": "test-key",
    }
    assert record.provider is PoiProvider.AMAP
    assert record.external_poi_id == EXTERNAL_POI_ID
    assert record.name == "Exact provider place"
    assert record.rating == 4.7


def test_amap_exact_adapter_rejects_missing_or_multiple_results():
    async def no_results(_external_poi_id, _api_key):
        return []

    async def multiple_results(external_poi_id, _api_key):
        return [
            {"id": external_poi_id, "name": "One"},
            {"id": external_poi_id, "name": "Two"},
        ]

    with pytest.raises(RuntimeError, match="exactly one"):
        asyncio.run(
            AmapExactPoiProvider("test-key", lookup=no_results).get_poi(
                EXTERNAL_POI_ID
            )
        )
    with pytest.raises(RuntimeError, match="exactly one"):
        asyncio.run(
            AmapExactPoiProvider("test-key", lookup=multiple_results).get_poi(
                EXTERNAL_POI_ID
            )
        )


def test_amap_exact_lookup_uses_detail_id_without_keyword_search(monkeypatch):
    captured = {}

    async def fake_get(url):
        captured["url"] = url
        return {"status": "1", "pois": [{"id": EXTERNAL_POI_ID}]}

    monkeypatch.setattr("app.providers.amap.poi.http_get_json_async", fake_get)

    results = asyncio.run(get_poi_by_id_async(EXTERNAL_POI_ID, "secret-key"))

    parsed = urlparse(captured["url"])
    query = parse_qs(parsed.query)
    assert parsed.path == "/v3/place/detail"
    assert query["id"] == [EXTERNAL_POI_ID]
    assert "keywords" not in query
    assert results == [{"id": EXTERNAL_POI_ID}]
