from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    AnchorCoordinateIdentity,
    ExternalPoiBinding,
    NavigationAccessPoint,
    PoiProvider,
)
from app.catalog.repository import InMemoryCatalogRepository
from app.planning.catalog_context import CatalogContextResolver
from app.planning.mandatory_pois import MandatoryPoiResolutionError
from app.planning.mandatory_spatial import (
    MandatorySpatialResolver,
    merge_spatial_candidates,
    missing_mandatory_spatial_candidates,
)
from app.planning.route_feasibility import TravelTimeMatrix
from app.planning.schemas import TravelPlanState
from app.providers.poi_identity import ExternalPoiRecord
from app.providers.travel_time import (
    TransportMode,
    TravelLeg,
    TravelPoint,
)


CATALOG_ROOT = Path(__file__).resolve().parents[1] / "content" / "catalog"
PACKAGE_ID = "shanxi.changzhi"
ROUTE_ID = "changzhi.route.jingwei-fajiushan"
ANCHOR_ID = "changzhi.anchor.fajiushan"


def _provenance() -> dict:
    return {
        "provenance_id": "spatial.provenance.runtime-test",
        "verification_method": "field_survey",
        "verified_at": "2026-08-22T10:00:00+08:00",
        "source_reference": "field-record:runtime-test",
        "verification_note": "Test fixture with auditable provenance.",
    }


def _coordinate(*, status: str = "verified") -> AnchorCoordinateIdentity:
    payload = {
        "spatial_identity_id": "spatial.identity.runtime-test",
        "anchor_id": ANCHOR_ID,
        "location": {"longitude": 112.0, "latitude": 36.0},
        "verification_status": status,
    }
    if status == "verified":
        payload.update(
            provenance=_provenance(), accuracy="precise", confidence="high"
        )
    return AnchorCoordinateIdentity.model_validate(payload)


def _access_point() -> NavigationAccessPoint:
    return NavigationAccessPoint.model_validate(
        {
            "access_point_id": "spatial.access.runtime-test",
            "anchor_id": ANCHOR_ID,
            "name": "Verified navigation entrance",
            "location": {"longitude": 112.01, "latitude": 36.01},
            "access_type": "general_access",
            "verification_status": "verified",
            "provenance": _provenance(),
            "accuracy": "precise",
            "confidence": "high",
            "note": "Navigation target only.",
        }
    )


def _repository(*, bindings=(), coordinates=(), access_points=()):
    base = FileCatalogLoader(CATALOG_ROOT).load()
    package = base.get_package(PACKAGE_ID).model_copy(
        update={
            "poi_bindings": list(bindings),
            "spatial_identities": list(coordinates),
            "navigation_access_points": list(access_points),
        }
    )
    return InMemoryCatalogRepository(
        regions=base.list_regions(),
        themes=base.list_themes(),
        routes=base.list_routes(),
        anchors=base.list_anchors(),
        manifests=(package.manifest,),
        packages=(package,),
        poi_bindings=bindings,
        spatial_identities=coordinates,
        navigation_access_points=access_points,
    )


class _ExactProvider:
    provider = PoiProvider.AMAP

    def __init__(self):
        self.requested_ids: list[str] = []

    async def get_poi(self, external_poi_id: str) -> ExternalPoiRecord:
        self.requested_ids.append(external_poi_id)
        return ExternalPoiRecord(
            provider=self.provider,
            external_poi_id=external_poi_id,
            name="Verified Provider POI",
            location={"lng": 112.0, "lat": 36.0},
        )


def test_existing_provider_poi_anchor_uses_strict_compatibility_path():
    repository = FileCatalogLoader(CATALOG_ROOT).load()
    context = CatalogContextResolver(repository).resolve(PACKAGE_ID, ROUTE_ID)
    provider = _ExactProvider()

    result = asyncio.run(
        MandatorySpatialResolver(
            repository, {PoiProvider.AMAP: provider}
        ).resolve(context)
    )

    assert result[0].spatial_identity_type.value == "provider_poi"
    assert result[0].external_poi_id == "B0FFF49AFB"
    assert result[0].binding_id == "changzhi.binding.fajiushan.amap"
    assert provider.requested_ids == ["B0FFF49AFB"]


def test_verified_coordinate_resolves_without_provider_poi_identity():
    repository = _repository(coordinates=(_coordinate(),))
    context = CatalogContextResolver(repository).resolve(PACKAGE_ID, ROUTE_ID)

    result = asyncio.run(MandatorySpatialResolver(repository, {}).resolve(context))

    assert result[0].spatial_identity_type.value == "verified_coordinate"
    assert result[0].spatial_identity_id == "spatial.identity.runtime-test"
    assert result[0].external_poi_id is None
    assert result[0].provider is None
    assert result[0].cultural_anchor_location == result[0].location


