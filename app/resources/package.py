"""Immutable LocalResourcePackage assembly and integrity rules."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from pydantic import Field, StrictBool, model_validator

from app.catalog.models import (
    CatalogModel,
    CommercialRelationship,
    ResourceVerificationStatus,
    StableId,
)
from app.knowledge.models import CatalogVersionSnapshot
from app.resources.models import ResourceProvenanceType
from app.resources.recommendation import (
    ContextualRelation,
    RecommendationCandidate,
    RecommendationMetrics,
    RecommendationResult,
    ResourceRecommendation,
)


class ResourceContextBinding(CatalogModel):
    resource_id: StableId
    related_itinerary_stop_ids: tuple[str, ...]
    related_story_chapter_ids: tuple[StableId, ...]
    related_experience_activity_ids: tuple[StableId, ...]
    contextual_relation: ContextualRelation
    cultural_identity: StrictBool = False

    @model_validator(mode="after")
    def reject_cultural_identity_claim(self) -> "ResourceContextBinding":
        if self.cultural_identity:
            raise ValueError("commercial context cannot assert cultural identity")
        return self


class ResourceDisclosure(CatalogModel):
    resource_id: StableId
    commercial_relationship: CommercialRelationship
    disclosure_text: str = Field(min_length=1, max_length=500)


class LocalResourcePackage(CatalogModel):
    resource_package_id: StableId
    package_id: StableId
    schema_version: str = Field(pattern=r"^\d+\.\d+$")
    content_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    run_id: str = Field(min_length=1, max_length=256)
    itinerary_id: str = Field(min_length=1, max_length=256)
    story_package_id: StableId
    story_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    experience_package_id: StableId
    experience_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    resources: tuple[RecommendationCandidate, ...]
    recommendations: tuple[ResourceRecommendation, ...]
    resource_bindings: tuple[ResourceContextBinding, ...]
    disclosures: tuple[ResourceDisclosure, ...]
    warnings: tuple[str, ...]
    metrics: RecommendationMetrics
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @model_validator(mode="after")
    def validate_package_contract(self) -> "LocalResourcePackage":
        resources = {item.resource_id: item for item in self.resources}
        if len(resources) != len(self.resources):
            raise ValueError("LocalResourcePackage contains duplicate resources")
        recommendations = {
            item.resource_id: item for item in self.recommendations
        }
        if len(recommendations) != len(self.recommendations):
            raise ValueError("LocalResourcePackage contains duplicate recommendations")
        if not set(recommendations).issubset(resources):
            raise ValueError("recommendation references missing resource")
        for resource_id, recommendation in recommendations.items():
            resource = resources[resource_id]
            if recommendation.provider is not resource.provider or (
                recommendation.external_poi_id != resource.external_poi_id
            ):
                raise ValueError("recommendation Provider identity mismatch")
        for resource in self.resources:
            if (
                resource.provenance_type is ResourceProvenanceType.CURATED_CATALOG
                and resource.verification_status
                is not ResourceVerificationStatus.VERIFIED
            ):
                raise ValueError("unverified curated resource in formal package")
        bindings = {item.resource_id: item for item in self.resource_bindings}
        if set(bindings) != set(recommendations):
            raise ValueError("resource bindings must cover recommendations exactly")
        disclosures = {item.resource_id: item for item in self.disclosures}
        expected_disclosures = {
            item.resource_id
            for item in self.recommendations
            if item.commercial_relationship
            in {CommercialRelationship.PARTNER, CommercialRelationship.SPONSORED}
        }
        if set(disclosures) != expected_disclosures:
            raise ValueError("commercial disclosures must cover commercial resources")
        if any(value != 0 for value in self.metrics.model_dump().values()):
            raise ValueError("formal LocalResourcePackage hard metrics must be zero")
        return self


def local_resource_package_hash(package: LocalResourcePackage) -> str:
    payload = package.model_dump(mode="json", exclude={"snapshot_hash"})
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_local_resource_package(
    *,
    catalog_version: CatalogVersionSnapshot,
    run_id: str,
    itinerary_id: str,
    story_package_id: str,
    story_snapshot_hash: str,
    experience_package_id: str,
    experience_snapshot_hash: str,
    resources: tuple[RecommendationCandidate, ...],
    result: RecommendationResult,
    created_at: datetime | None = None,
) -> LocalResourcePackage:
    recommendations = result.recommendations
    bindings = tuple(
        ResourceContextBinding(
            resource_id=item.resource_id,
            related_itinerary_stop_ids=item.related_itinerary_stop_ids,
            related_story_chapter_ids=item.related_story_chapter_ids,
            related_experience_activity_ids=item.related_experience_activity_ids,
            contextual_relation=item.contextual_relation,
            cultural_identity=False,
        )
        for item in recommendations
    )
    disclosures = tuple(
        ResourceDisclosure(
            resource_id=item.resource_id,
            commercial_relationship=item.commercial_relationship,
            disclosure_text=item.disclosure,
        )
        for item in recommendations
        if item.commercial_relationship
        in {CommercialRelationship.PARTNER, CommercialRelationship.SPONSORED}
    )
    identity_seed = "|".join(
        (
            run_id,
            itinerary_id,
            story_package_id,
            experience_package_id,
            *(item.resource_id for item in resources),
        )
    )
    package_digest = hashlib.sha256(identity_seed.encode("utf-8")).hexdigest()[:24]
    package = LocalResourcePackage(
        resource_package_id=f"resource-package.{package_digest}",
        package_id=catalog_version.package_id,
        schema_version=catalog_version.schema_version,
        content_version=catalog_version.content_version,
        run_id=run_id,
        itinerary_id=itinerary_id,
        story_package_id=story_package_id,
        story_snapshot_hash=story_snapshot_hash,
        experience_package_id=experience_package_id,
        experience_snapshot_hash=experience_snapshot_hash,
        resources=resources,
        recommendations=recommendations,
        resource_bindings=bindings,
        disclosures=disclosures,
        warnings=result.warnings,
        metrics=result.metrics,
        snapshot_hash="0" * 64,
        created_at=created_at or datetime.now(timezone.utc),
    )
    return package.model_copy(
        update={"snapshot_hash": local_resource_package_hash(package)}
    )
