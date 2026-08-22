"""Baseline persistence and deterministic regression classification."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from app.evaluation.models import (
    BenchmarkReport,
    EvalResult,
    EvalStatus,
    EvaluationModel,
    MetricDirection,
)
from app.evaluation.registry import MetricRegistry


class RegressionClassification(StrEnum):
    IMPROVED = "IMPROVED"
    UNCHANGED = "UNCHANGED"
    SOFT_REGRESSION = "SOFT_REGRESSION"
    HARD_REGRESSION = "HARD_REGRESSION"
    NEW_CASE = "NEW_CASE"
    REMOVED_CASE = "REMOVED_CASE"


class Regression(EvaluationModel):
    case_id: str
    metric_id: str
    classification: RegressionClassification
    baseline_status: EvalStatus | None = None
    current_status: EvalStatus | None = None
    baseline_actual: Any = None
    current_actual: Any = None
    hard_gate: bool


class BenchmarkBaseline(EvaluationModel):
    scope: str = "global"
    route_id: str | None = None
    benchmark_version: dict[str, str]
    git_commit: str
    snapshot_versions: dict[str, Any] = Field(default_factory=dict)
    report: BenchmarkReport

    @classmethod
    def load(cls, path: str | Path) -> "BenchmarkBaseline":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def from_report(
        cls,
        report: BenchmarkReport,
        *,
        scope: str = "global",
        route_id: str | None = None,
    ) -> "BenchmarkBaseline":
        return cls(
            scope=scope,
            route_id=route_id,
            benchmark_version=report.benchmark_version.model_dump(),
            git_commit=report.git_commit,
            snapshot_versions=report.snapshot_versions,
            report=report,
        )

    @model_validator(mode="after")
    def validate_scope(self) -> "BenchmarkBaseline":
        if self.scope not in {"global", "route"}:
            raise ValueError("baseline scope must be global or route")
        if self.scope == "route" and not self.route_id:
            raise ValueError("route baseline requires route_id")
        if self.scope == "global" and self.route_id is not None:
            raise ValueError("global baseline cannot set route_id")
        return self

    def save(self, path: str | Path) -> Path:
        has_hard_result = any(
            result.hard_gate and result.status in {EvalStatus.FAIL, EvalStatus.ERROR}
            for suite in self.report.suite_results
            for result in suite.results
        )
        if self.report.hard_failures or has_hard_result:
            raise ValueError("cannot update baseline while hard failures exist")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return target


def compare_reports(
    current: BenchmarkReport,
    baseline: BenchmarkReport,
    metrics: MetricRegistry,
) -> tuple[Regression, ...]:
    current_results = _results(current)
    baseline_results = _results(baseline)
    keys = sorted(set(current_results) | set(baseline_results))
    comparisons = []
    for key in keys:
        current_result = current_results.get(key)
        baseline_result = baseline_results.get(key)
        metric = metrics.get(key[1])
        hard = bool(
            current_result.hard_gate if current_result is not None
            else baseline_result.hard_gate if baseline_result is not None
            else metric.hard_gate if metric is not None
            else False
        )
        if baseline_result is None:
            classification = RegressionClassification.NEW_CASE
        elif current_result is None:
            classification = RegressionClassification.REMOVED_CASE
        else:
            classification = _classify(current_result, baseline_result, metric)
        comparisons.append(
            Regression(
                case_id=key[0],
                metric_id=key[1],
                classification=classification,
                baseline_status=(baseline_result.status if baseline_result else None),
                current_status=(current_result.status if current_result else None),
                baseline_actual=(baseline_result.actual if baseline_result else None),
                current_actual=(current_result.actual if current_result else None),
                hard_gate=hard,
            )
        )
    return tuple(comparisons)


def _results(report: BenchmarkReport) -> dict[tuple[str, str], EvalResult]:
    return {
        (result.case_id, result.metric_id): result
        for suite in report.suite_results
        for result in suite.results
    }


def _classify(
    current: EvalResult,
    baseline: EvalResult,
    metric,
) -> RegressionClassification:
    failing = {EvalStatus.FAIL, EvalStatus.ERROR}
    if current.status in failing and baseline.status not in failing:
        return (
            RegressionClassification.HARD_REGRESSION
            if current.hard_gate
            else RegressionClassification.SOFT_REGRESSION
        )
    if baseline.status in failing and current.status not in failing:
        return RegressionClassification.IMPROVED
    if current.status != baseline.status:
        if current.status is EvalStatus.WARNING:
            return RegressionClassification.SOFT_REGRESSION
        if baseline.status in {EvalStatus.WARNING, EvalStatus.SKIPPED}:
            return RegressionClassification.IMPROVED
    value_change = _compare_values(current.actual, baseline.actual, metric)
    if value_change > 0:
        return RegressionClassification.IMPROVED
    if value_change < 0:
        return (
            RegressionClassification.HARD_REGRESSION
            if current.hard_gate
            else RegressionClassification.SOFT_REGRESSION
        )
    return RegressionClassification.UNCHANGED


def _compare_values(current: Any, baseline: Any, metric) -> int:
    if current == baseline or metric is None:
        return 0
    if isinstance(current, (int, float)) and isinstance(baseline, (int, float)):
        if metric.direction is MetricDirection.HIGHER_IS_BETTER:
            return 1 if current > baseline else -1
        if metric.direction is MetricDirection.LOWER_IS_BETTER:
            return 1 if current < baseline else -1
    return -1
