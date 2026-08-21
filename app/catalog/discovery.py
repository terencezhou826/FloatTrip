"""Provider-neutral candidate discovery for curated Anchors."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field

from app.catalog.models import CatalogModel, PoiProvider, Region, StableId
from app.catalog.repository import CatalogRepository


class PoiLocation(CatalogModel):
    lng: float
    lat: float


class ExternalPoiCandidate(CatalogModel):
    provider: PoiProvider
    external_poi_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    address: str | None = Field(default=None, max_length=500)
    provider_region_code: str | None = Field(default=None, max_length=64)
    location: PoiLocation | None = None
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class PoiDiscoveryQuery(CatalogModel):
    anchor_id: StableId
    anchor_name: str = Field(min_length=1, max_length=100)
    region_path: tuple[Region, ...]


class PoiDiscoveryProvider(Protocol):
    provider: PoiProvider

    def search_candidates(
        self, query: PoiDiscoveryQuery
    ) -> tuple[ExternalPoiCandidate, ...]: ...


class AnchorPoiDiscoveryError(ValueError):
    pass


class AnchorPoiDiscovery:
    def __init__(self, repository: CatalogRepository):
        self._repository = repository

    def discover(
        self,
        anchor_id: str,
        provider: PoiDiscoveryProvider,
    ) -> tuple[ExternalPoiCandidate, ...]:
        anchor = self._repository.get_anchor(anchor_id)
        if anchor is None:
            raise AnchorPoiDiscoveryError(f"anchor {anchor_id} not found")

        query = PoiDiscoveryQuery(
            anchor_id=anchor.id,
            anchor_name=anchor.name,
            region_path=self._region_path(anchor.region_id),
        )
        return tuple(provider.search_candidates(query))

    def _region_path(self, region_id: str) -> tuple[Region, ...]:
        path: list[Region] = []
        visited: set[str] = set()
        current_id: str | None = region_id
        while current_id is not None:
            if current_id in visited:
                raise AnchorPoiDiscoveryError(
                    f"region hierarchy cycle includes {current_id}"
                )
            visited.add(current_id)
            region = self._repository.get_region(current_id)
            if region is None:
                raise AnchorPoiDiscoveryError(f"region {current_id} not found")
            path.append(region)
            current_id = region.parent_id
        path.reverse()
        return tuple(path)
