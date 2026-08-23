from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.loader import CatalogLoadError, FileCatalogLoader
from app.catalog.models import CatalogTheme, RegionType, ThemeType
from app.catalog.repository import CatalogRepository
from app.catalog.validation import CatalogValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"


@pytest.fixture(scope="module")
def catalog():
    return FileCatalogLoader(CATALOG_ROOT).load()


def _catalog_copy(tmp_path: Path) -> Path:
    target = tmp_path / "catalog"
    shutil.copytree(CATALOG_ROOT, target)
    return target


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_region_tree_loads_with_shanxi_as_registry_root(catalog):
    regions = {item.id: item for item in catalog.list_regions()}

    assert len(regions) == 6
    assert regions["cn.shanxi"].parent_id is None
    assert regions["cn.shanxi.changzhi"].parent_id == "cn.shanxi"


def test_region_type_enum_contains_supported_administrative_levels():
    assert {item.value for item in RegionType} == {
        "province",
        "prefecture_city",
        "county",
        "district",
        "county_level_city",
    }


def test_region_types_and_unconfirmed_admin_codes_load(catalog):
    regions = {item.id: item for item in catalog.list_regions()}

    assert {region_id: region.region_type for region_id, region in regions.items()} == {
        "cn.shanxi": RegionType.PROVINCE,
        "cn.shanxi.changzhi": RegionType.PREFECTURE_CITY,
        "cn.shanxi.changzhi.changzi": RegionType.COUNTY,
        "cn.shanxi.changzhi.shangdang": RegionType.DISTRICT,
        "cn.shanxi.changzhi.luzhou": RegionType.DISTRICT,
        "cn.shanxi.changzhi.tunliu": RegionType.DISTRICT,
    }
    assert regions["cn.shanxi.changzhi.shangdang"].admin_code == "140404"
    assert all(
        region.admin_code is None
        for region_id, region in regions.items()
        if region_id != "cn.shanxi.changzhi.shangdang"
    )


def test_four_changzhi_subregions_load(catalog):
    expected = {
        "cn.shanxi.changzhi.changzi": "长子县",
        "cn.shanxi.changzhi.shangdang": "上党区",
        "cn.shanxi.changzhi.luzhou": "潞州区",
        "cn.shanxi.changzhi.tunliu": "屯留区",
    }

    assert {region_id: catalog.get_region(region_id).name for region_id in expected} == expected


def test_four_catalog_themes_load(catalog):
    themes = catalog.list_themes()

    assert len(themes) == 4
    assert {item.id for item in themes} == {
        "changzhi.jingwei",
        "changzhi.nuwa",
        "changzhi.shennong",
        "changzhi.houyi",
    }
    assert {item.type for item in themes} == {ThemeType.MYTHOLOGY}


def test_theme_type_enum_is_not_bound_to_mythology():
    assert {item.value for item in ThemeType} == {
        "mythology",
        "historical_figure",
        "ancient_architecture",
        "red_culture",
        "folk_custom",
        "food",
        "nature",
        "heritage",
        "custom",
    }


def test_custom_type_is_reserved_for_custom_themes():
    with pytest.raises(ValidationError, match="custom themes require custom_type"):
        CatalogTheme(
            id="sample.custom",
            type=ThemeType.CUSTOM,
            name="Sample",
            region_id="sample.region",
        )

    with pytest.raises(ValidationError, match="only valid for custom themes"):
        CatalogTheme(
            id="sample.nature",
            type=ThemeType.NATURE,
            name="Sample",
            region_id="sample.region",
            custom_type="not-allowed",
        )


def test_four_curated_routes_load(catalog):
    routes = catalog.list_routes()

    assert len(routes) == 4
    assert {item.name for item in routes} == {
        "精卫填海·发鸠山探秘",
        "女娲补天·天台山寻迹",
        "神农尝草·老顶山农耕溯源",
        "羿射九日·老爷山揽胜",
    }
    assert {
        (route.primary_region_id, tuple(route.coverage_region_ids)) for route in routes
    } == {
        ("cn.shanxi.changzhi.changzi", ("cn.shanxi.changzhi.changzi",)),
        ("cn.shanxi.changzhi.shangdang", ("cn.shanxi.changzhi.shangdang",)),
        ("cn.shanxi.changzhi.luzhou", ("cn.shanxi.changzhi.luzhou",)),
        ("cn.shanxi.changzhi.tunliu", ("cn.shanxi.changzhi.tunliu",)),
    }


def test_each_route_has_its_single_mandatory_anchor(catalog):
    routes = catalog.list_routes()

    assert len(catalog.list_anchors()) == 4
    assert all(len(route.mandatory_anchor_ids) == 1 for route in routes)
    assert {
        catalog.get_anchor(route.mandatory_anchor_ids[0]).name for route in routes
    } == {"发鸠山", "天台山", "老顶山", "老爷山"}


def test_manifest_loads_and_repository_contract_is_satisfied(catalog):
    manifests = catalog.list_manifests()

    assert isinstance(catalog, CatalogRepository)
    assert len(manifests) == 1
    assert manifests[0].model_dump() == {
        "package_id": "shanxi.changzhi",
        "schema_version": "1.0",
        "content_version": "0.6.0",
        "region_id": "cn.shanxi.changzhi",
        "enabled": True,
    }


def test_missing_region_parent_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "registry" / "regions" / "cn" / "shanxi" / "regions.json"
    payload = _json(path)
    payload["regions"][1]["parent_id"] = "cn.missing"
    _write_json(path, payload)

    with pytest.raises(CatalogValidationError, match="missing parent"):
        FileCatalogLoader(root).load()


