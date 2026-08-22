"""Resolve mandatory cultural Anchors to verified spatial identities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.catalog.models import PoiProvider, SpatialIdentityType, StableId
from app.catalog.repository import CatalogRepository
from app.planning.catalog_context import CatalogContext
from app.planning.mandatory_pois import (
    MandatoryPoiResolutionError,
    MandatoryPoiResolver,
)
from app.providers.poi_identity import ExactPoiProvider, PoiLocation


class ResolvedMandatorySpatialCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=256)
    location: PoiLocation
    curated_anchor_id: StableId
    is_mandatory: bool = True
    spatial_identity_type: SpatialIdentityType
    spatial_identity_id: StableId
    provenance_id: StableId
    binding_id: StableId | None = None
    provider: PoiProvider | None = None
    external_poi_id: str | None = Field(default=None, min_length=1, max_length=256)
    rating: float | None = None
    open_time: str | None = None
    photo: str | None = None
    region_name: str | None = None
    address: str | None = None
    tel: str | None = None
    cost: str | None = None
    cultural_anchor_location: PoiLocation | None = None
    navigation_location: PoiLocation | None = None
    navigation_name: str | None = Field(default=None, min_length=1, max_length=256)


class MandatorySpatialResolver:
    """Resolve each mandatory Anchor by strict identity priority, without search."""

    def __init__(
        self,
        repository: CatalogRepository,
        providers: Mapping[PoiProvider, ExactPoiProvider],
    ) -> None:
        self._repository = repository
        self._providers = providers

    async def resolve(
        self, context: CatalogContext | None
    ) -> tuple[ResolvedMandatorySpatialCandidate, ...]:
        if context is None or not context.mandatory_anchor_ids:
            return ()
        self._validate_snapshot(context)

        resolved: list[ResolvedMandatorySpatialCandidate] = []
        for anchor_id in context.mandatory_anchor_ids:
            anchor = self._repository.get_anchor(anchor_id)
            if anchor_id not in context.anchor_ids:
                raise MandatoryPoiResolutionError(
                    f"mandatory anchor {anchor_id} is outside the selected route"
                )
            if anchor is None:
                raise MandatoryPoiResolutionError(
                    f"mandatory anchor {anchor_id} is unavailable"
                )

            bindings = self._repository.list_verified_bindings_for_anchor(anchor_id)
            if bindings:
                if len(bindings) > 1:
                    raise MandatoryPoiResolutionError(
                        f"mandatory anchor {anchor_id} has multiple verified bindings"
                    )
                poi = (
                    await MandatoryPoiResolver(
                        self._repository, self._providers
                    ).resolve(context.model_copy(update={"mandatory_anchor_ids": (anchor_id,)}))
                )[0]
                resolved.append(
                    ResolvedMandatorySpatialCandidate(
                        **poi.model_dump(),
                        spatial_identity_type=SpatialIdentityType.PROVIDER_POI,
                        spatial_identity_id=poi.binding_id,
                        provenance_id=poi.binding_id,
                        cultural_anchor_location=poi.location,
                    )
                )
                continue

            coordinates = (
                self._repository.list_verified_spatial_identities_for_anchor(anchor_id)
            )
            if coordinates:
                if len(coordinates) > 1:
                    raise MandatoryPoiResolutionError(
                        f"mandatory anchor {anchor_id} has multiple verified coordinates"
                    )
                identity = coordinates[0]
                resolved.append(
                    ResolvedMandatorySpatialCandidate(
                        name=anchor.name,
                        location=PoiLocation(
                            lng=identity.location.longitude,
                            lat=identity.location.latitude,
                        ),
                        curated_anchor_id=anchor_id,
                        spatial_identity_type=SpatialIdentityType.VERIFIED_COORDINATE,
                        spatial_identity_id=identity.spatial_identity_id,
                        provenance_id=identity.provenance.provenance_id,
                        cultural_anchor_location=PoiLocation(
                            lng=identity.location.longitude,
                            lat=identity.location.latitude,
                        ),
                    )
                )
                continue

            access_points = (
                self._repository.list_verified_navigation_access_points_for_anchor(
                    anchor_id
                )
            )
            if access_points:
                if len(access_points) > 1:
                    raise MandatoryPoiResolutionError(
                        f"mandatory anchor {anchor_id} has multiple verified navigation "
                        "access points"
                    )
                access = access_points[0]
                navigation_location = PoiLocation(
                    lng=access.location.longitude,
                    lat=access.location.latitude,
                )
                resolved.append(
                    ResolvedMandatorySpatialCandidate(
                        name=anchor.name,
                        location=navigation_location,
                        curated_anchor_id=anchor_id,
                        spatial_identity_type=(
                            SpatialIdentityType.NAVIGATION_ACCESS_POINT
                        ),
                        spatial_identity_id=access.access_point_id,
                        provenance_id=access.provenance.provenance_id,
                        navigation_location=navigation_location,
                        navigation_name=access.name,
                    )
                )
                continue

            raise MandatoryPoiResolutionError(
                f"mandatory anchor {anchor_id} has no verified spatial identity"
            )
        return tuple(resolved)

    def _validate_snapshot(self, context: CatalogContext) -> None:
        package = self._repository.get_package(context.package_id)
        if package is None or not package.manifest.enabled:
            raise MandatoryPoiResolutionError(
                f"catalog package {context.package_id} is unavailable"
            )
        if (
            package.manifest.schema_version != context.schema_version
            or package.manifest.content_version != context.content_version
        ):
            raise MandatoryPoiResolutionError(
                "catalog snapshot version is no longer available"
            )
        if self._repository.get_route(context.route_id) is None:
            raise MandatoryPoiResolutionError(
                f"catalog route {context.route_id} is unavailable"
            )


def _as_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    return dict(item)


def spatial_identity(item: Mapping[str, Any]) -> tuple[str, ...] | None:
    provider = item.get("provider")
    external_poi_id = item.get("external_poi_id")
    if hasattr(provider, "value"):
        provider = provider.value
    if provider and external_poi_id:
        return "provider_poi", str(provider), str(external_poi_id)
    identity_type = item.get("spatial_identity_type")
    if hasattr(identity_type, "value"):
        identity_type = identity_type.value
    spatial_identity_id = item.get("spatial_identity_id")
    if identity_type and spatial_identity_id:
        return str(identity_type), str(spatial_identity_id)
    return None


def merge_spatial_candidates(
    ordinary: Sequence[dict[str, Any]], mandatory: Sequence[Any]
) -> list[dict[str, Any]]:
    if not mandatory:
        return list(ordinary)
    merged = [dict(item) for item in ordinary]
    positions = {
        identity: index
        for index, item in enumerate(merged)
        if (identity := spatial_identity(item)) is not None
    }
    for raw in mandatory:
        item = _as_dict(raw)
        identity = spatial_identity(item)
        if identity is not None and identity in positions:
            index = positions[identity]
            merged[index] = {**merged[index], **item}
        else:
            if identity is not None:
                positions[identity] = len(merged)
            merged.append(item)
    return merged


def missing_mandatory_spatial_candidates(
    route: Sequence[Mapping[str, Any]], mandatory: Sequence[Any]
) -> list[dict[str, Any]]:
    selected = {
        identity
        for day in route
        for spot in day.get("spots", [])
        if (identity := spatial_identity(spot)) is not None
    }
    return [
        item
        for raw in mandatory
        if (item := _as_dict(raw)) and spatial_identity(item) not in selected
    ]


def mandatory_spatial_constraint_block(mandatory: Sequence[Any]) -> str:
    if not mandatory:
        return ""
    lines = []
    provider_only = True
    for raw in mandatory:
        item = _as_dict(raw)
        identity = spatial_identity(item)
        if identity is None:
            continue
        provider_only = provider_only and identity[0] == "provider_poi"
        lines.append(
            f"- {item['name']} | spatial_identity_type={identity[0]} | "
            f"spatial_identity_id={item.get('spatial_identity_id') or identity[-1]} | "
            f"curated_anchor_id={item['curated_anchor_id']}"
            + (
                f" | provider={item['provider']} | "
                f"external_poi_id={item['external_poi_id']}"
                if identity[0] == "provider_poi"
                else ""
            )
        )
    heading = "mandatory POI" if provider_only else "mandatory spatial Anchor"
    return (
        f"\n\n【策展线路 {heading} 硬约束】\n"
        "以下文化地点必须在最终路线中至少安排一次，输出时必须原样保留其稳定空间身份、"
        "curated_anchor_id 和 is_mandatory；Provider POI 还必须保留 provider 与 "
        "external_poi_id。不得按名称猜测、搜索替代或使用附近地点：\n"
        + "\n".join(lines)
    )
