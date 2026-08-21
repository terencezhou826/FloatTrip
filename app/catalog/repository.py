"""Repository contract and immutable in-memory Catalog implementation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from app.catalog.models import (
    Anchor,
    CatalogTheme,
    ContentPackageManifest,
    CuratedRoute,
    Region,
)


@runtime_checkable
class CatalogRepository(Protocol):
    def get_region(self, region_id: str) -> Region | None: ...

    def list_regions(self) -> tuple[Region, ...]: ...

    def get_theme(self, theme_id: str) -> CatalogTheme | None: ...

    def list_themes(self, region_id: str | None = None) -> tuple[CatalogTheme, ...]: ...

    def get_route(self, route_id: str) -> CuratedRoute | None: ...

    def list_routes(self, region_id: str | None = None) -> tuple[CuratedRoute, ...]: ...

    def get_anchor(self, anchor_id: str) -> Anchor | None: ...

    def list_anchors(self, region_id: str | None = None) -> tuple[Anchor, ...]: ...

    def list_manifests(self) -> tuple[ContentPackageManifest, ...]: ...


class InMemoryCatalogRepository:
    def __init__(
        self,
        *,
        regions: Iterable[Region],
        themes: Iterable[CatalogTheme],
        routes: Iterable[CuratedRoute],
        anchors: Iterable[Anchor],
        manifests: Iterable[ContentPackageManifest],
    ) -> None:
        self._regions = tuple(regions)
        self._themes = tuple(themes)
        self._routes = tuple(routes)
        self._anchors = tuple(anchors)
        self._manifests = tuple(manifests)
        self._regions_by_id = {item.id: item for item in self._regions}
        self._themes_by_id = {item.id: item for item in self._themes}
        self._routes_by_id = {item.id: item for item in self._routes}
        self._anchors_by_id = {item.id: item for item in self._anchors}

    def get_region(self, region_id: str) -> Region | None:
        return self._regions_by_id.get(region_id)

    def list_regions(self) -> tuple[Region, ...]:
        return self._regions

    def get_theme(self, theme_id: str) -> CatalogTheme | None:
        return self._themes_by_id.get(theme_id)

    def list_themes(self, region_id: str | None = None) -> tuple[CatalogTheme, ...]:
        return self._filter_region(self._themes, region_id)

    def get_route(self, route_id: str) -> CuratedRoute | None:
        return self._routes_by_id.get(route_id)

    def list_routes(self, region_id: str | None = None) -> tuple[CuratedRoute, ...]:
        if region_id is None:
            return self._routes
        return tuple(
            route
            for route in self._routes
            if route.primary_region_id == region_id
            or region_id in route.coverage_region_ids
        )

    def get_anchor(self, anchor_id: str) -> Anchor | None:
        return self._anchors_by_id.get(anchor_id)

    def list_anchors(self, region_id: str | None = None) -> tuple[Anchor, ...]:
        return self._filter_region(self._anchors, region_id)

    def list_manifests(self) -> tuple[ContentPackageManifest, ...]:
        return self._manifests

    @staticmethod
    def _filter_region(items, region_id: str | None):
        if region_id is None:
            return items
        return tuple(item for item in items if item.region_id == region_id)
