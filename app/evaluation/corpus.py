"""Load and audit committed benchmark definitions without executing production code."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from app.evaluation.models import BenchmarkVersion, EvalCase, EvalSuite, EvaluationModel
from app.evaluation.registry import EvaluationRegistry, FORMAL_METRICS


DEFAULT_CORPUS_ROOT = Path(__file__).resolve().parents[2] / "benchmarks"
_SECRET_PATTERNS = (
    re.compile(
        r"(?i)[\"']?(api[_-]?key|authorization|access[_-]?token|secret)"
        r"[\"']?\s*[:=]\s*[\"']?[^\s,}\]]+"
    ),
    re.compile(r"(?i)bearer\s+[a-z0-9._-]{12,}"),
)


class BenchmarkFixture(EvaluationModel):
    fixture_id: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=1000)
    actual: dict[str, Any]
    evidence_refs: tuple[str, ...] = ()
    attack: str | None = Field(default=None, min_length=1, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorpusMetricObservation(EvaluationModel):
    expected: Any
    actual: Any


class CorpusCaseRecord(EvaluationModel):
    case_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    severity: str
    metrics: dict[str, CorpusMetricObservation] = Field(min_length=1)
    tags: tuple[str, ...] = ()
    route_scope: tuple[str, ...] = ()
    requires_network: bool = False
    requires_llm: bool = False
    source: str = Field(min_length=1, max_length=1000)
    attack: str | None = Field(default=None, min_length=1, max_length=1000)
    evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorpusSuiteFile(EvaluationModel):
    suite_id: str
    name: str
    description: str
    domain: str
    version: str
    required_for_route_readiness: bool
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    cases: tuple[CorpusCaseRecord, ...] = Field(min_length=1)


class CorpusManifest(EvaluationModel):
    benchmark_version: BenchmarkVersion
    suite_files: tuple[str, ...] = Field(min_length=1)
    golden_fixture: str | None = None
    golden_fixtures: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_golden_fixtures(self) -> "CorpusManifest":
        paths = self.golden_paths
        if not paths:
            raise ValueError("benchmark manifest requires at least one golden fixture")
        if len(paths) != len(set(paths)):
            raise ValueError("golden fixture paths must be unique")
        return self

    @property
    def golden_paths(self) -> tuple[str, ...]:
        legacy = (self.golden_fixture,) if self.golden_fixture else ()
        return legacy + self.golden_fixtures


class BenchmarkCorpus:
    def __init__(
        self,
        *,
        root: Path,
        manifest: CorpusManifest,
        suite_files: tuple[CorpusSuiteFile, ...],
        goldens: tuple[dict[str, Any], ...],
    ) -> None:
        self.root = root
        self.manifest = manifest
        self.suite_files = suite_files
        self.goldens = goldens
        self.golden = goldens[0]
        self._goldens_by_route = {
            golden["route_id"]: golden
            for golden in goldens
            if isinstance(golden.get("route_id"), str)
        }
        if len(self._goldens_by_route) != len(goldens):
            raise ValueError("golden fixture route IDs must be present and unique")
        suites: list[EvalSuite] = []
        cases: list[EvalCase] = []
        fixtures: dict[str, BenchmarkFixture] = {}
        for relative, document in zip(manifest.suite_files, suite_files, strict=True):
            case_ids = tuple(record.case_id for record in document.cases)
            suites.append(
                EvalSuite(
                    suite_id=document.suite_id,
                    name=document.name,
                    description=document.description,
                    domain=document.domain,
                    version=document.version,
                    case_ids=case_ids,
                    required_for_route_readiness=document.required_for_route_readiness,
                    enabled=document.enabled,
                    metadata=document.metadata,
                )
            )
            for record in document.cases:
                metric_ids = tuple(record.metrics)
                cases.append(
                    EvalCase(
                        case_id=record.case_id,
                        suite_id=document.suite_id,
                        name=record.name,
                        description=record.description,
                        severity=record.severity,
                        input_fixture=f"benchmarks/{relative}#{record.case_id}",
                        expected_contract={
                            metric_id: observation.expected
                            for metric_id, observation in record.metrics.items()
                        },
                        metric_ids=metric_ids,
                        tags=record.tags,
                        route_scope=record.route_scope,
                        requires_network=record.requires_network,
                        requires_llm=record.requires_llm,
                        metadata=record.metadata,
                    )
                )
                fixtures[record.case_id] = BenchmarkFixture(
                    fixture_id=record.case_id,
                    source=record.source,
                    actual={
                        metric_id: observation.actual
                        for metric_id, observation in record.metrics.items()
                    },
                    evidence_refs=record.evidence_refs,
                    attack=record.attack,
                    metadata=record.metadata,
                )
        self.suites = tuple(suites)
        self.cases = tuple(cases)
        self.fixtures = fixtures
        self.registry = EvaluationRegistry(
            suites=self.suites, cases=self.cases, metrics=FORMAL_METRICS
        )

    @classmethod
    def load(cls, root: str | Path = DEFAULT_CORPUS_ROOT) -> "BenchmarkCorpus":
        root_path = Path(root).resolve()
        manifest_path = root_path / "manifest.json"
        manifest = CorpusManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
        suite_files = tuple(
            CorpusSuiteFile.model_validate_json(
                _safe_child(root_path, relative).read_text(encoding="utf-8")
            )
            for relative in manifest.suite_files
        )
        goldens = tuple(
            json.loads(_safe_child(root_path, relative).read_text(encoding="utf-8"))
            for relative in manifest.golden_paths
        )
        corpus = cls(
            root=root_path,
            manifest=manifest,
            suite_files=suite_files,
            goldens=goldens,
        )
        corpus.audit()
        return corpus

    def audit(self) -> None:
        serialized = "\n".join(
            path.read_text(encoding="utf-8") for path in self.root.rglob("*.json")
        )
        if any(pattern.search(serialized) for pattern in _SECRET_PATTERNS):
            raise ValueError("benchmark fixture secret leakage detected")
        required_golden = {
            "mandatory_anchor_identity",
            "expected_chapter_ids",
            "expected_activity_ids",
            "approved_claim_ids",
            "forbidden_claim_ids",
            "capability_expectation",
        }
        for golden in self.goldens:
            if golden.get("route_id") is None:
                raise ValueError("golden fixture requires route_id")
            missing = required_golden.difference(golden)
            if missing:
                raise ValueError(f"golden fixture missing fields: {sorted(missing)}")

    def get_golden(self, route_id: str) -> dict[str, Any] | None:
        return self._goldens_by_route.get(route_id)


def _safe_child(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"benchmark path escapes corpus root: {relative}")
    if not path.is_file():
        raise ValueError(f"benchmark file not found: {relative}")
    return path
