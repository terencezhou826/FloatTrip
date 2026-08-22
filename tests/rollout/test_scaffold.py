from __future__ import annotations

import json

import pytest

from app.rollout import RouteContentScaffold


def test_scaffold_creates_only_empty_content_contracts(tmp_path):
    target = RouteContentScaffold().create(tmp_path, "example.route.alpha")
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == {
        "scaffold_schema_version": "1.0",
        "route_id": "example.route.alpha",
        "rollout_status": "catalog_only",
        "generated_content": False,
    }
    for relative in RouteContentScaffold.EMPTY_FILES:
        assert json.loads((target / relative).read_text(encoding="utf-8")) == []
    golden = json.loads(
        (target / "benchmarks" / "golden.json").read_text(encoding="utf-8")
    )
    assert golden["route_id"] == "example.route.alpha"
    assert all(not value for key, value in golden.items() if key != "route_id")


def test_scaffold_does_not_overwrite_existing_workspace(tmp_path):
    scaffold = RouteContentScaffold()
    scaffold.create(tmp_path, "example.route.alpha")
    with pytest.raises(FileExistsError):
        scaffold.create(tmp_path, "example.route.alpha")


def test_scaffold_rejects_non_stable_route_id(tmp_path):
    with pytest.raises(ValueError, match="stable ID"):
        RouteContentScaffold().create(tmp_path, "../outside")
