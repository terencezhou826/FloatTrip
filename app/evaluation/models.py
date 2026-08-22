"""Stable schemas shared by benchmark fixtures, runners, and reports."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvaluationDomain(StrEnum):
    PLANNING = "planning"
    KNOWLEDGE = "knowledge"
    STORY = "story"
    EXPERIENCE = "experience"
    RESOURCES = "resources"
    PRODUCT = "product"
    CROSS_LAYER = "cross_layer"


class EvalSeverity(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class MetricType(StrEnum):
    BOOLEAN = "boolean"
    COUNT = "count"
    RATIO = "ratio"
    DURATION = "duration"
    SCORE = "score"
    SET_EQUALITY = "set_equality"
    IDENTITY_MATCH = "identity_match"


class MetricDirection(StrEnum):
    EXACT = "exact"
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class EvaluatorKind(StrEnum):
    DETERMINISTIC = "deterministic"
    LLM_JUDGE = "llm_judge"


class EvalStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class OverallStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class BenchmarkVersion(EvaluationModel):
    schema_version: str = Field(pattern=r"^\d+\.\d+$")
    content_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")


class EvalSuite(EvaluationModel):
    suite_id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    domain: EvaluationDomain
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    case_ids: tuple[str, ...] = Field(min_length=1)
    required_for_route_readiness: StrictBool
    enabled: StrictBool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_case_ids(self) -> "EvalSuite":
        if len(self.case_ids) != len(set(self.case_ids)):
            raise ValueError("suite case_ids must be unique")
        return self


class EvalCase(EvaluationModel):
    case_id: str = Field(min_length=1, max_length=200)
    suite_id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    severity: EvalSeverity
    input_fixture: str = Field(min_length=1, max_length=500)
    expected_contract: dict[str, Any]
    metric_ids: tuple[str, ...] = Field(min_length=1)
    tags: tuple[str, ...] = ()
    route_scope: tuple[str, ...] = ()
    requires_network: StrictBool = False
    requires_llm: StrictBool = False
    enabled: StrictBool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_metric_ids(self) -> "EvalCase":
        if len(self.metric_ids) != len(set(self.metric_ids)):
            raise ValueError("case metric_ids must be unique")
        return self


class EvalMetric(EvaluationModel):
    metric_id: str = Field(min_length=1, max_length=200)
    domain: EvaluationDomain
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    metric_type: MetricType
    direction: MetricDirection
    threshold: Any
    hard_gate: StrictBool
    unit: str | None = Field(default=None, min_length=1, max_length=80)
    evaluator_kind: EvaluatorKind = EvaluatorKind.DETERMINISTIC
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def prohibit_llm_hard_gate(self) -> "EvalMetric":
        if self.hard_gate and self.evaluator_kind is EvaluatorKind.LLM_JUDGE:
            raise ValueError("LLM judges cannot define hard gates")
        return self


class EvalResult(EvaluationModel):
    case_id: str
    metric_id: str
    status: EvalStatus
    actual: Any = None
    expected: Any = None
    threshold: Any = None
    hard_gate: StrictBool
    details: str = ""
    evidence_refs: tuple[str, ...] = ()
    duration_ms: float = Field(default=0.0, ge=0)
    warnings: tuple[str, ...] = ()


class SuiteResult(EvaluationModel):
    suite_id: str
    domain: EvaluationDomain
    results: tuple[EvalResult, ...]
    duration_ms: float = Field(default=0.0, ge=0)


class RouteReadinessResult(EvaluationModel):
    route_id: str
    ready: StrictBool
    availability: str
    passed_requirements: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    optional_capabilities: dict[str, bool] = Field(default_factory=dict)


class BenchmarkReport(EvaluationModel):
    report_id: str
    benchmark_version: BenchmarkVersion
    git_commit: str
    created_at: datetime
    suite_results: tuple[SuiteResult, ...]
    metric_summary: dict[str, Any]
    hard_failures: tuple[str, ...] = ()
    soft_warnings: tuple[str, ...] = ()
    regressions: tuple[dict[str, Any], ...] = ()
    environment: dict[str, Any] = Field(default_factory=dict)
    snapshot_versions: dict[str, Any] = Field(default_factory=dict)
    route_readiness: tuple[RouteReadinessResult, ...] = ()
    overall_status: OverallStatus

    @model_validator(mode="after")
    def require_timezone(self) -> "BenchmarkReport":
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must include an ISO 8601 timezone")
        return self
