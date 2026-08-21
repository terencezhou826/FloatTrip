"""Provider-neutral exact POI identity contracts."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.catalog.models import PoiProvider


class PoiLocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lng: float
    lat: float


class ExternalPoiRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: PoiProvider
    external_poi_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=256)
    location: PoiLocation
    rating: float | None = None
    open_time: str | None = None
    photo: str | None = None
    region_name: str | None = None
    address: str | None = None
    tel: str | None = None
    cost: str | None = None


class ExactPoiProvider(Protocol):
    provider: PoiProvider

    async def get_poi(self, external_poi_id: str) -> ExternalPoiRecord: ...
