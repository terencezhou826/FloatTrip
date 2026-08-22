from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_catalog_product_list_is_complete_and_data_driven():
    response = client.get("/api/catalog/product-collections")

    assert response.status_code == 200
    collections = response.json()["collections"]
    assert len(collections) == 1
    collection = collections[0]
    assert collection["package_id"] == "shanxi.changzhi"
    assert collection["content_version"] == "0.3.0"
    assert collection["region"]["name"] == "长治市"
    assert len(collection["routes"]) == 4


def test_route_capabilities_are_projected_from_verified_catalog_content():
    routes = client.get("/api/catalog/product-collections").json()["collections"][0]["routes"]
    ready = [route for route in routes if route["availability"] == "ready"]
    unavailable = [route for route in routes if route["availability"] != "ready"]

    assert len(ready) == 1
    assert all(ready[0]["capabilities"].values())
    assert len(unavailable) == 3
    assert all(not route["capabilities"]["planning_available"] for route in unavailable)


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
