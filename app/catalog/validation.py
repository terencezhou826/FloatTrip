"""Cross-file integrity checks for a complete Catalog snapshot."""

from __future__ import annotations

from collections import Counter

from app.catalog.models import (
    Anchor,
    CatalogTheme,
    ContentPackage,
    CuratedRoute,
    ExternalPoiBinding,
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
    issues: list[str] = []

    _check_duplicate_ids(regions, themes, routes, anchors, poi_bindings, issues)

    region_ids = {item.id for item in regions}
    parents = {item.id: item.parent_id for item in regions}
    theme_ids = {item.id for item in themes}
    anchor_ids = {item.id for item in anchors}
    anchors_by_id = {item.id: item for item in anchors}

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
    issues: list[str],
) -> None:
    typed_items = (
        [("region", item.id) for item in regions]
        + [("theme", item.id) for item in themes]
        + [("route", item.id) for item in routes]
        + [("anchor", item.id) for item in anchors]
        + [("poi_binding", item.binding_id) for item in poi_bindings]
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
