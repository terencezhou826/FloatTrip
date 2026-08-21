"""Generic JSON loader for registry data and content packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.catalog.models import Anchor, CatalogTheme, ContentPackage, CuratedRoute, Region
from app.catalog.repository import InMemoryCatalogRepository
from app.catalog.validation import CatalogValidationError, validate_catalog


class CatalogLoadError(ValueError):
    pass


class FileCatalogLoader:
    def __init__(self, catalog_root: str | Path):
        self.catalog_root = Path(catalog_root)

    def load(self) -> InMemoryCatalogRepository:
        try:
            regions = self._load_regions()
            packages = self._load_packages()
            validate_catalog(regions, packages)
        except CatalogValidationError:
            raise
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise CatalogLoadError(str(exc)) from exc

        enabled = [package for package in packages if package.manifest.enabled]
        return InMemoryCatalogRepository(
            regions=regions,
            manifests=[package.manifest for package in enabled],
            themes=[item for package in enabled for item in package.themes],
            routes=[item for package in enabled for item in package.routes],
            anchors=[item for package in enabled for item in package.anchors],
        )

    def _load_regions(self) -> list[Region]:
        registry_root = self.catalog_root / "registry" / "regions"
        paths = sorted(registry_root.rglob("*.json")) if registry_root.is_dir() else []
        if not paths:
            raise CatalogLoadError(f"no region registry files found under {registry_root}")
        adapter = TypeAdapter(list[Region])
        regions: list[Region] = []
        for path in paths:
            payload = self._read_json(path)
            if not isinstance(payload, dict) or "regions" not in payload:
                raise CatalogLoadError(f"{path} must contain a regions list")
            regions.extend(adapter.validate_python(payload["regions"]))
        return regions

    def _load_packages(self) -> list[ContentPackage]:
        packages_root = self.catalog_root / "packages"
        manifests = sorted(packages_root.rglob("manifest.json")) if packages_root.is_dir() else []
        packages: list[ContentPackage] = []
        for manifest_path in manifests:
            directory = manifest_path.parent
            package_payload: dict[str, Any] = {
                "manifest": self._read_json(manifest_path),
                "themes": self._read_collection(directory / "themes.json", "themes"),
                "routes": self._read_collection(directory / "routes.json", "routes"),
                "anchors": self._read_collection(directory / "anchors.json", "anchors"),
            }
            packages.append(ContentPackage.model_validate(package_payload))
        return packages

    def _read_collection(self, path: Path, key: str) -> Any:
        payload = self._read_json(path)
        if not isinstance(payload, dict) or key not in payload:
            raise CatalogLoadError(f"{path} must contain a {key} list")
        return payload[key]

    @staticmethod
    def _read_json(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
