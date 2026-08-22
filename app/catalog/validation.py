"""Cross-file integrity checks for a complete Catalog snapshot."""

from __future__ import annotations

from collections import Counter

from app.catalog.models import (
    Anchor,
    CatalogTheme,
    ContentPackage,
    CuratedRoute,
    EvidenceRelation,
    ExternalPoiBinding,
    KnowledgeClaim,
    KnowledgeEvidence,
    KnowledgeSource,
    KnowledgeVerificationStatus,
    Region,
)


SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0"})


class CatalogValidationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = tuple(issues)
        super().__init__("catalog validation failed: " + "; ".join(issues))


def validate_catalog(regions: list[Region], packages: list[ContentPackage]) -> None:
    themes = [item for package in packages for item in package.themes]
    routes = [item for package in packages for item in package.routes]
    anchors = [item for package in packages for item in package.anchors]
    poi_bindings = [item for package in packages for item in package.poi_bindings]
    knowledge_sources = [
        item for package in packages for item in package.knowledge_sources
    ]
    knowledge_claims = [
        item for package in packages for item in package.knowledge_claims
    ]
    knowledge_evidence = [
        item for package in packages for item in package.knowledge_evidence
    ]
    issues: list[str] = []

    _check_duplicate_ids(
        regions,
        themes,
        routes,
        anchors,
        poi_bindings,
        knowledge_sources,
        knowledge_claims,
        knowledge_evidence,
        issues,
    )

    region_ids = {item.id for item in regions}
    parents = {item.id: item.parent_id for item in regions}
    theme_ids = {item.id for item in themes}
    anchor_ids = {item.id for item in anchors}
    anchors_by_id = {item.id: item for item in anchors}
    source_ids = {item.source_id for item in knowledge_sources}
    claim_ids = {item.claim_id for item in knowledge_claims}
    sources_by_id = {item.source_id: item for item in knowledge_sources}

    for region in regions:
        if region.parent_id and region.parent_id not in region_ids:
            issues.append(f"region {region.id} has missing parent {region.parent_id}")

    _check_region_cycles(regions, issues)

    package_ids = [package.manifest.package_id for package in packages]
    for duplicate in _duplicates(package_ids):
        issues.append(f"duplicate package_id {duplicate}")

    for package in packages:
        manifest = package.manifest
        if manifest.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            issues.append(
                f"package {manifest.package_id} uses unsupported schema_version "
                f"{manifest.schema_version}"
            )
        if manifest.region_id not in region_ids:
            issues.append(
                f"package {manifest.package_id} references missing region {manifest.region_id}"
            )

    for theme in themes:
        if theme.region_id not in region_ids:
            issues.append(f"theme {theme.id} references missing region {theme.region_id}")

    for anchor in anchors:
        if anchor.region_id not in region_ids:
            issues.append(f"anchor {anchor.id} references missing region {anchor.region_id}")

    for binding in poi_bindings:
        if binding.anchor_id not in anchor_ids:
            issues.append(
                f"binding {binding.binding_id} references missing anchor "
                f"{binding.anchor_id}"
            )

    for source in knowledge_sources:
        for region_id in source.region_ids:
            if region_id not in region_ids:
                issues.append(
                    f"knowledge source {source.source_id} references missing region "
                    f"{region_id}"
                )

    for claim in knowledge_claims:
        for region_id in claim.region_ids:
            if region_id not in region_ids:
                issues.append(
                    f"knowledge claim {claim.claim_id} references missing region "
                    f"{region_id}"
                )
        for theme_id in claim.theme_ids:
            if theme_id not in theme_ids:
                issues.append(
                    f"knowledge claim {claim.claim_id} references missing theme "
                    f"{theme_id}"
                )
        for anchor_id in claim.anchor_ids:
            if anchor_id not in anchor_ids:
                issues.append(
                    f"knowledge claim {claim.claim_id} references missing anchor "
                    f"{anchor_id}"
                )

    for evidence in knowledge_evidence:
        if evidence.claim_id not in claim_ids:
            issues.append(
                f"knowledge evidence {evidence.evidence_id} references missing claim "
                f"{evidence.claim_id}"
            )
        if evidence.source_id not in source_ids:
            issues.append(
                f"knowledge evidence {evidence.evidence_id} references missing source "
                f"{evidence.source_id}"
            )

    supported_verified_claim_ids = {
        evidence.claim_id
        for evidence in knowledge_evidence
        if evidence.verification_status is KnowledgeVerificationStatus.VERIFIED
        and evidence.evidence_relation is EvidenceRelation.SUPPORTS
        and (
            source := sources_by_id.get(evidence.source_id)
        ) is not None
        and source.verification_status is KnowledgeVerificationStatus.VERIFIED
    }
    for claim in knowledge_claims:
        if (
            claim.verification_status is KnowledgeVerificationStatus.VERIFIED
            and claim.claim_id not in supported_verified_claim_ids
        ):
            issues.append(
                f"verified knowledge claim {claim.claim_id} has no verified supporting "
                "evidence from a verified source"
            )

    coverage = calculate_evidence_coverage(
        knowledge_claims,
        knowledge_evidence,
        verified_source_ids={
            source.source_id
            for source in knowledge_sources
            if source.verification_status is KnowledgeVerificationStatus.VERIFIED
        },
    )
    if coverage < 1.0:
        issues.append(
            f"verified knowledge claim evidence coverage is {coverage:.3f}, not 1.000"
        )

    binding_identities: dict[tuple[str, str], set[str]] = {}
    for binding in poi_bindings:
        identity = (binding.provider.value, binding.external_poi_id)
        binding_identities.setdefault(identity, set()).add(binding.anchor_id)
    for (provider, external_poi_id), bound_anchor_ids in sorted(
        binding_identities.items()
    ):
        if len(bound_anchor_ids) > 1:
            issues.append(
                f"provider identity {provider}:{external_poi_id} has conflicting anchors "
                f"{', '.join(sorted(bound_anchor_ids))}"
            )

    for route in routes:
        if route.primary_region_id not in region_ids:
            issues.append(
                f"route {route.id} references missing primary region "
                f"{route.primary_region_id}"
            )
        for coverage_id in route.coverage_region_ids:
            if coverage_id not in region_ids:
                issues.append(
                    f"route {route.id} references missing coverage region {coverage_id}"
                )
        if route.primary_region_id in region_ids:
            incompatible = [
                coverage_id
                for coverage_id in route.coverage_region_ids
                if coverage_id in region_ids
                and not is_same_or_descendant(
                    coverage_id, route.primary_region_id, parents
                )
            ]
            if incompatible:
                issues.append(
                    f"route {route.id} primary region {route.primary_region_id} "
                    f"is incompatible with coverage {', '.join(incompatible)}"
                )
        if route.theme_id not in theme_ids:
            issues.append(f"route {route.id} references missing theme {route.theme_id}")
        for anchor_id in route.anchor_ids:
            if anchor_id not in anchor_ids:
                issues.append(f"route {route.id} references missing anchor {anchor_id}")
                continue
            anchor = anchors_by_id[anchor_id]
            covered = any(
                coverage_id in region_ids
                and is_same_or_descendant(anchor.region_id, coverage_id, parents)
                for coverage_id in route.coverage_region_ids
            )
            if not covered:
                issues.append(
                    f"route {route.id} anchor {anchor_id} region {anchor.region_id} "
                    "is outside route coverage"
                )

    if issues:
        raise CatalogValidationError(issues)


