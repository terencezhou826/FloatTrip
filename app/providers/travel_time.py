"""Provider-neutral point-to-point travel-time contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.catalog.models import PoiProvider, SpatialIdentityType


class TransportMode(StrEnum):
    DRIVING = "driving"


class TravelPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: PoiProvider | None = None
    external_poi_id: str | None = Field(default=None, min_length=1, max_length=256)
    routing_provider: PoiProvider | None = None
    spatial_identity_type: SpatialIdentityType = SpatialIdentityType.PROVIDER_POI
    spatial_identity_id: str | None = Field(default=None, min_length=1, max_length=256)
    curated_anchor_id: str | None = Field(default=None, min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=256)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)

    @model_validator(mode="after")
    def validate_identity(self) -> "TravelPoint":
        if self.spatial_identity_type is SpatialIdentityType.PROVIDER_POI:
            if self.provider is None or self.external_poi_id is None:
                raise ValueError("provider_poi requires provider and external_poi_id")
        elif self.spatial_identity_id is None or self.curated_anchor_id is None:
            raise ValueError(
                "coordinate and access-point identities require spatial_identity_id "
                "and curated_anchor_id"
            )
        return self

    @property
    def identity(self) -> tuple[object, str]:
        if self.spatial_identity_type is SpatialIdentityType.PROVIDER_POI:
            return self.provider, self.external_poi_id
        return self.spatial_identity_type, self.spatial_identity_id

    @property
    def effective_routing_provider(self) -> PoiProvider | None:
        return self.routing_provider or self.provider


class TravelLeg(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    from_poi: TravelPoint
    to_poi: TravelPoint
    distance_m: int = Field(ge=0)
    duration_s: int = Field(ge=0)
    provider: PoiProvider
    transport_mode: TransportMode
    source: str = Field(min_length=1, max_length=256)


class TravelRoutingError(RuntimeError):
    pass


class TravelTimeProvider(Protocol):
    provider: PoiProvider

    async def get_travel_time(
        self,
        origin: TravelPoint,
        destination: TravelPoint,
        transport_mode: TransportMode,
    ) -> TravelLeg: ...
