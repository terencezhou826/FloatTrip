"""Catalog-driven product views and truthful route capabilities."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from app.catalog.models import (
    ExperienceVerificationStatus,
    KnowledgeVerificationStatus,
    StoryVerificationStatus,
)
from app.catalog.repository import CatalogRepository
from app.catalog.spatial import project_anchor_spatial_resolution


class ProductAvailability(StrEnum):
    READY = "ready"
    PREVIEW = "preview"
    COMING_SOON = "coming_soon"


class CatalogProductService:
    """Build browser-safe views without mutating or duplicating Catalog data."""

    def __init__(self, repository: CatalogRepository) -> None:
        self.repository = repository

    def list_collections(self, *, region_id: str | None = None) -> list[dict[str, Any]]:
        collections: list[dict[str, Any]] = []
        for manifest in self.repository.list_manifests():
            if not manifest.enabled:
                continue
            if region_id and not self._region_contains(region_id, manifest.region_id):
                continue
            package = self.repository.get_package(manifest.package_id)
            if package is None:
                continue
            region = self.repository.get_region(manifest.region_id)
            if region is None:
                continue
            routes = [self._route_view(route, manifest.package_id) for route in package.routes]
            collections.append(
                {
                    "package_id": manifest.package_id,
                    "schema_version": manifest.schema_version,
                    "content_version": manifest.content_version,
                    "region": self._region_view(region),
                    "routes": routes,
                }
            )
        return collections

    def get_route(self, package_id: str, route_id: str) -> dict[str, Any] | None:
        package = self.repository.get_package(package_id)
        if package is None or not package.manifest.enabled:
            return None
        route = next((item for item in package.routes if item.id == route_id), None)
        if route is None:
            return None
        return self._route_view(route, package_id, include_preview=True)

    def find_route(self, route_id: str) -> dict[str, Any] | None:
        matches = []
        for manifest in self.repository.list_manifests():
            if not manifest.enabled:
                continue
            package = self.repository.get_package(manifest.package_id)
            if package is None:
                continue
            if any(route.id == route_id for route in package.routes):
                matches.append(manifest.package_id)
        if len(matches) != 1:
            return None
        return self.get_route(matches[0], route_id)

    def _route_view(
        self,
        route,
        package_id: str,
        *,
        include_preview: bool = False,
    ) -> dict[str, Any]:
        theme = self.repository.get_theme(route.theme_id)
        primary_region = self.repository.get_region(route.primary_region_id)
        coverage_regions = [
            region
            for region_id in route.coverage_region_ids
            if (region := self.repository.get_region(region_id)) is not None
        ]
        anchors = []
        for anchor_id in route.anchor_ids:
            anchor = self.repository.get_anchor(anchor_id)
            if anchor is None:
                continue
            anchors.append(
                {
                    "id": anchor.id,
                    "name": anchor.name,
                    "region_id": anchor.region_id,
                    "mandatory": anchor.id in route.mandatory_anchor_ids,
                }
            )
        capabilities, spatial_details = self._capabilities(route)
        required_capabilities = (
            "catalog_available",
            "planning_available",
            "knowledge_available",
            "story_available",
            "experience_available",
        )
        if all(capabilities[key] for key in required_capabilities):
            availability = ProductAvailability.READY
        elif any(capabilities[key] for key in required_capabilities[1:]):
            availability = ProductAvailability.PREVIEW
        else:
            availability = ProductAvailability.COMING_SOON
        experiences = [
            item
            for item in self.repository.list_experiences(route_id=route.id)
            if item.enabled
            and item.verification_status is ExperienceVerificationStatus.VERIFIED
        ]
        result: dict[str, Any] = {
            "package_id": package_id,
            "id": route.id,
            "name": route.name,
            "theme": (
                {"id": theme.id, "name": theme.name, "type": theme.type.value}
                if theme is not None
                else None
            ),
            "primary_region": (
                self._region_view(primary_region) if primary_region is not None else None
            ),
            "coverage_regions": [self._region_view(item) for item in coverage_regions],
            "region_hierarchy": (
                self._region_hierarchy(primary_region.id) if primary_region else []
            ),
            "anchors": anchors,
            "capabilities": capabilities,
            "spatial_details": spatial_details,
            "location_disclosures": [
                item["disclosure_text"]
                for item in spatial_details
                if item["disclosure_required"] and item["disclosure_text"]
            ],
            "availability": availability.value,
            "experience_types": sorted({item.experience_type.value for item in experiences}),
        }
        if include_preview:
            result["cultural_preview"] = self._cultural_preview(route)
        return result

    def _capabilities(self, route) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        spatial = [
            project_anchor_spatial_resolution(self.repository, anchor_id)
            for anchor_id in route.mandatory_anchor_ids
        ]
        planning_available = bool(spatial) and all(
            item.planning_available for item in spatial
        )
        claims = [
            claim
            for claim in self.repository.list_claims()
            if (
                route.theme_id in claim.theme_ids
                or bool(set(route.anchor_ids).intersection(claim.anchor_ids))
            )
            and self.repository.is_claim_production_eligible(claim.claim_id)
        ]
        knowledge_available = bool(claims)
        stories = [
            item
            for item in self.repository.list_stories(route.id)
            if item.enabled
            and item.verification_status is StoryVerificationStatus.VERIFIED
        ]
        story_available = bool(stories)
        experiences = [
            item
            for item in self.repository.list_experiences(route_id=route.id)
            if item.enabled
            and item.verification_status is ExperienceVerificationStatus.VERIFIED
            and any(story.story_id == item.story_id for story in stories)
        ]
        experience_available = bool(experiences)
        levels = {
            item.resolution_level.value
            for item in spatial
            if item.resolution_level is not None
        }
        spatial_resolution = next(iter(levels)) if len(levels) == 1 else (
            "mixed" if levels else None
        )
        capabilities: dict[str, Any] = {
            "catalog_available": True,
            "planning_available": planning_available,
            "knowledge_available": knowledge_available,
            "story_available": story_available,
            "experience_available": experience_available,
            "resources_available": planning_available and experience_available,
            "spatial_resolution": spatial_resolution,
            "spatial_degraded": any(item.degraded for item in spatial),
            "location_disclosure_required": any(
                item.disclosure_required for item in spatial
            ),
            "exact_anchor_location_available": bool(spatial) and all(
                item.exact_anchor_location_available for item in spatial
            ),
            "navigation_available": bool(spatial) and all(
                item.navigation_available for item in spatial
            ),
        }
        return capabilities, [item.model_dump(mode="json") for item in spatial]

    def _cultural_preview(self, route) -> list[dict[str, Any]]:
        previews: list[dict[str, Any]] = []
        for claim in self.repository.list_claims():
            if len(previews) >= 3:
                break
            if not (
                route.theme_id in claim.theme_ids
                or bool(set(route.anchor_ids).intersection(claim.anchor_ids))
            ):
                continue
            if not self.repository.is_claim_production_eligible(claim.claim_id):
                continue
            citations = []
            for evidence in self.repository.list_evidence_for_claim(claim.claim_id):
                source = self.repository.get_source(evidence.source_id)
                if (
                    source is None
                    or source.verification_status is not KnowledgeVerificationStatus.VERIFIED
                ):
                    continue
                citations.append(
                    {
                        "source_id": source.source_id,
                        "source_title": source.title,
                        "source_type": source.source_type.value,
                        "url": source.url,
                        "locator": evidence.locator.model_dump(mode="json", exclude_none=True),
                        "quote_excerpt": evidence.quote_excerpt,
                    }
                )
            previews.append(
                {
                    "claim_id": claim.claim_id,
                    "text": claim.promotion_policy.approved_wording or claim.statement,
                    "claim_type": claim.claim_type.value,
                    "required_qualifier": claim.promotion_policy.required_qualifier,
                    "citations": citations,
                }
            )
        return previews

    def _region_hierarchy(self, region_id: str) -> list[dict[str, Any]]:
        result = []
        seen: set[str] = set()
        current = self.repository.get_region(region_id)
        while current is not None and current.id not in seen:
            seen.add(current.id)
            result.append(self._region_view(current))
            current = (
                self.repository.get_region(current.parent_id)
                if current.parent_id is not None
                else None
            )
        return list(reversed(result))

    def _region_contains(self, ancestor_id: str, region_id: str) -> bool:
        current = self.repository.get_region(region_id)
        seen: set[str] = set()
        while current is not None and current.id not in seen:
            if current.id == ancestor_id:
                return True
            seen.add(current.id)
            current = (
                self.repository.get_region(current.parent_id)
                if current.parent_id is not None
                else None
            )
        return False

    @staticmethod
    def _region_view(region) -> dict[str, Any]:
        return {
            "id": region.id,
            "name": region.name,
            "region_type": region.region_type.value,
            "admin_code": region.admin_code,
        }
