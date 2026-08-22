"""Repository contract and immutable in-memory Catalog implementation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from app.catalog.models import (
    Anchor,
    CatalogTheme,
    ContentPackage,
    ContentPackageManifest,
    CuratedRoute,
    ExternalPoiBinding,
    EvidenceRelation,
    KnowledgeClaim,
    KnowledgeClaimType,
    KnowledgeEvidence,
    KnowledgeSource,
    KnowledgeVerificationStatus,
    PoiProvider,
    PromotionPolicyStatus,
    Region,
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
        knowledge_sources: Iterable[KnowledgeSource] = (),
        knowledge_claims: Iterable[KnowledgeClaim] = (),
        knowledge_evidence: Iterable[KnowledgeEvidence] = (),
        packages: Iterable[ContentPackage] = (),
    ) -> None:
        self._packages = tuple(packages)
        self._regions = tuple(regions)
        self._themes = tuple(themes)
        self._routes = tuple(routes)
        self._anchors = tuple(anchors)
        self._poi_bindings = tuple(poi_bindings)
        self._knowledge_sources = tuple(knowledge_sources)
        self._knowledge_claims = tuple(knowledge_claims)
        self._knowledge_evidence = tuple(knowledge_evidence)
        self._manifests = tuple(manifests)
        self._regions_by_id = {item.id: item for item in self._regions}
        self._themes_by_id = {item.id: item for item in self._themes}
        self._routes_by_id = {item.id: item for item in self._routes}
        self._anchors_by_id = {item.id: item for item in self._anchors}
        self._poi_bindings_by_id = {
            item.binding_id: item for item in self._poi_bindings
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

    @staticmethod
    def _filter_region(items, region_id: str | None):
        if region_id is None:
            return items
        return tuple(item for item in items if item.region_id == region_id)
