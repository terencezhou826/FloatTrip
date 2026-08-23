from __future__ import annotations

from fastapi.testclient import TestClient

from app.catalog.loader import FileCatalogLoader
from app.main import app


client = TestClient(app)


def test_catalog_product_list_is_complete_and_data_driven():
    response = client.get("/api/catalog/product-collections")

    assert response.status_code == 200
    collections = response.json()["collections"]
    assert len(collections) == 1
    collection = collections[0]
    assert collection["package_id"] == "shanxi.changzhi"
    manifest = FileCatalogLoader("content/catalog").load().get_package(
        "shanxi.changzhi"
    ).manifest
    assert collection["content_version"] == manifest.content_version
    assert collection["region"]["name"] == "长治市"
    assert len(collection["routes"]) == 4


def test_route_capabilities_are_projected_from_verified_catalog_content():
    routes = client.get("/api/catalog/product-collections").json()["collections"][0]["routes"]
    for route in routes:
        capabilities = route["capabilities"]
        required = (
            "catalog_available",
            "planning_available",
            "knowledge_available",
            "story_available",
            "experience_available",
        )
        expected = (
            "ready"
            if all(capabilities[key] for key in required)
            else "preview"
            if any(capabilities[key] for key in required[1:])
            else "coming_soon"
        )
        assert route["availability"] == expected

    jingwei = next(
        route["capabilities"]
        for route in routes
        if route["id"] == "changzhi.route.jingwei-fajiushan"
    )
    assert jingwei["spatial_resolution"] == "exact_provider_poi"
    assert jingwei["spatial_degraded"] is False
    assert jingwei["location_disclosure_required"] is False
    assert jingwei["exact_anchor_location_available"] is True
    assert jingwei["navigation_available"] is True

    nuwa = next(
        route
        for route in routes
        if route["id"] == "changzhi.route.nuwa-tiantaishan"
    )
    assert nuwa["availability"] == "ready"
    assert nuwa["capabilities"]["planning_available"] is True
    assert nuwa["capabilities"]["spatial_resolution"] == "verified_locality"
    assert nuwa["capabilities"]["spatial_degraded"] is True
    assert nuwa["capabilities"]["location_disclosure_required"] is True
    assert nuwa["capabilities"]["exact_anchor_location_available"] is False
    assert nuwa["capabilities"]["navigation_available"] is True

    assert len(routes) == 4
    assert all(route["availability"] == "ready" for route in routes)
    assert all(route["capabilities"]["planning_available"] for route in routes)


def test_route_detail_contains_catalog_identity_and_safe_preview():
    response = client.get(
        "/api/catalog/packages/shanxi.changzhi/routes/"
        "changzhi.route.jingwei-fajiushan"
    )

    assert response.status_code == 200
    route = response.json()
    assert route["theme"]["id"] == "changzhi.jingwei"
    assert route["primary_region"]["id"] == "cn.shanxi.changzhi.changzi"
    assert route["anchors"][0] == {
        "id": "changzhi.anchor.fajiushan",
        "name": "发鸠山",
        "region_id": "cn.shanxi.changzhi.changzi",
        "mandatory": True,
    }
    assert route["cultural_preview"]
    assert route["cultural_preview"][0]["citations"]


def test_unknown_or_disabled_product_route_is_not_exposed():
    response = client.get(
        "/api/catalog/packages/shanxi.changzhi/routes/missing.route"
    )

    assert response.status_code == 404


def test_route_can_be_resolved_without_frontend_package_hardcoding():
    response = client.get(
        "/api/catalog/routes/changzhi.route.jingwei-fajiushan"
    )

    assert response.status_code == 200
    assert response.json()["package_id"] == "shanxi.changzhi"


def test_frontend_product_routes_deliver_the_spa():
    for path in (
        "/myth-journeys",
        "/myth-journeys/changzhi.route.jingwei-fajiushan",
        "/my-trips/example-run",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert '<div id="root"></div>' in response.text
