"""Durable state contracts for post-planning product fulfillment."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.catalog.models import CatalogModel


class ProductFulfillmentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PARTIAL = "partial"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class FulfillmentStageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"


class FulfillmentStage(StrEnum):
    STORY = "story"
    EXPERIENCE = "experience"
    RESOURCES = "resources"


class ProductFulfillmentJob(CatalogModel):
    job_id: str = Field(min_length=1, max_length=256)
    owner_id: str = Field(min_length=1, max_length=256)
    run_id: str = Field(min_length=1, max_length=256)
    itinerary_id: str = Field(min_length=1, max_length=256)
    route_id: str = Field(min_length=1, max_length=256)
    package_id: str = Field(min_length=1, max_length=256)
    schema_version: str = Field(min_length=1, max_length=64)
    content_version: str = Field(min_length=1, max_length=64)
    status: ProductFulfillmentStatus
    story_status: FulfillmentStageStatus
    experience_status: FulfillmentStageStatus
    resources_status: FulfillmentStageStatus
    story_package_id: str | None = None
    story_snapshot_hash: str | None = None
    experience_package_id: str | None = None
    experience_snapshot_hash: str | None = None
    resource_package_id: str | None = None
    resource_snapshot_hash: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempt_count: int = Field(default=0, ge=0)
    last_error_stage: FulfillmentStage | None = None
    last_error_class: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None

    def stage_status(self, stage: FulfillmentStage) -> FulfillmentStageStatus:
        return getattr(self, f"{stage.value}_status")


class FulfillmentSnapshotRef(CatalogModel):
    package_id: str = Field(min_length=1, max_length=256)
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class FulfillmentStageResult(CatalogModel):
    status: FulfillmentStageStatus
    snapshot: FulfillmentSnapshotRef | None = None

