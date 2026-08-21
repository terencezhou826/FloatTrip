"""Domain models for the curated content catalog."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

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


class CuratedRoute(CatalogModel):
    id: StableId
    name: str = Field(min_length=1, max_length=160)
    primary_region_id: StableId
    coverage_region_ids: list[StableId] = Field(min_length=1)
    theme_id: StableId
    anchor_ids: list[StableId] = Field(min_length=1)
    mandatory_anchor_ids: list[StableId] = Field(min_length=1)

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
