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
            packages=packages,
            manifests=[package.manifest for package in enabled],
            themes=[item for package in enabled for item in package.themes],
            routes=[item for package in enabled for item in package.routes],
            anchors=[item for package in enabled for item in package.anchors],
            poi_bindings=[item for package in enabled for item in package.poi_bindings],
            knowledge_sources=[
                item for package in enabled for item in package.knowledge_sources
            ],
            knowledge_claims=[
                item for package in enabled for item in package.knowledge_claims
            ],
            knowledge_evidence=[
                item for package in enabled for item in package.knowledge_evidence
            ],
            story_blueprints=[
                item for package in enabled for item in package.story_blueprints
            ],
            story_chapters=[
                item for package in enabled for item in package.story_chapters
            ],
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
                "poi_bindings": self._read_optional_collection(
                    directory / "poi_bindings.json", "poi_bindings"
                ),
            }
            package_payload.update(self._load_knowledge(directory / "knowledge"))
            package_payload.update(self._load_stories(directory / "stories"))
            packages.append(ContentPackage.model_validate(package_payload))
        return packages

    def _load_knowledge(self, knowledge_root: Path) -> dict[str, list[Any]]:
        collections: dict[str, list[Any]] = {
            "knowledge_sources": [],
            "knowledge_claims": [],
            "knowledge_evidence": [],
        }
        key_map = {
            "sources": "knowledge_sources",
            "claims": "knowledge_claims",
            "evidence": "knowledge_evidence",
        }
        paths = (
            sorted(knowledge_root.rglob("*.json"))
            if knowledge_root.is_dir()
            else []
        )
        for path in paths:
            payload = self._read_json(path)
            if not isinstance(payload, dict):
                raise CatalogLoadError(f"{path} must contain one knowledge collection")
            recognized = [key for key in key_map if key in payload]
            if len(recognized) != 1 or len(payload) != 1:
                raise CatalogLoadError(
                    f"{path} must contain exactly one of: {', '.join(key_map)}"
                )
            key = recognized[0]
            if not isinstance(payload[key], list):
                raise CatalogLoadError(f"{path} must contain a {key} list")
            collections[key_map[key]].extend(payload[key])
        return collections

    def _load_stories(self, stories_root: Path) -> dict[str, list[Any]]:
        collections: dict[str, list[Any]] = {
            "story_blueprints": [],
            "story_chapters": [],
        }
        key_map = {
            "blueprints": "story_blueprints",
            "chapters": "story_chapters",
        }
        paths = sorted(stories_root.rglob("*.json")) if stories_root.is_dir() else []
        for path in paths:
            payload = self._read_json(path)
            if not isinstance(payload, dict):
                raise CatalogLoadError(f"{path} must contain one story collection")
            recognized = [key for key in key_map if key in payload]
            if len(recognized) != 1 or len(payload) != 1:
                raise CatalogLoadError(
                    f"{path} must contain exactly one of: {', '.join(key_map)}"
                )
            key = recognized[0]
            if not isinstance(payload[key], list):
                raise CatalogLoadError(f"{path} must contain a {key} list")
            collections[key_map[key]].extend(payload[key])
        return collections

    def _read_collection(self, path: Path, key: str) -> Any:
        payload = self._read_json(path)
        if not isinstance(payload, dict) or key not in payload:
            raise CatalogLoadError(f"{path} must contain a {key} list")
        return payload[key]

    def _read_optional_collection(self, path: Path, key: str) -> Any:
        if not path.is_file():
            return []
        return self._read_collection(path, key)

    @staticmethod
    def _read_json(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
