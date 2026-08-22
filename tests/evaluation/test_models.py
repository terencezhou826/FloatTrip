from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.evaluation import (
    BenchmarkReport,
    BenchmarkVersion,
    EvalCase,
    EvalMetric,
    EvalSeverity,
    EvalSuite,
    EvaluationDomain,
    EvaluatorKind,
    MetricDirection,
    MetricType,
    OverallStatus,
)


def test_suite_and_case_contracts_are_frozen_and_serializable():
    case = EvalCase(
        case_id="planning.plain-trip",
        suite_id="planning.core",
        name="Plain trip",
        description="Legacy trip remains supported.",
        severity=EvalSeverity.HARD,
        input_fixture="benchmarks/planning/plain-trip.json",
        expected_contract={"completes": True},
        metric_ids=("planning.runtime_completion",),
        tags=("positive",),
    )
    suite = EvalSuite(
        suite_id="planning.core",
        name="Planning core",
        description="Deterministic planning contracts.",
        domain=EvaluationDomain.PLANNING,
        version="1.0.0",
        case_ids=(case.case_id,),
        required_for_route_readiness=True,
    )
    assert EvalCase.model_validate_json(case.model_dump_json()) == case
    assert EvalSuite.model_validate_json(suite.model_dump_json()) == suite
    with pytest.raises(ValidationError):
        suite.name = "changed"


def test_duplicate_references_are_rejected():
    with pytest.raises(ValidationError, match="case_ids must be unique"):
        EvalSuite(
            suite_id="duplicate",
            name="Duplicate",
            description="Invalid duplicate references.",
            domain="planning",
            version="1.0.0",
            case_ids=("a", "a"),
            required_for_route_readiness=True,
        )


def test_llm_judge_cannot_be_a_hard_gate():
    with pytest.raises(ValidationError, match="LLM judges cannot define hard gates"):
        EvalMetric(
            metric_id="story.style",
            domain="story",
            name="Style",
            description="Optional prose quality.",
            metric_type=MetricType.SCORE,
            direction=MetricDirection.HIGHER_IS_BETTER,
            threshold=80,
            hard_gate=True,
            evaluator_kind=EvaluatorKind.LLM_JUDGE,
        )


def test_benchmark_version_is_explicit_and_not_a_catalog_version_alias():
    report = BenchmarkReport(
        report_id="report-1",
        benchmark_version=BenchmarkVersion(
            schema_version="1.0", content_version="1.0.0"
        ),
        git_commit="abc123",
        created_at=datetime.now(timezone.utc),
        suite_results=(),
        metric_summary={},
        snapshot_versions={
            "catalog": {"schema_version": "1.0", "content_version": "0.3.0"}
        },
        overall_status=OverallStatus.PASS,
    )
    assert report.benchmark_version.content_version == "1.0.0"
    assert report.snapshot_versions["catalog"]["content_version"] == "0.3.0"


def test_naive_report_timestamp_is_rejected():
    with pytest.raises(ValidationError, match="ISO 8601 timezone"):
        BenchmarkReport(
            report_id="report-1",
            benchmark_version={"schema_version": "1.0", "content_version": "1.0.0"},
            git_commit="abc123",
            created_at=datetime(2026, 8, 22),
            suite_results=(),
            metric_summary={},
            overall_status="PASS",
        )
