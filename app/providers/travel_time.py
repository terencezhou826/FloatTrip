"""Provider-neutral point-to-point travel-time contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.catalog.models import PoiProvider


class TransportMode(StrEnum):
    DRIVING = "driving"


class TravelPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: PoiProvider
    external_poi_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)

    @property
    def identity(self) -> tuple[PoiProvider, str]:
        return self.provider, self.external_poi_id


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
