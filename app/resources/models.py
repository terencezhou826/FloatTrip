"""Provider-neutral contracts for local resource discovery and recommendation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from app.catalog.models import (
    CatalogModel,
    CommercialRelationship,
    CurrencyCode,
    LocalResourceType,
    PoiProvider,
    PriceStatus,
    ResourceCoordinates,
    ResourceOperationalStatus,
    ResourceVerificationStatus,
    StableId,
)


class ResourceProvenanceType(StrEnum):
    RUNTIME_PROVIDER = "runtime_provider"
    CURATED_CATALOG = "curated_catalog"


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class ProviderPriceInfo(CatalogModel):
    price_status: PriceStatus = PriceStatus.UNKNOWN
    currency: CurrencyCode | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, min_length=1, max_length=64)
    provider: PoiProvider | None = None
    source_field: str | None = Field(default=None, min_length=1, max_length=128)
    retrieved_at: datetime | None = None
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN

    @model_validator(mode="after")
    def validate_provider_price(self) -> "ProviderPriceInfo":
        if self.price_status is PriceStatus.UNKNOWN:
            if any(
                value is not None
                for value in (
                    self.currency,
                    self.amount,
                    self.unit,
                    self.provider,
                    self.source_field,
                    self.retrieved_at,
                )
            ) or self.freshness_status is not FreshnessStatus.UNKNOWN:
                raise ValueError("unknown provider price cannot carry price claims")
            return self
        if self.price_status is not PriceStatus.PER_PERSON:
            raise ValueError("runtime provider price currently supports per_person only")
        if any(
            value is None
            for value in (
                self.currency,
                self.amount,
                self.unit,
                self.provider,
                self.source_field,
                self.retrieved_at,
            )
        ):
            raise ValueError("provider price requires value and provenance")
        return self


class ProviderBusinessHours(CatalogModel):
    display_text: str = Field(min_length=1, max_length=500)
    provider: PoiProvider
    source_field: str = Field(min_length=1, max_length=128)
    retrieved_at: datetime
    freshness_status: FreshnessStatus


class RuntimeResourceCandidate(CatalogModel):
    runtime_resource_id: StableId
    resource_type: LocalResourceType
    name: str = Field(min_length=1, max_length=256)
    provider: PoiProvider
    external_poi_id: str = Field(min_length=1, max_length=256)
    coordinates: ResourceCoordinates
    address: str | None = Field(default=None, min_length=1, max_length=500)
    province: str | None = Field(default=None, min_length=1, max_length=100)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    district: str | None = Field(default=None, min_length=1, max_length=100)
    provider_region_code: str | None = Field(default=None, min_length=1, max_length=64)
    poi_type: str | None = Field(default=None, min_length=1, max_length=300)
    provider_distance_m: int | None = Field(default=None, ge=0)
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    price_info: ProviderPriceInfo = Field(default_factory=ProviderPriceInfo)
    business_hours: ProviderBusinessHours | None = None
    verification_status: ResourceVerificationStatus = ResourceVerificationStatus.CANDIDATE
    operational_status: ResourceOperationalStatus = ResourceOperationalStatus.UNKNOWN
    provenance_type: ResourceProvenanceType = ResourceProvenanceType.RUNTIME_PROVIDER
    provider_source: str = Field(min_length=1, max_length=256)
    retrieved_at: datetime
    freshness_status: FreshnessStatus
    commercial_relationship: CommercialRelationship = CommercialRelationship.UNKNOWN
    provider_raw_fields: dict[str, Any] = Field(default_factory=dict)
    discovery_stop_id: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_runtime_candidate(self) -> "RuntimeResourceCandidate":
        if self.verification_status is not ResourceVerificationStatus.CANDIDATE:
            raise ValueError("runtime Provider resources must remain candidate")
        if self.provenance_type is not ResourceProvenanceType.RUNTIME_PROVIDER:
            raise ValueError("runtime Provider resource requires Provider provenance")
        return self

    @property
    def identity(self) -> tuple[PoiProvider, str]:
        return self.provider, self.external_poi_id


def classify_freshness(
    retrieved_at: datetime | None,
    *,
    as_of: datetime,
    max_age: timedelta,
) -> FreshnessStatus:
    if retrieved_at is None:
        return FreshnessStatus.UNKNOWN
    retrieved = retrieved_at
    reference = as_of
    if retrieved.tzinfo is None:
        retrieved = retrieved.replace(tzinfo=timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return (
        FreshnessStatus.STALE
        if reference - retrieved > max_age
        else FreshnessStatus.FRESH
    )
