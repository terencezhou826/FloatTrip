"""Machine-readable and human-readable benchmark report writers."""

from __future__ import annotations

import json
from pathlib import Path

from app.evaluation.models import BenchmarkReport, EvalStatus


def write_reports(report: BenchmarkReport, output: str | Path) -> tuple[Path, Path]:
    output_path = Path(output)
    if output_path.suffix.lower() in {".json", ".md"}:
        stem = output_path.with_suffix("")
    else:
        output_path.mkdir(parents=True, exist_ok=True)
        stem = output_path / "benchmark-report"
    stem.parent.mkdir(parents=True, exist_ok=True)
    json_path = stem.with_suffix(".json")
    markdown_path = stem.with_suffix(".md")
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def render_markdown(report: BenchmarkReport) -> str:
    lines = [
        "# Benchmark Report",
        "",
        f"- Overall status: **{report.overall_status.value}**",
        f"- Benchmark version: `{report.benchmark_version.schema_version} / {report.benchmark_version.content_version}`",
        f"- Git commit: `{report.git_commit}`",
        f"- Created at: `{report.created_at.isoformat()}`",
        f"- Mode: `{report.environment.get('mode', 'offline')}`",
        "",
        "## Hard Failures",
        "",
    ]
    lines.extend(f"- {item}" for item in report.hard_failures)
    if not report.hard_failures:
        lines.append("None.")
    lines.extend(["", "## Soft Warnings", ""])
    lines.extend(f"- {item}" for item in report.soft_warnings)
    if not report.soft_warnings:
        lines.append("None.")
    lines.extend(["", "## Domain Summary", "", "| Domain | Pass | Fail | Warning | Skipped |", "|---|---:|---:|---:|---:|"])
    for suite in report.suite_results:
        counts = {status: 0 for status in EvalStatus}
        for result in suite.results:
            counts[result.status] += 1
        lines.append(
            f"| {suite.domain.value} | {counts[EvalStatus.PASS]} | "
            f"{counts[EvalStatus.FAIL] + counts[EvalStatus.ERROR]} | "
            f"{counts[EvalStatus.WARNING]} | {counts[EvalStatus.SKIPPED]} |"
        )
    lines.extend(["", "## Metrics", "", "| Case | Metric | Status | Actual | Expected |", "|---|---|---|---|---|"])
    for suite in report.suite_results:
        for result in suite.results:
            lines.append(
                f"| `{result.case_id}` | `{result.metric_id}` | {result.status.value} | "
                f"`{_short(result.actual)}` | `{_short(result.expected)}` |"
            )
    lines.extend(["", "## Regressions", ""])
    if report.regressions:
        for regression in report.regressions:
            lines.append(
                f"- `{regression['classification']}`: "
                f"`{regression['case_id']} / {regression['metric_id']}`"
            )
    else:
        lines.append("No baseline comparison requested.")
    lines.extend(["", "## Route Readiness", ""])
    if report.route_readiness:
        for readiness in report.route_readiness:
            lines.append(
                f"- `{readiness.route_id}`: `{readiness.availability}` "
                f"(ready={str(readiness.ready).lower()})"
            )
    else:
        lines.append("Not evaluated in this run.")
    lines.extend(["", "## Environment", "", "```json", json.dumps(report.environment, ensure_ascii=False, indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines)


def _short(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= 80 else text[:77] + "..."
