from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
CLIENT = TestClient(app)


def test_product_run_uses_formal_runtime_and_resume_apis():
    api = (ROOT / "frontend" / "api.js").read_text(encoding="utf-8")
    page = (ROOT / "frontend" / "product-pages.jsx").read_text(encoding="utf-8")

    assert 'apiJson("/api/runs"' in api
    assert "resumeRuntimeRun(" in page
    assert "streamRuntimeRun(" in page
    assert "getRunEvents(runId, 0)" in page
    assert "createRuntimeRun(\"travel_plan\"" in (ROOT / "frontend" / "main.jsx").read_text(encoding="utf-8")
    assert "Planning Graph" not in page


def test_product_run_recovery_does_not_create_a_duplicate_run():
    page = (ROOT / "frontend" / "product-pages.jsx").read_text(encoding="utf-8")

    recovery = page[page.index("function ProductTripRuntimePage"):]
    assert "getRun(runId)" in recovery
    assert "getRunEvents(runId, 0)" in recovery
    assert "createRuntimeRun" not in recovery
    assert "run-cursor:" in recovery


def test_coming_soon_is_blocked_by_backend_capability_projection():
    state = (ROOT / "frontend" / "product-state.js").read_text(encoding="utf-8")
    page = (ROOT / "frontend" / "product-pages.jsx").read_text(encoding="utf-8")

    assert 'route?.availability === "ready"' in state
    assert "if (creatingRef.current || !ready) return" in page
    assert "完整体验尚未开放" in page


def test_non_provider_spatial_points_use_neutral_map_label():
    api = (ROOT / "frontend" / "api.js").read_text(encoding="utf-8")
    page = (ROOT / "frontend" / "product-pages.jsx").read_text(encoding="utf-8")

    assert 'it.spatial_identity_type !== "provider_poi"' in api
    assert '"文化地点定位"' in api
    assert "spatialLocationLabel" in page
    assert "高德景区" not in api


def test_locality_route_exposes_visible_precision_and_safety_disclosure():
    route = CLIENT.get(
        "/api/catalog/packages/shanxi.changzhi/routes/"
        "changzhi.route.nuwa-tiantaishan"
    ).json()
    page = (ROOT / "frontend" / "product-pages.jsx").read_text(encoding="utf-8")
    state = (ROOT / "frontend" / "product-state.js").read_text(encoding="utf-8")

    assert route["capabilities"]["spatial_resolution"] == "verified_locality"
    assert route["capabilities"]["location_disclosure_required"] is True
    assert route["location_disclosures"]
    assert "上郝村" in route["location_disclosures"][0]
    assert "农田" in route["location_disclosures"][0]
    assert "location_disclosures" in page
    assert "近域导航" in state


def test_fulfillment_ui_polls_snapshot_only_until_terminal():
    api = (ROOT / "frontend" / "api.js").read_text(encoding="utf-8")
    page = (ROOT / "frontend" / "product-pages.jsx").read_text(encoding="utf-8")
    state = (ROOT / "frontend" / "product-state.js").read_text(encoding="utf-8")

    assert "setInterval" in page and "2500" in page
    assert "document.hidden" in page
    assert "visibilitychange" in page
    assert "shouldPollFulfillment" in page
    assert "isFulfillmentTerminal" in state
    assert "/trip/fulfillment/retry" in api
    assert "StoryGenerationService" not in page
    assert "ExperienceGenerationService" not in page
    assert "AMAP_API_KEY" not in page
    assert "sqlite" not in page.casefold()


def test_fulfillment_ui_has_distinct_truthful_stage_states():
    page = (ROOT / "frontend" / "product-pages.jsx").read_text(encoding="utf-8")

    for copy in (
        "等待生成故事",
        "正在生成你的主题故事",
        "互动将在主题故事完成后生成",
        "正在准备现场互动",
        "正在核验沿途资源",
        "当前没有已验证的附近资源",
        "本线路暂未提供附近资源推荐",
        "附近资源暂时无法核验",
    ):
        assert copy in page
