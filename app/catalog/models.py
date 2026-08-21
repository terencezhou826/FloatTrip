"""Domain models for the curated content catalog."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


StableId = Annotated[
    str,
    Field(min_length=1, max_length=160, pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$"),
]


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ThemeType(StrEnum):
    MYTHOLOGY = "mythology"
    HISTORICAL_FIGURE = "historical_figure"
    ANCIENT_ARCHITECTURE = "ancient_architecture"
    RED_CULTURE = "red_culture"
    FOLK_CUSTOM = "folk_custom"
    FOOD = "food"
    NATURE = "nature"
    HERITAGE = "heritage"
    CUSTOM = "custom"


class RegionType(StrEnum):
    PROVINCE = "province"
    PREFECTURE_CITY = "prefecture_city"
    COUNTY = "county"
    DISTRICT = "district"
    COUNTY_LEVEL_CITY = "county_level_city"


class PoiProvider(StrEnum):
    AMAP = "amap"
    BAIDU = "baidu"
    TENCENT = "tencent"
    OTHER = "other"
    CUSTOM = "custom"


class PoiVerificationStatus(StrEnum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    REJECTED = "rejected"


class PoiVerificationMethod(StrEnum):
    MANUAL_REVIEW = "manual_review"
    PROVIDER_EXACT_ID = "provider_exact_id"
    OFFICIAL_SOURCE = "official_source"
    OTHER = "other"


class Region(CatalogModel):
    id: StableId
    name: str = Field(min_length=1, max_length=100)
    parent_id: StableId | None = None
    region_type: RegionType
    admin_code: str | None = Field(default=None, min_length=1, max_length=32)


class CatalogTheme(CatalogModel):
    id: StableId
    type: ThemeType
    name: str = Field(min_length=1, max_length=100)
    region_id: StableId
    custom_type: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_custom_type(self) -> "CatalogTheme":
        if self.type is ThemeType.CUSTOM and self.custom_type is None:
            raise ValueError("custom themes require custom_type")
        if self.type is not ThemeType.CUSTOM and self.custom_type is not None:
            raise ValueError("custom_type is only valid for custom themes")
        return self


class Anchor(CatalogModel):
    id: StableId
    name: str = Field(min_length=1, max_length=100)
    region_id: StableId


class ExternalPoiBinding(CatalogModel):
    binding_id: StableId
    anchor_id: StableId
    provider: PoiProvider
    external_poi_id: str = Field(min_length=1, max_length=256)
    external_name: str = Field(min_length=1, max_length=256)
    verification_status: PoiVerificationStatus
    provider_region_code: str | None = Field(default=None, min_length=1, max_length=64)
    provider_address: str | None = Field(default=None, min_length=1, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    verification_method: PoiVerificationMethod | None = None
    verified_at: datetime | None = None
    verification_note: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_verification_provenance(self) -> "ExternalPoiBinding":
        if self.verification_status is PoiVerificationStatus.VERIFIED:
            missing = []
            if self.verification_method is None:
                missing.append("verification_method")
            if self.verified_at is None:
                missing.append("verified_at")
            if missing:
                raise ValueError(f"verified bindings require {', '.join(missing)}")
        return self

    @property
    def is_runtime_eligible(self) -> bool:
        return self.verification_status is PoiVerificationStatus.VERIFIED


class CuratedRoute(CatalogModel):
    id: StableId
    name: str = Field(min_length=1, max_length=160)
    primary_region_id: StableId
    coverage_region_ids: list[StableId] = Field(min_length=1)
    theme_id: StableId
    anchor_ids: list[StableId] = Field(min_length=1)
    mandatory_anchor_ids: list[StableId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_mandatory_anchors(self) -> "CuratedRoute":
        if not set(self.mandatory_anchor_ids).issubset(self.anchor_ids):
            raise ValueError("mandatory_anchor_ids must be included in anchor_ids")
        return self


class ContentPackageManifest(CatalogModel):
    package_id: StableId
    schema_version: str = Field(pattern=r"^\d+\.\d+$")
    content_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    region_id: StableId
    enabled: StrictBool


class ContentPackage(CatalogModel):
    manifest: ContentPackageManifest
    themes: list[CatalogTheme]
    routes: list[CuratedRoute]
    anchors: list[Anchor]
    poi_bindings: list[ExternalPoiBinding] = Field(default_factory=list)