def _check_duplicate_ids(
    regions: list[Region],
    themes: list[CatalogTheme],
    routes: list[CuratedRoute],
    anchors: list[Anchor],
    poi_bindings: list[ExternalPoiBinding],
    knowledge_sources: list[KnowledgeSource],
    knowledge_claims: list[KnowledgeClaim],
    knowledge_evidence: list[KnowledgeEvidence],
    issues: list[str],
) -> None:
    typed_items = (
        [("region", item.id) for item in regions]
        + [("theme", item.id) for item in themes]
        + [("route", item.id) for item in routes]
        + [("anchor", item.id) for item in anchors]
        + [("poi_binding", item.binding_id) for item in poi_bindings]
        + [("knowledge_source", item.source_id) for item in knowledge_sources]
        + [("knowledge_claim", item.claim_id) for item in knowledge_claims]
        + [("knowledge_evidence", item.evidence_id) for item in knowledge_evidence]
    )
    counts = Counter(item_id for _, item_id in typed_items)
    for duplicate in sorted(item_id for item_id, count in counts.items() if count > 1):
        kinds = sorted(kind for kind, item_id in typed_items if item_id == duplicate)
        issues.append(f"duplicate id {duplicate} ({', '.join(kinds)})")


def _check_region_cycles(regions: list[Region], issues: list[str]) -> None:
    parents = {item.id: item.parent_id for item in regions}
    for region in regions:
        seen: set[str] = set()
        current: str | None = region.id
        while current is not None and current in parents:
            if current in seen:
                issues.append(f"region parent cycle includes {current}")
                break
            seen.add(current)
            current = parents[current]


def is_same_or_descendant(
    region_id: str,
    ancestor_id: str,
    parents: dict[str, str | None],
) -> bool:
    current: str | None = region_id
    visited: set[str] = set()
    while current is not None and current not in visited:
        if current == ancestor_id:
            return True
        visited.add(current)
        current = parents.get(current)
    return False


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def calculate_evidence_coverage(
    claims: list[KnowledgeClaim],
    evidence: list[KnowledgeEvidence],
    *,
    verified_source_ids: set[str],
) -> float:
    verified_claim_ids = {
        claim.claim_id
        for claim in claims
        if claim.verification_status is KnowledgeVerificationStatus.VERIFIED
    }
    if not verified_claim_ids:
        return 1.0
    covered_claim_ids = {
        item.claim_id
        for item in evidence
        if item.claim_id in verified_claim_ids
        and item.source_id in verified_source_ids
        and item.verification_status is KnowledgeVerificationStatus.VERIFIED
        and item.evidence_relation is EvidenceRelation.SUPPORTS
    }
    return len(covered_claim_ids) / len(verified_claim_ids)