def test_invalid_region_type_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "registry" / "regions" / "cn" / "shanxi" / "regions.json"
    payload = _json(path)
    payload["regions"][0]["region_type"] = "special_region"
    _write_json(path, payload)

    with pytest.raises(CatalogLoadError, match="region_type"):
        FileCatalogLoader(root).load()


def test_missing_primary_region_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "routes.json"
    payload = _json(path)
    payload["routes"][0]["primary_region_id"] = "cn.missing"
    _write_json(path, payload)

    with pytest.raises(CatalogValidationError, match="missing primary region cn.missing"):
        FileCatalogLoader(root).load()


def test_primary_region_must_be_compatible_with_coverage(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "routes.json"
    payload = _json(path)
    payload["routes"][0]["primary_region_id"] = "cn.shanxi.changzhi.shangdang"
    _write_json(path, payload)

    with pytest.raises(CatalogValidationError, match="is incompatible with coverage"):
        FileCatalogLoader(root).load()


def test_empty_coverage_region_ids_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "routes.json"
    payload = _json(path)
    payload["routes"][0]["coverage_region_ids"] = []
    _write_json(path, payload)

    with pytest.raises(CatalogLoadError, match="coverage_region_ids"):
        FileCatalogLoader(root).load()


def test_missing_coverage_region_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "routes.json"
    payload = _json(path)
    payload["routes"][0]["coverage_region_ids"] = ["cn.missing"]
    _write_json(path, payload)

    with pytest.raises(CatalogValidationError, match="missing coverage region cn.missing"):
        FileCatalogLoader(root).load()


def test_multi_region_route_is_valid(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "routes.json"
    payload = _json(path)
    payload["routes"][0]["primary_region_id"] = "cn.shanxi.changzhi"
    payload["routes"][0]["coverage_region_ids"] = [
        "cn.shanxi.changzhi.changzi",
        "cn.shanxi.changzhi.shangdang",
    ]
    _write_json(path, payload)

    catalog = FileCatalogLoader(root).load()

    assert catalog.get_route("changzhi.route.jingwei-fajiushan").coverage_region_ids == [
        "cn.shanxi.changzhi.changzi",
        "cn.shanxi.changzhi.shangdang",
    ]


def test_anchor_outside_route_coverage_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "routes.json"
    payload = _json(path)
    payload["routes"][0]["primary_region_id"] = "cn.shanxi.changzhi"
    payload["routes"][0]["coverage_region_ids"] = [
        "cn.shanxi.changzhi.shangdang"
    ]
    _write_json(path, payload)

    with pytest.raises(CatalogValidationError, match="is outside route coverage"):
        FileCatalogLoader(root).load()


def test_anchor_in_child_region_of_route_coverage_is_valid(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "routes.json"
    payload = _json(path)
    payload["routes"][0]["primary_region_id"] = "cn.shanxi.changzhi"
    payload["routes"][0]["coverage_region_ids"] = ["cn.shanxi.changzhi"]
    _write_json(path, payload)

    catalog = FileCatalogLoader(root).load()

    assert catalog.get_route("changzhi.route.jingwei-fajiushan") is not None


def test_missing_theme_reference_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "routes.json"
    payload = _json(path)
    payload["routes"][0]["theme_id"] = "missing.theme"
    _write_json(path, payload)

    with pytest.raises(CatalogValidationError, match="missing theme"):
        FileCatalogLoader(root).load()


def test_missing_anchor_reference_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "routes.json"
    payload = _json(path)
    payload["routes"][0]["anchor_ids"] = ["missing.anchor"]
    payload["routes"][0]["mandatory_anchor_ids"] = ["missing.anchor"]
    _write_json(path, payload)

    with pytest.raises(CatalogValidationError, match="missing anchor"):
        FileCatalogLoader(root).load()


def test_duplicate_id_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "registry" / "regions" / "cn" / "shanxi" / "regions.json"
    payload = _json(path)
    payload["regions"].append(dict(payload["regions"][0]))
    _write_json(path, payload)

    with pytest.raises(CatalogValidationError, match="duplicate id cn.shanxi"):
        FileCatalogLoader(root).load()


def test_invalid_theme_type_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "themes.json"
    payload = _json(path)
    payload["themes"][0]["type"] = "regional_special_case"
    _write_json(path, payload)

    with pytest.raises(CatalogLoadError, match=r"themes\.0\.type"):
        FileCatalogLoader(root).load()


def test_empty_mandatory_anchor_list_is_valid(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "routes.json"
    payload = _json(path)
    payload["routes"][0]["mandatory_anchor_ids"] = []
    _write_json(path, payload)

    catalog = FileCatalogLoader(root).load()
    assert catalog.get_route("changzhi.route.jingwei-fajiushan").mandatory_anchor_ids == []


def test_invalid_manifest_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "manifest.json"
    payload = _json(path)
    del payload["package_id"]
    _write_json(path, payload)

    with pytest.raises(CatalogLoadError, match="package_id"):
        FileCatalogLoader(root).load()


def test_unsupported_manifest_schema_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / "packages" / "shanxi" / "changzhi" / "manifest.json"
    payload = _json(path)
    payload["schema_version"] = "2.0"
    _write_json(path, payload)

    with pytest.raises(CatalogValidationError, match="unsupported schema_version 2.0"):
        FileCatalogLoader(root).load()


def test_catalog_python_contains_no_regional_special_cases():
    prohibited_tokens = {"changzhi", "jingwei"}
    found: list[tuple[str, str]] = []

    for path in sorted((PROJECT_ROOT / "app" / "catalog").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            value = node.value.casefold()
            for token in prohibited_tokens:
                if token in value:
                    found.append((path.name, token))

    assert not found
