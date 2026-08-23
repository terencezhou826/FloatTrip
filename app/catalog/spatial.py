"""Route-neutral Catalog projection for mandatory spatial readiness."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.catalog.models import SpatialResolutionLevel, StableId
from app.catalog.repository import CatalogRepository


class CatalogSpatialResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    anchor_id: StableId
    resolution_level: SpatialResolutionLevel | None = None
    identity_id: StableId | None = None
    planning_available: bool = False
    ready_capable: bool = False
    navigation_available: bool = False
    degraded: bool = False
    disclosure_required: bool = False
    disclosure_text: str | None = None
    exact_anchor_location_available: bool = False
    ambiguous: bool = False


def project_anchor_spatial_resolution(
    repository: CatalogRepository, anchor_id: str
) -> CatalogSpatialResolution:
    levels = (
        (
            SpatialResolutionLevel.EXACT_PROVIDER_POI,
            repository.list_verified_bindings_for_anchor(anchor_id),
        ),
        (
            SpatialResolutionLevel.VERIFIED_COORDINATE,
            repository.list_verified_spatial_identities_for_anchor(anchor_id),
        ),
        (
            SpatialResolutionLevel.VERIFIED_ACCESS_POINT,
            repository.list_verified_navigation_access_points_for_anchor(anchor_id),
        ),
        (
            None,
            repository.list_verified_locality_identities_for_anchor(anchor_id),
        ),
    )
    for fixed_level, records in levels:
        if not records:
            continue
        if len(records) != 1:
            return CatalogSpatialResolution(anchor_id=anchor_id, ambiguous=True)
        record = records[0]
        level = fixed_level or record.resolution_level
        if level is SpatialResolutionLevel.EXACT_PROVIDER_POI:
            identity_id = record.binding_id
        elif level is SpatialResolutionLevel.VERIFIED_COORDINATE:
            identity_id = record.spatial_identity_id
        elif level is SpatialResolutionLevel.VERIFIED_ACCESS_POINT:
            identity_id = record.access_point_id
        else:
            identity_id = record.locality_identity_id

        locality_ready = level is SpatialResolutionLevel.VERIFIED_LOCALITY
        township_ready = bool(
            level is SpatialResolutionLevel.VERIFIED_TOWNSHIP
            and record.metadata.get("township_ready_approved") is True
        )
        ready_capable = level in {
            SpatialResolutionLevel.EXACT_PROVIDER_POI,
            SpatialResolutionLevel.VERIFIED_COORDINATE,
            SpatialResolutionLevel.VERIFIED_ACCESS_POINT,
        } or locality_ready or township_ready
        locality_record = fixed_level is None
        return CatalogSpatialResolution(
            anchor_id=anchor_id,
            resolution_level=level,
            identity_id=identity_id,
            planning_available=ready_capable,
            ready_capable=ready_capable,
            navigation_available=(
                True if not locality_record else record.navigation_reference is not None
            ),
            degraded=level
            in {
                SpatialResolutionLevel.VERIFIED_LOCALITY,
                SpatialResolutionLevel.VERIFIED_TOWNSHIP,
                SpatialResolutionLevel.ADMINISTRATIVE_AREA,
            },
            disclosure_required=bool(
                locality_record and record.disclosure_text
            ),
            disclosure_text=(record.disclosure_text if locality_record else None),
            exact_anchor_location_available=level
            in {
                SpatialResolutionLevel.EXACT_PROVIDER_POI,
                SpatialResolutionLevel.VERIFIED_COORDINATE,
            },
        )
    return CatalogSpatialResolution(anchor_id=anchor_id)
