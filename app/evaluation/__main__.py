"""Command-line entry point for the M7 benchmark system."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.evaluation.baseline import BenchmarkBaseline
from app.evaluation.models import EvaluationDomain
from app.evaluation.reports import write_reports
from app.evaluation.runner import BenchmarkRunner


DEFAULT_BASELINE = Path("benchmarks/baselines/global-1.0.0.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run FloatTrip benchmarks")
    parser.add_argument("--suite", action="append", default=[])
    parser.add_argument("--domain", action="append", choices=[item.value for item in EvaluationDomain], default=[])
    parser.add_argument("--case", action="append", default=[])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="Run deterministic local cases (default)")
    mode.add_argument("--live", action="store_true", help="Allow cases explicitly marked as live")
    parser.add_argument("--output", default=".benchmark_reports")
    parser.add_argument("--compare-baseline", nargs="?", const=str(DEFAULT_BASELINE))
    parser.add_argument("--update-baseline", nargs="?", const=str(DEFAULT_BASELINE))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    baseline = None
    if args.compare_baseline:
        baseline = BenchmarkBaseline.load(args.compare_baseline)
    report = BenchmarkRunner().run(
        suite_ids=set(args.suite) or None,
        domains={EvaluationDomain(item) for item in args.domain} or None,
        case_ids=set(args.case) or None,
        live=args.live,
        compare_baseline=baseline,
    )
    paths = write_reports(report, args.output)
    if args.update_baseline:
        BenchmarkBaseline.from_report(report).save(args.update_baseline)
    print(f"{report.overall_status.value}: {report.metric_summary['total']} metric results")
    print(f"JSON: {paths[0]}")
    print(f"Markdown: {paths[1]}")
    return 2 if report.hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
