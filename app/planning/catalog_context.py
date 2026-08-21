"""Versioned Catalog selection projected into planning state."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.catalog.models import StableId
from app.catalog.repository import CatalogRepository


class CatalogContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    package_id: StableId
    schema_version: str = Field(pattern=r"^\d+\.\d+$")
    content_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    region_id: StableId
    theme_id: StableId
    route_id: StableId
    theme_name: str = Field(min_length=1, max_length=100)
    route_name: str = Field(min_length=1, max_length=160)
    primary_region_id: StableId
    coverage_region_ids: tuple[StableId, ...] = Field(min_length=1)
    anchor_ids: tuple[StableId, ...] = Field(min_length=1)
    mandatory_anchor_ids: tuple[StableId, ...] = Field(min_length=1)


class CatalogContextResolutionError(ValueError):
    pass


class CatalogContextResolver:
    def __init__(self, repository: CatalogRepository):
        self.repository = repository

    def resolve(self, package_id: str, route_id: str) -> CatalogContext:
        package = self.repository.get_package(package_id)
        if package is None:
            raise CatalogContextResolutionError(f"package {package_id} not found")
        manifest = package.manifest
        if not manifest.enabled:
            raise CatalogContextResolutionError(f"package {package_id} is disabled")

        package_route_ids = {item.id for item in package.routes}
        route = self.repository.get_route(route_id)
        if route is None or route_id not in package_route_ids:
            raise CatalogContextResolutionError(
                f"route {route_id} not found in package {package_id}"
            )

        package_theme_ids = {item.id for item in package.themes}
        theme = self.repository.get_theme(route.theme_id)
        if theme is None or theme.id not in package_theme_ids:
            raise CatalogContextResolutionError(f"theme {route.theme_id} not found")

        package_anchor_ids = {item.id for item in package.anchors}
        anchors = []
        for anchor_id in route.anchor_ids:
            anchor = self.repository.get_anchor(anchor_id)
            if anchor is None or anchor_id not in package_anchor_ids:
                raise CatalogContextResolutionError(f"anchor {anchor_id} not found")
            anchors.append(anchor)

        region_references = {
            manifest.region_id,
            theme.region_id,
            route.primary_region_id,
            *route.coverage_region_ids,
            *(anchor.region_id for anchor in anchors),
        }
        for region_id in region_references:
            if self.repository.get_region(region_id) is None:
                raise CatalogContextResolutionError(f"region {region_id} not found")

        anchor_ids = {anchor.id for anchor in anchors}
        missing_mandatory = set(route.mandatory_anchor_ids) - anchor_ids
        if missing_mandatory:
            missing = ", ".join(sorted(missing_mandatory))
            raise CatalogContextResolutionError(
                f"mandatory anchors not found: {missing}"
            )

        return CatalogContext(
            package_id=manifest.package_id,
            schema_version=manifest.schema_version,
            content_version=manifest.content_version,
            region_id=manifest.region_id,
            theme_id=theme.id,
            route_id=route.id,
            theme_name=theme.name,
            route_name=route.name,
            primary_region_id=route.primary_region_id,
            coverage_region_ids=tuple(route.coverage_region_ids),
            anchor_ids=tuple(route.anchor_ids),
            mandatory_anchor_ids=tuple(route.mandatory_anchor_ids),
        )


def freeze_catalog_selection(
    request_snapshot: dict[str, Any],
    resolver: CatalogContextResolver,
) -> dict[str, Any]:
    snapshot = dict(request_snapshot)
    package_id = snapshot.get("package_id")
    route_id = snapshot.get("route_id")
    if package_id is None and route_id is None:
        return snapshot
    if not isinstance(package_id, str) or not package_id:
        raise CatalogContextResolutionError(
            "package_id is required when route_id is selected"
        )
    if not isinstance(route_id, str) or not route_id:
        raise CatalogContextResolutionError(
            "route_id is required when package_id is selected"
        )
    snapshot["catalog_context"] = resolver.resolve(
        package_id, route_id
    ).model_dump(mode="json")
    return snapshot
