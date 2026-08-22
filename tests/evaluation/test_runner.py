from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.evaluation import (
    BenchmarkBaseline,
    BenchmarkReport,
    BenchmarkRunner,
    BenchmarkVersion,
    EvalMetric,
    EvalResult,
    EvalStatus,
    EvaluationDomain,
    FORMAL_METRICS,
    MetricDirection,
    MetricRegistry,
    MetricType,
    OverallStatus,
    RegressionClassification,
    SuiteResult,
    compare_reports,
)
from app.evaluation.reports import write_reports
from app.evaluation.runner import substantive_results


def _report(
    results: tuple[EvalResult, ...],
    *,
    status: OverallStatus = OverallStatus.PASS,
    hard_failures: tuple[str, ...] = (),
) -> BenchmarkReport:
    return BenchmarkReport(
        report_id="report-test",
        benchmark_version=BenchmarkVersion(schema_version="1.0", content_version="1.0.0"),
        git_commit="abc123",
        created_at=datetime.now(timezone.utc),
        suite_results=(
            SuiteResult(
                suite_id="test",
                domain=EvaluationDomain.PLANNING,
                results=results,
            ),
        ),
        metric_summary={"total": len(results)},
        hard_failures=hard_failures,
        overall_status=status,
    )


def _result(
    case: str,
    metric: str,
    status: EvalStatus,
    actual,
    *,
    hard: bool,
) -> EvalResult:
    return EvalResult(
        case_id=case,
        metric_id=metric,
        status=status,
        actual=actual,
        expected=True,
        threshold=True,
        hard_gate=hard,
    )


def test_offline_runner_passes_without_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("offline benchmark attempted network access")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "socket", blocked)
    report = BenchmarkRunner().run()
    assert report.overall_status is OverallStatus.PASS
    assert report.environment["mode"] == "offline"
    assert report.metric_summary["failed"] == 0
    assert report.metric_summary["total"] > 0


def test_two_offline_runs_have_identical_substantive_results():
    runner = BenchmarkRunner()
    first = runner.run()
    second = runner.run()
    assert first.report_id != second.report_id
    assert substantive_results(first) == substantive_results(second)


def test_json_and_markdown_reports_are_written(tmp_path):
    report = BenchmarkRunner().run()
    json_path, markdown_path = write_reports(report, tmp_path)
    loaded = BenchmarkReport.model_validate_json(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert loaded.metric_summary == report.metric_summary
    assert "# Benchmark Report" in markdown
    assert "## Hard Failures" in markdown
    assert "## Route Readiness" in markdown


def test_hard_regression_is_detected():
    metric_id = "planning.runtime_completion"
    baseline = _report((_result("case", metric_id, EvalStatus.PASS, True, hard=True),))
    current = _report(
        (_result("case", metric_id, EvalStatus.FAIL, False, hard=True),),
        status=OverallStatus.FAIL,
        hard_failures=("case",),
    )
    comparison = compare_reports(current, baseline, FORMAL_METRICS)
    assert comparison[0].classification is RegressionClassification.HARD_REGRESSION


def test_hard_ratio_threshold_regression_is_detected_even_if_status_is_pass():
    metric_id = "planning.mandatory_anchor_recall"
    baseline = _report((_result("case", metric_id, EvalStatus.PASS, 1.0, hard=True),))
    current = _report((_result("case", metric_id, EvalStatus.PASS, 0.9, hard=True),))
    comparison = compare_reports(current, baseline, FORMAL_METRICS)
    assert comparison[0].classification is RegressionClassification.HARD_REGRESSION


def test_soft_regression_and_improvement_are_direction_aware():
    metric = EvalMetric(
        metric_id="story.quality_score",
        domain="story",
        name="Quality",
        description="Soft prose quality.",
        metric_type=MetricType.SCORE,
        direction=MetricDirection.HIGHER_IS_BETTER,
        threshold=75,
        hard_gate=False,
    )
    metrics = MetricRegistry((metric,))
    baseline = _report((_result("case", metric.metric_id, EvalStatus.PASS, 82, hard=False),))
    worse = _report((_result("case", metric.metric_id, EvalStatus.PASS, 78, hard=False),))
    better = _report((_result("case", metric.metric_id, EvalStatus.PASS, 86, hard=False),))
    assert compare_reports(worse, baseline, metrics)[0].classification is RegressionClassification.SOFT_REGRESSION
    assert compare_reports(better, baseline, metrics)[0].classification is RegressionClassification.IMPROVED


def test_new_and_removed_cases_are_classified():
    metric_id = "planning.runtime_completion"
    baseline = _report((_result("removed", metric_id, EvalStatus.PASS, True, hard=True),))
    current = _report((_result("new", metric_id, EvalStatus.PASS, True, hard=True),))
    classes = {item.classification for item in compare_reports(current, baseline, FORMAL_METRICS)}
    assert classes == {
        RegressionClassification.NEW_CASE,
        RegressionClassification.REMOVED_CASE,
    }


def test_baseline_round_trip_and_hard_failure_protection(tmp_path):
    passing = BenchmarkRunner().run()
    path = tmp_path / "baseline.json"
    BenchmarkBaseline.from_report(passing).save(path)
    assert BenchmarkBaseline.load(path).report.metric_summary == passing.metric_summary

    failed_result = _result(
        "case", "planning.runtime_completion", EvalStatus.FAIL, False, hard=True
    )
    failed = _report((failed_result,), status=OverallStatus.FAIL)
    protected = tmp_path / "protected.json"
    protected.write_text("original", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot update baseline"):
        BenchmarkBaseline.from_report(failed).save(protected)
    assert protected.read_text(encoding="utf-8") == "original"


def test_route_baseline_records_explicit_scope():
    report = BenchmarkRunner().run()
    baseline = BenchmarkBaseline.from_report(
        report, scope="route", route_id="example.route"
    )
    assert baseline.scope == "route"
    assert baseline.route_id == "example.route"


def test_report_has_no_secret_material():
    serialized = BenchmarkRunner().run().model_dump_json().lower()
    assert "amap_api_key" not in serialized
    assert "openai_api_key" not in serialized
    assert "authorization" not in serialized
