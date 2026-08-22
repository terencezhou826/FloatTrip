"""Offline-first benchmark orchestration."""

from __future__ import annotations

import platform
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.evaluation.baseline import BenchmarkBaseline, compare_reports
from app.evaluation.corpus import BenchmarkCorpus
from app.evaluation.evaluators import evaluate_observation
from app.evaluation.models import (
    BenchmarkReport,
    EvalResult,
    EvalStatus,
    EvaluationDomain,
    OverallStatus,
    SuiteResult,
)
from app.evaluation.registry import FORMAL_METRICS


class BenchmarkRunner:
    def __init__(self, corpus: BenchmarkCorpus | None = None) -> None:
        self.corpus = corpus or BenchmarkCorpus.load()

    def run(
        self,
        *,
        suite_ids: set[str] | None = None,
        domains: set[EvaluationDomain] | None = None,
        case_ids: set[str] | None = None,
        live: bool = False,
        compare_baseline: BenchmarkBaseline | None = None,
    ) -> BenchmarkReport:
        suite_results = []
        hard_failures: list[str] = []
        soft_warnings: list[str] = []
        for suite in self.corpus.suites:
            if suite_ids and suite.suite_id not in suite_ids:
                continue
            if domains and suite.domain not in domains:
                continue
            started = time.perf_counter()
            results = []
            for case in self.corpus.cases:
                if case.suite_id != suite.suite_id:
                    continue
                if case_ids and case.case_id not in case_ids:
                    continue
                fixture = self.corpus.fixtures[case.case_id]
                for metric_id in case.metric_ids:
                    metric = FORMAL_METRICS.get(metric_id)
                    if metric is None:
                        raise ValueError(f"unknown metric: {metric_id}")
                    result_started = time.perf_counter()
                    if not live and (case.requires_network or case.requires_llm):
                        status = EvalStatus.SKIPPED
                        details = "case requires live network or LLM mode"
                    else:
                        status, details = evaluate_observation(
                            metric,
                            fixture.actual[metric_id],
                            case.expected_contract[metric_id],
                        )
                    result = EvalResult(
                        case_id=case.case_id,
                        metric_id=metric_id,
                        status=status,
                        actual=fixture.actual[metric_id],
                        expected=case.expected_contract[metric_id],
                        threshold=metric.threshold,
                        hard_gate=metric.hard_gate,
                        details=details,
                        evidence_refs=fixture.evidence_refs,
                        duration_ms=(time.perf_counter() - result_started) * 1000,
                    )
                    results.append(result)
                    identity = f"{case.case_id} / {metric_id}"
                    if status in {EvalStatus.FAIL, EvalStatus.ERROR} and metric.hard_gate:
                        hard_failures.append(identity)
                    elif status in {EvalStatus.WARNING, EvalStatus.SKIPPED}:
                        soft_warnings.append(identity)
            suite_results.append(
                SuiteResult(
                    suite_id=suite.suite_id,
                    domain=suite.domain,
                    results=tuple(results),
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
            )
        status = (
            OverallStatus.FAIL
            if hard_failures
            else OverallStatus.WARNING
            if soft_warnings
            else OverallStatus.PASS
        )
        report = BenchmarkReport(
            report_id=f"benchmark-{uuid.uuid4()}",
            benchmark_version=self.corpus.manifest.benchmark_version,
            git_commit=_git_commit(),
            created_at=datetime.now(timezone.utc),
            suite_results=tuple(suite_results),
            metric_summary=_summary(suite_results),
            hard_failures=tuple(hard_failures),
            soft_warnings=tuple(soft_warnings),
            environment={
                "mode": "live" if live else "offline",
                "python": platform.python_version(),
                "platform": platform.system(),
                "network_required_cases": sum(case.requires_network for case in self.corpus.cases),
                "llm_required_cases": sum(case.requires_llm for case in self.corpus.cases),
            },
            snapshot_versions={
                "catalog": {
                    "schema_version": self.corpus.golden.get("catalog_schema_version"),
                    "content_version": self.corpus.golden.get("catalog_content_version"),
                },
                "golden": self.corpus.golden.get("snapshot_identity", {}),
            },
            overall_status=status,
        )
        from app.evaluation.readiness import RouteReadinessEvaluator

        profiles = RouteReadinessEvaluator(self.corpus).evaluate(report)
        report = report.model_copy(
            update={"route_readiness": tuple(profile.to_result() for profile in profiles)}
        )
        if compare_baseline is not None:
            comparisons = compare_reports(report, compare_baseline.report, FORMAL_METRICS)
            report = report.model_copy(
                update={"regressions": tuple(item.model_dump(mode="json") for item in comparisons)}
            )
        return report


def substantive_results(report: BenchmarkReport) -> tuple[tuple, ...]:
    return tuple(
        (
            suite.suite_id,
            result.case_id,
            result.metric_id,
            result.status.value,
            result.actual,
            result.expected,
            result.hard_gate,
        )
        for suite in report.suite_results
        for result in suite.results
    )


def _summary(suites: list[SuiteResult]) -> dict[str, int]:
    results = [result for suite in suites for result in suite.results]
    return {
        "total": len(results),
        "passed": sum(result.status is EvalStatus.PASS for result in results),
        "failed": sum(result.status in {EvalStatus.FAIL, EvalStatus.ERROR} for result in results),
        "warnings": sum(result.status is EvalStatus.WARNING for result in results),
        "skipped": sum(result.status is EvalStatus.SKIPPED for result in results),
        "hard": sum(result.hard_gate for result in results),
        "soft": sum(not result.hard_gate for result in results),
    }


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
