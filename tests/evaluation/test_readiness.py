from __future__ import annotations

from app.evaluation import (
    BenchmarkCorpus,
    BenchmarkRunner,
    RouteReadinessEvaluator,
)


def _profiles():
    corpus = BenchmarkCorpus.load()
    report = BenchmarkRunner(corpus).run()
    return corpus, report, RouteReadinessEvaluator(corpus).evaluate(report)


def test_ready_routes_have_all_required_capabilities():
    _, report, profiles = _profiles()
    ready = [profile for profile in profiles if profile.ready]
    assert ready
    for profile in ready:
        assert profile.availability == "ready"
        assert not profile.missing_requirements
        report_result = next(
            item for item in report.route_readiness if item.route_id == profile.route_id
        )
        assert report_result.ready


def test_non_ready_routes_report_their_actual_missing_prerequisites():
    _, _, profiles = _profiles()
    for profile in profiles:
        assert profile.ready is (not profile.missing_requirements)
        assert profile.availability == ("ready" if profile.ready else "coming_soon")


def test_resources_are_optional_for_product_ready():
    corpus = BenchmarkCorpus.load()
    corpus.golden["capability_expectation"]["resources_available"] = False
    report = BenchmarkRunner(corpus).run()
    profile = next(item for item in RouteReadinessEvaluator(corpus).evaluate(report) if item.ready)
    assert not profile.resources_declared
    assert not profile.resources_available
    assert profile.ready


def test_golden_fixture_structure_drift_blocks_readiness():
    corpus = BenchmarkCorpus.load()
    initial = BenchmarkRunner(corpus).run()
    ready_route = next(item.route_id for item in initial.route_readiness if item.ready)
    corpus.get_golden(ready_route)["expected_chapter_ids"] = ["changed.chapter"]
    report = BenchmarkRunner(corpus).run()
    profile = next(
        item
        for item in RouteReadinessEvaluator(corpus).evaluate(report)
        if item.route_id == ready_route
    )
    assert not profile.ready
    assert "golden_eval_cases" in profile.missing_requirements


def test_readiness_uses_capabilities_not_route_names():
    source = __import__("inspect").getsource(RouteReadinessEvaluator).lower()
    for name in ("jingwei", "nuwa", "shennong", "houyi", "changzhi"):
        assert name not in source
