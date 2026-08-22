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


def test_jingwei_is_ready_and_optional_resources_are_available():
    _, report, profiles = _profiles()
    ready = [profile for profile in profiles if profile.ready]
    assert len(ready) == 1
    profile = ready[0]
    assert profile.route_id == "changzhi.route.jingwei-fajiushan"
    assert profile.availability == "ready"
    assert not profile.missing_requirements
    assert profile.resources_declared
    assert profile.resources_available
    report_result = next(item for item in report.route_readiness if item.route_id == profile.route_id)
    assert report_result.ready


def test_other_routes_are_coming_soon_from_missing_prerequisites():
    _, _, profiles = _profiles()
    coming_soon = [profile for profile in profiles if not profile.ready]
    assert len(coming_soon) == 3
    for profile in coming_soon:
        assert profile.availability == "coming_soon"
        assert "planning_available" in profile.missing_requirements
        assert "knowledge_available" in profile.missing_requirements
        assert "story_available" in profile.missing_requirements
        assert "experience_available" in profile.missing_requirements
        assert "golden_eval_cases" in profile.missing_requirements


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
    corpus.golden["expected_chapter_ids"] = ["changed.chapter"]
    report = BenchmarkRunner(corpus).run()
    profile = next(
        item
        for item in RouteReadinessEvaluator(corpus).evaluate(report)
        if item.route_id == corpus.golden["route_id"]
    )
    assert not profile.ready
    assert "golden_eval_cases" in profile.missing_requirements


def test_readiness_uses_capabilities_not_route_names():
    source = __import__("inspect").getsource(RouteReadinessEvaluator).lower()
    for name in ("jingwei", "nuwa", "shennong", "houyi", "changzhi"):
        assert name not in source
