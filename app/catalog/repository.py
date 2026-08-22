"""Repository contract and immutable in-memory Catalog implementation."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Protocol, runtime_checkable

from app.catalog.models import (
    Anchor,
    AnchorCoordinateIdentity,
    CatalogTheme,
    ContentPackage,
    ContentPackageManifest,
    CuratedRoute,
    ExperienceActivity,
    ExperienceBlueprint,
    ExternalPoiBinding,
    EvidenceRelation,
    KnowledgeClaim,
    KnowledgeClaimType,
    KnowledgeEvidence,
    KnowledgeSource,
    KnowledgeVerificationStatus,
    LocalResource,
    LocalResourceType,
    NavigationAccessPoint,
    PoiProvider,
    PromotionPolicyStatus,
    Region,
    ResourceSource,
    ResourceVerificationStatus,
    StoryBlueprint,
    StoryChapter,
    is_resource_recommendation_eligible,
)


@runtime_checkable
class CatalogRepository(Protocol):
    def get_package(self, package_id: str) -> ContentPackage | None: ...

    def get_region(self, region_id: str) -> Region | None: ...

    def list_regions(self) -> tuple[Region, ...]: ...

    def get_theme(self, theme_id: str) -> CatalogTheme | None: ...

    def list_themes(self, region_id: str | None = None) -> tuple[CatalogTheme, ...]: ...

    def get_route(self, route_id: str) -> CuratedRoute | None: ...

    def list_routes(self, region_id: str | None = None) -> tuple[CuratedRoute, ...]: ...

    def get_anchor(self, anchor_id: str) -> Anchor | None: ...

    def list_anchors(self, region_id: str | None = None) -> tuple[Anchor, ...]: ...

    def get_poi_binding(self, binding_id: str) -> ExternalPoiBinding | None: ...

    def list_poi_bindings(
        self, provider: PoiProvider | None = None
    ) -> tuple[ExternalPoiBinding, ...]: ...

    def list_bindings_for_anchor(
        self, anchor_id: str
    ) -> tuple[ExternalPoiBinding, ...]: ...

    def list_verified_bindings_for_anchor(
        self, anchor_id: str
    ) -> tuple[ExternalPoiBinding, ...]: ...

    def get_spatial_identity(
        self, spatial_identity_id: str
    ) -> AnchorCoordinateIdentity | None: ...

    def list_spatial_identities_for_anchor(
        self, anchor_id: str
    ) -> tuple[AnchorCoordinateIdentity, ...]: ...

    def list_verified_spatial_identities_for_anchor(
        self, anchor_id: str
    ) -> tuple[AnchorCoordinateIdentity, ...]: ...

    def get_navigation_access_point(
        self, access_point_id: str
    ) -> NavigationAccessPoint | None: ...

    def list_navigation_access_points_for_anchor(
        self, anchor_id: str
    ) -> tuple[NavigationAccessPoint, ...]: ...

    def list_verified_navigation_access_points_for_anchor(
        self, anchor_id: str
    ) -> tuple[NavigationAccessPoint, ...]: ...

    def list_manifests(self) -> tuple[ContentPackageManifest, ...]: ...

    def get_source(self, source_id: str) -> KnowledgeSource | None: ...

    def list_sources(
        self, region_id: str | None = None
    ) -> tuple[KnowledgeSource, ...]: ...

    def get_claim(self, claim_id: str) -> KnowledgeClaim | None: ...

    def list_claims(
        self,
        *,
        region_id: str | None = None,
        theme_id: str | None = None,
        anchor_id: str | None = None,
        claim_type: KnowledgeClaimType | None = None,
        verification_status: KnowledgeVerificationStatus | None = None,
    ) -> tuple[KnowledgeClaim, ...]: ...

    def get_evidence(self, evidence_id: str) -> KnowledgeEvidence | None: ...

    def list_evidence_for_claim(
        self, claim_id: str
    ) -> tuple[KnowledgeEvidence, ...]: ...

    def is_claim_production_eligible(self, claim_id: str) -> bool: ...

    def get_story(self, story_id: str) -> StoryBlueprint | None: ...

    def list_stories(
        self, route_id: str | None = None
    ) -> tuple[StoryBlueprint, ...]: ...

    def get_story_chapter(self, chapter_id: str) -> StoryChapter | None: ...

    def list_story_chapters(self, story_id: str) -> tuple[StoryChapter, ...]: ...

    def get_experience(self, experience_id: str) -> ExperienceBlueprint | None: ...

    def list_experiences(
        self,
        *,
        route_id: str | None = None,
        story_id: str | None = None,
        theme_id: str | None = None,
        region_id: str | None = None,
    ) -> tuple[ExperienceBlueprint, ...]: ...

    def get_activity(self, activity_id: str) -> ExperienceActivity | None: ...

    def list_activities(
        self, experience_id: str
    ) -> tuple[ExperienceActivity, ...]: ...

    def get_resource_source(self, source_id: str) -> ResourceSource | None: ...

    def get_resource(self, resource_id: str) -> LocalResource | None: ...

    def list_resources(
        self,
        *,
        resource_type: LocalResourceType | None = None,
        region_id: str | None = None,
        anchor_id: str | None = None,
        verification_status: ResourceVerificationStatus | None = None,
    ) -> tuple[LocalResource, ...]: ...

    def is_resource_recommendation_eligible(
        self, resource_id: str, *, as_of: date | None = None
    ) -> bool: ...


class InMemoryCatalogRepository:
    def __init__(
        self,
        *,
        regions: Iterable[Region],
        themes: Iterable[CatalogTheme],
        routes: Iterable[CuratedRoute],
        anchors: Iterable[Anchor],
        manifests: Iterable[ContentPackageManifest],
        poi_bindings: Iterable[ExternalPoiBinding] = (),
        spatial_identities: Iterable[AnchorCoordinateIdentity] = (),
        navigation_access_points: Iterable[NavigationAccessPoint] = (),
        knowledge_sources: Iterable[KnowledgeSource] = (),
        knowledge_claims: Iterable[KnowledgeClaim] = (),
        knowledge_evidence: Iterable[KnowledgeEvidence] = (),
        story_blueprints: Iterable[StoryBlueprint] = (),
        story_chapters: Iterable[StoryChapter] = (),
        experience_blueprints: Iterable[ExperienceBlueprint] = (),
        experience_activities: Iterable[ExperienceActivity] = (),
        resource_sources: Iterable[ResourceSource] = (),
        local_resources: Iterable[LocalResource] = (),
        packages: Iterable[ContentPackage] = (),
    ) -> None:
        self._packages = tuple(packages)
        self._regions = tuple(regions)
        self._themes = tuple(themes)
        self._routes = tuple(routes)
        self._anchors = tuple(anchors)
        self._poi_bindings = tuple(poi_bindings)
        self._spatial_identities = tuple(spatial_identities)
        self._navigation_access_points = tuple(navigation_access_points)
        self._knowledge_sources = tuple(knowledge_sources)
        self._knowledge_claims = tuple(knowledge_claims)
        self._knowledge_evidence = tuple(knowledge_evidence)
        self._story_blueprints = tuple(story_blueprints)
        self._story_chapters = tuple(story_chapters)
        self._experience_blueprints = tuple(experience_blueprints)
        self._experience_activities = tuple(experience_activities)
        self._resource_sources = tuple(resource_sources)
        self._local_resources = tuple(local_resources)
        self._manifests = tuple(manifests)
        self._regions_by_id = {item.id: item for item in self._regions}
        self._themes_by_id = {item.id: item for item in self._themes}
        self._routes_by_id = {item.id: item for item in self._routes}
        self._anchors_by_id = {item.id: item for item in self._anchors}
        self._poi_bindings_by_id = {
            item.binding_id: item for item in self._poi_bindings
        }
        self._spatial_identities_by_id = {
            item.spatial_identity_id: item for item in self._spatial_identities
        }
        self._navigation_access_points_by_id = {
            item.access_point_id: item for item in self._navigation_access_points
        }
        self._knowledge_sources_by_id = {
            item.source_id: item for item in self._knowledge_sources
        }
        self._knowledge_claims_by_id = {
            item.claim_id: item for item in self._knowledge_claims
        }
        self._knowledge_evidence_by_id = {
            item.evidence_id: item for item in self._knowledge_evidence
        }
        self._story_blueprints_by_id = {
            item.story_id: item for item in self._story_blueprints
        }
        self._story_chapters_by_id = {
            item.chapter_id: item for item in self._story_chapters
        }
        self._experience_blueprints_by_id = {
            item.experience_id: item for item in self._experience_blueprints
        }
        self._experience_activities_by_id = {
            item.activity_id: item for item in self._experience_activities
        }
        self._resource_sources_by_id = {
            item.source_id: item for item in self._resource_sources
        }
        self._local_resources_by_id = {
            item.resource_id: item for item in self._local_resources
        }
        self._packages_by_id = {
            item.manifest.package_id: item for item in self._packages
        }

    def get_package(self, package_id: str) -> ContentPackage | None:
        return self._packages_by_id.get(package_id)

    def get_region(self, region_id: str) -> Region | None:
        return self._regions_by_id.get(region_id)

    def list_regions(self) -> tuple[Region, ...]:
        return self._regions

    def get_theme(self, theme_id: str) -> CatalogTheme | None:
        return self._themes_by_id.get(theme_id)

    def list_themes(self, region_id: str | None = None) -> tuple[CatalogTheme, ...]:
        return self._filter_region(self._themes, region_id)

    def get_route(self, route_id: str) -> CuratedRoute | None:
        return self._routes_by_id.get(route_id)

    def list_routes(self, region_id: str | None = None) -> tuple[CuratedRoute, ...]:
        if region_id is None:
            return self._routes
        return tuple(
            route
            for route in self._routes
            if route.primary_region_id == region_id
            or region_id in route.coverage_region_ids
        )

    def get_anchor(self, anchor_id: str) -> Anchor | None:
        return self._anchors_by_id.get(anchor_id)

    def list_anchors(self, region_id: str | None = None) -> tuple[Anchor, ...]:
        return self._filter_region(self._anchors, region_id)

    def get_poi_binding(self, binding_id: str) -> ExternalPoiBinding | None:
        return self._poi_bindings_by_id.get(binding_id)

    def list_poi_bindings(
        self, provider: PoiProvider | None = None
    ) -> tuple[ExternalPoiBinding, ...]:
        if provider is None:
            return self._poi_bindings
        return tuple(item for item in self._poi_bindings if item.provider is provider)

    def list_bindings_for_anchor(
        self, anchor_id: str
    ) -> tuple[ExternalPoiBinding, ...]:
        return tuple(item for item in self._poi_bindings if item.anchor_id == anchor_id)

    def list_verified_bindings_for_anchor(
        self, anchor_id: str
    ) -> tuple[ExternalPoiBinding, ...]:
        return tuple(
            item
            for item in self._poi_bindings
            if item.anchor_id == anchor_id and item.is_runtime_eligible
        )

    def get_spatial_identity(
        self, spatial_identity_id: str
    ) -> AnchorCoordinateIdentity | None:
        return self._spatial_identities_by_id.get(spatial_identity_id)

    def list_spatial_identities_for_anchor(
        self, anchor_id: str
    ) -> tuple[AnchorCoordinateIdentity, ...]:
        return tuple(
            item for item in self._spatial_identities if item.anchor_id == anchor_id
        )

    def list_verified_spatial_identities_for_anchor(
        self, anchor_id: str
    ) -> tuple[AnchorCoordinateIdentity, ...]:
        return tuple(
            item
            for item in self._spatial_identities
            if item.anchor_id == anchor_id and item.is_runtime_eligible
        )

    def get_navigation_access_point(
        self, access_point_id: str
    ) -> NavigationAccessPoint | None:
        return self._navigation_access_points_by_id.get(access_point_id)

    def list_navigation_access_points_for_anchor(
        self, anchor_id: str
    ) -> tuple[NavigationAccessPoint, ...]:
        return tuple(
            item
            for item in self._navigation_access_points
            if item.anchor_id == anchor_id
        )

    def list_verified_navigation_access_points_for_anchor(
        self, anchor_id: str
    ) -> tuple[NavigationAccessPoint, ...]:
        return tuple(
            item
            for item in self._navigation_access_points
            if item.anchor_id == anchor_id and item.is_runtime_eligible
        )

    def list_manifests(self) -> tuple[ContentPackageManifest, ...]:
        return self._manifests

    def get_source(self, source_id: str) -> KnowledgeSource | None:
        return self._knowledge_sources_by_id.get(source_id)

    def list_sources(self, region_id: str | None = None) -> tuple[KnowledgeSource, ...]:
        if region_id is None:
            return self._knowledge_sources
        return tuple(
            source for source in self._knowledge_sources if region_id in source.region_ids
        )

    def get_claim(self, claim_id: str) -> KnowledgeClaim | None:
        return self._knowledge_claims_by_id.get(claim_id)

    def list_claims(
        self,
        *,
        region_id: str | None = None,
        theme_id: str | None = None,
        anchor_id: str | None = None,
        claim_type: KnowledgeClaimType | None = None,
        verification_status: KnowledgeVerificationStatus | None = None,
    ) -> tuple[KnowledgeClaim, ...]:
        return tuple(
            claim
            for claim in self._knowledge_claims
            if (region_id is None or region_id in claim.region_ids)
            and (theme_id is None or theme_id in claim.theme_ids)
            and (anchor_id is None or anchor_id in claim.anchor_ids)
            and (claim_type is None or claim.claim_type is claim_type)
            and (
                verification_status is None
                or claim.verification_status is verification_status
            )
        )

    def get_evidence(self, evidence_id: str) -> KnowledgeEvidence | None:
        return self._knowledge_evidence_by_id.get(evidence_id)

    def list_evidence_for_claim(self, claim_id: str) -> tuple[KnowledgeEvidence, ...]:
        return tuple(
            evidence
            for evidence in self._knowledge_evidence
            if evidence.claim_id == claim_id
        )

    def is_claim_production_eligible(self, claim_id: str) -> bool:
        claim = self.get_claim(claim_id)
        if (
            claim is None
            or claim.verification_status is not KnowledgeVerificationStatus.VERIFIED
        ):
            return False
        if claim.promotion_policy.status in {
            PromotionPolicyStatus.INTERNAL_ONLY,
            PromotionPolicyStatus.FORBIDDEN,
        }:
            return False
        return any(
            evidence.verification_status is KnowledgeVerificationStatus.VERIFIED
            and evidence.evidence_relation is EvidenceRelation.SUPPORTS
            and (source := self.get_source(evidence.source_id)) is not None
            and source.verification_status is KnowledgeVerificationStatus.VERIFIED
            for evidence in self.list_evidence_for_claim(claim_id)
        )

    def get_story(self, story_id: str) -> StoryBlueprint | None:
        return self._story_blueprints_by_id.get(story_id)

    def list_stories(
        self, route_id: str | None = None
    ) -> tuple[StoryBlueprint, ...]:
        if route_id is None:
            return self._story_blueprints
        return tuple(
            story for story in self._story_blueprints if story.route_id == route_id
        )

    def get_story_chapter(self, chapter_id: str) -> StoryChapter | None:
        return self._story_chapters_by_id.get(chapter_id)

    def list_story_chapters(self, story_id: str) -> tuple[StoryChapter, ...]:
        return tuple(
            sorted(
                (
                    chapter
                    for chapter in self._story_chapters
                    if chapter.story_id == story_id
                ),
                key=lambda chapter: (chapter.sequence, chapter.chapter_id),
            )
        )

    def get_experience(self, experience_id: str) -> ExperienceBlueprint | None:
        return self._experience_blueprints_by_id.get(experience_id)

    def list_experiences(
        self,
        *,
        route_id: str | None = None,
        story_id: str | None = None,
        theme_id: str | None = None,
        region_id: str | None = None,
    ) -> tuple[ExperienceBlueprint, ...]:
        return tuple(
            item
            for item in self._experience_blueprints
            if (route_id is None or item.route_id == route_id)
            and (story_id is None or item.story_id == story_id)
            and (theme_id is None or item.theme_id == theme_id)
            and (region_id is None or item.region_id == region_id)
        )

    def get_activity(self, activity_id: str) -> ExperienceActivity | None:
        return self._experience_activities_by_id.get(activity_id)

    def list_activities(
        self, experience_id: str
    ) -> tuple[ExperienceActivity, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._experience_activities
                    if item.experience_id == experience_id
                ),
                key=lambda item: (item.sequence, item.activity_id),
            )
        )

    def get_resource_source(self, source_id: str) -> ResourceSource | None:
        return self._resource_sources_by_id.get(source_id)

    def get_resource(self, resource_id: str) -> LocalResource | None:
        return self._local_resources_by_id.get(resource_id)

    def list_resources(
        self,
        *,
        resource_type: LocalResourceType | None = None,
        region_id: str | None = None,
        anchor_id: str | None = None,
        verification_status: ResourceVerificationStatus | None = None,
    ) -> tuple[LocalResource, ...]:
        return tuple(
            resource
            for resource in self._local_resources
            if (resource_type is None or resource.resource_type is resource_type)
            and (region_id is None or region_id in resource.region_ids)
            and (anchor_id is None or anchor_id in resource.anchor_ids)
            and (
                verification_status is None
                or resource.verification_status is verification_status
            )
        )

    def is_resource_recommendation_eligible(
        self, resource_id: str, *, as_of: date | None = None
    ) -> bool:
        resource = self.get_resource(resource_id)
        if resource is None or not is_resource_recommendation_eligible(
            resource, as_of=as_of
        ):
            return False
        sources = [
            self.get_resource_source(source_id)
            for source_id in resource.source_refs
        ]
        return all(source is not None for source in sources) and any(
            source.verified_at is not None for source in sources if source is not None
        )

    @staticmethod
    def _filter_region(items, region_id: str | None):
        if region_id is None:
            return items
        return tuple(item for item in items if item.region_id == region_id)
