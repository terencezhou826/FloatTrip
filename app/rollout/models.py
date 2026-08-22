"""Read-only reporting contracts for route rollout progress."""

from __future__ import annotations

from enum import StrEnum

from app.evaluation.models import EvaluationModel, RouteReadinessResult


class RouteRolloutStatus(StrEnum):
    CATALOG_ONLY = "catalog_only"
    POI_PENDING = "poi_pending"
    KNOWLEDGE_PENDING = "knowledge_pending"
    STORY_PENDING = "story_pending"
    EXPERIENCE_PENDING = "experience_pending"
    VALIDATION_PENDING = "validation_pending"
    READY = "ready"
    BLOCKED = "blocked"


class RolloutLayer(StrEnum):
    CATALOG = "catalog"
    POI = "poi"
    KNOWLEDGE = "knowledge"
    STORY = "story"
    EXPERIENCE = "experience"
    RESOURCES = "resources"
    EVALUATION = "evaluation"
    PRODUCT = "product"


class RolloutLayerStatus(StrEnum):
    PASS = "PASS"
    MISSING = "MISSING"
    BLOCKED = "BLOCKED"
    OPTIONAL = "OPTIONAL"


class RolloutLayerAudit(EvaluationModel):
    layer: RolloutLayer
    status: RolloutLayerStatus
    details: str
    missing_requirements: tuple[str, ...] = ()


class RouteRolloutAudit(EvaluationModel):
    package_id: str
    route_id: str
    rollout_status: RouteRolloutStatus
    readiness: RouteReadinessResult
    layers: tuple[RolloutLayerAudit, ...]

    def layer(self, layer: RolloutLayer) -> RolloutLayerAudit:
        return next(item for item in self.layers if item.layer is layer)