def test_unverified_coordinate_cannot_resolve_at_runtime():
    repository = _repository(coordinates=(_coordinate(status="candidate"),))
    context = CatalogContextResolver(repository).resolve(PACKAGE_ID, ROUTE_ID)

    with pytest.raises(MandatoryPoiResolutionError, match="no verified spatial identity"):
        asyncio.run(MandatorySpatialResolver(repository, {}).resolve(context))


def test_verified_access_point_keeps_navigation_and_cultural_identity_separate():
    repository = _repository(access_points=(_access_point(),))
    context = CatalogContextResolver(repository).resolve(PACKAGE_ID, ROUTE_ID)

    result = asyncio.run(MandatorySpatialResolver(repository, {}).resolve(context))[0]

    assert result.spatial_identity_type.value == "navigation_access_point"
    assert result.name == repository.get_anchor(ANCHOR_ID).name
    assert result.navigation_name == "Verified navigation entrance"
    assert result.navigation_location == result.location
    assert result.cultural_anchor_location is None


def test_name_only_and_nearby_unrelated_poi_do_not_resolve():
    base = FileCatalogLoader(CATALOG_ROOT).load()
    original = base.list_poi_bindings()[0]
    unrelated = ExternalPoiBinding.model_validate(
        {
            **original.model_dump(mode="json"),
            "binding_id": "binding.unrelated.runtime-test",
            "anchor_id": "changzhi.anchor.tiantaishan",
            "external_name": base.get_anchor(ANCHOR_ID).name,
        }
    )
    repository = _repository(bindings=(unrelated,))
    context = CatalogContextResolver(repository).resolve(PACKAGE_ID, ROUTE_ID)
    provider = _ExactProvider()

    with pytest.raises(MandatoryPoiResolutionError, match="no verified spatial identity"):
        asyncio.run(
            MandatorySpatialResolver(
                repository, {PoiProvider.AMAP: provider}
            ).resolve(context)
        )
    assert provider.requested_ids == []


@pytest.mark.parametrize("candidate", [_coordinate(), _access_point()])
def test_mandatory_non_poi_identity_is_preserved(candidate):
    repository = _repository(
        coordinates=(candidate,) if isinstance(candidate, AnchorCoordinateIdentity) else (),
        access_points=(candidate,) if isinstance(candidate, NavigationAccessPoint) else (),
    )
    context = CatalogContextResolver(repository).resolve(PACKAGE_ID, ROUTE_ID)
    resolved = asyncio.run(MandatorySpatialResolver(repository, {}).resolve(context))
    pool = merge_spatial_candidates([], resolved)
    route = [
        {
            "day": 1,
            "spots": [
                {
                    "name": pool[0]["name"],
                    "spatial_identity_type": pool[0]["spatial_identity_type"],
                    "spatial_identity_id": pool[0]["spatial_identity_id"],
                    "curated_anchor_id": ANCHOR_ID,
                    "is_mandatory": True,
                }
            ],
        }
    ]

    assert missing_mandatory_spatial_candidates(route, pool) == []
    assert missing_mandatory_spatial_candidates(
        [{"day": 1, "spots": [{"name": pool[0]["name"]}]}], pool
    ) == pool


def test_coordinate_candidate_round_trips_through_planning_state():
    repository = _repository(coordinates=(_coordinate(),))
    context = CatalogContextResolver(repository).resolve(PACKAGE_ID, ROUTE_ID)
    candidate = asyncio.run(MandatorySpatialResolver(repository, {}).resolve(context))[0]
    state = TravelPlanState(
        query="test",
        catalog_context=context,
        mandatory_spatial_candidates=[candidate.model_dump(mode="json")],
    )

    restored = TravelPlanState.model_validate_json(state.model_dump_json())

    assert restored.mandatory_spatial_candidates == state.mandatory_spatial_candidates


class _TravelProvider:
    provider = PoiProvider.AMAP

    async def get_travel_time(self, origin, destination, transport_mode):
        return TravelLeg(
            from_poi=origin,
            to_poi=destination,
            distance_m=1000,
            duration_s=600,
            provider=self.provider,
            transport_mode=transport_mode,
            source="test-coordinate-routing",
        )


def test_travel_time_consumes_coordinate_without_external_poi_id():
    coordinate = TravelPoint(
        spatial_identity_type="verified_coordinate",
        spatial_identity_id="spatial.identity.runtime-test",
        curated_anchor_id=ANCHOR_ID,
        name="Cultural place",
        longitude=112.0,
        latitude=36.0,
    )
    provider_poi = TravelPoint(
        provider="amap",
        external_poi_id="POI-1",
        name="Provider POI",
        longitude=112.1,
        latitude=36.1,
    )
    matrix = TravelTimeMatrix({PoiProvider.AMAP: _TravelProvider()})

    leg = asyncio.run(matrix.get_leg(coordinate, provider_poi, TransportMode.DRIVING))

    assert leg.duration_s == 600
    assert leg.from_poi.external_poi_id is None
    assert leg.provider is PoiProvider.AMAP
