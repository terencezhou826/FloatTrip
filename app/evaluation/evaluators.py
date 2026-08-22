"""Deterministic metric evaluation for frozen benchmark observations."""

from __future__ import annotations

from typing import Any

from app.evaluation.models import EvalMetric, EvalStatus, MetricDirection


def evaluate_observation(
    metric: EvalMetric, actual: Any, expected: Any
) -> tuple[EvalStatus, str]:
    if metric.direction is MetricDirection.EXACT:
        passed = _normalized(actual) == _normalized(expected)
    elif not _numeric(actual) or not _numeric(expected):
        return EvalStatus.ERROR, "ordered metric requires numeric values"
    elif metric.direction is MetricDirection.HIGHER_IS_BETTER:
        passed = float(actual) >= float(expected)
    else:
        passed = float(actual) <= float(expected)
    if passed:
        return EvalStatus.PASS, "observed value satisfies the case contract"
    return (
        EvalStatus.FAIL if metric.hard_gate else EvalStatus.WARNING,
        "observed value violates the case contract",
    )


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _normalized(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_normalized(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((key, _normalized(item)) for key, item in value.items()))
    return value
