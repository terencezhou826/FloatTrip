from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
