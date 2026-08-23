"""Formal, route-neutral metric registry for M1-M6 behavior."""

from __future__ import annotations

from collections.abc import Iterable

from app.evaluation.models import (
    EvalCase,
    EvalMetric,
    EvalSeverity,
    EvalSuite,
    EvaluationDomain,
    EvaluatorKind,
    MetricDirection,
    MetricType,
)


def _metric(
    domain: EvaluationDomain,
    name: str,
    metric_type: MetricType,
    direction: MetricDirection,
    threshold,
    *,
    hard: bool = True,
    unit: str | None = None,
) -> EvalMetric:
    return EvalMetric(
        metric_id=f"{domain.value}.{name}",
        domain=domain,
        name=name.replace("_", " ").title(),
        description=f"Measures {name.replace('_', ' ')} for the {domain.value} domain.",
        metric_type=metric_type,
        direction=direction,
        threshold=threshold,
        hard_gate=hard,
        unit=unit,
        evaluator_kind=EvaluatorKind.DETERMINISTIC,
    )


_BOOL = (MetricType.BOOLEAN, MetricDirection.EXACT, True)
_ZERO = (MetricType.COUNT, MetricDirection.LOWER_IS_BETTER, 0)
_FULL = (MetricType.RATIO, MetricDirection.HIGHER_IS_BETTER, 1.0)


def _build_metrics() -> tuple[EvalMetric, ...]:
    specs: dict[EvaluationDomain, tuple[tuple, ...]] = {
        EvaluationDomain.PLANNING: (
            ("runtime_completion", *_BOOL),
            ("mandatory_anchor_recall", *_FULL),
            ("mandatory_identity_preservation", MetricType.IDENTITY_MATCH, MetricDirection.EXACT, True),
            ("candidate_provenance", *_FULL),
            ("fake_poi_count", *_ZERO),
            ("route_feasibility", *_BOOL),
            ("road_data_completeness", *_FULL),
            ("meal_coverage", *_FULL),
            ("meal_route_feasible", *_BOOL),
            ("provider_identity_mismatch", *_ZERO),
            ("snapshot_context_preservation", *_BOOL),
            ("waiting_user_resume", *_BOOL),
            ("runtime_recovery", *_BOOL),
            ("spatial_resolution_truthfulness", *_BOOL),
            ("navigation_reference_identity", MetricType.IDENTITY_MATCH, MetricDirection.EXACT, True),
            ("road_scope_truthfulness", *_BOOL),
        ),
        EvaluationDomain.KNOWLEDGE: (
            ("evidence_coverage", *_FULL),
            ("production_ineligible_leakage", *_ZERO),
            ("citation_identity_accuracy", *_FULL),
            ("qualifier_preservation", *_FULL),
            ("claim_type_preservation", *_FULL),
            ("unsupported_fact_count", *_ZERO),
            ("unverified_botanical_fact", *_ZERO),
            ("agricultural_historical_hallucination", *_ZERO),
            ("internal_only_leakage", *_ZERO),
            ("review_required_leakage", *_ZERO),
            ("answerability_false_positive", *_ZERO),
            ("answerability_false_negative", *_ZERO),
            ("locality_identity_verified", *_BOOL),
            ("cultural_locality_relation_verified", *_BOOL),
        ),
        EvaluationDomain.STORY: (
            ("story_chapter_count_contract", MetricType.COUNT, MetricDirection.EXACT, 5),
            ("story_grounding_coverage", *_FULL),
            ("production_claim_leakage", *_ZERO),
            ("citation_hallucination", *_ZERO),
            ("qualifier_violation", *_ZERO),
            ("claim_type_promotion", *_ZERO),
            ("context_fact_violation", *_ZERO),
            ("story_anchor_binding", *_FULL),
            ("name_only_binding", *_ZERO),
            ("knowledge_mutation", *_ZERO),
            ("itinerary_mutation", *_ZERO),
        ),
        EvaluationDomain.EXPERIENCE: (
            ("experience_activity_count_contract", MetricType.COUNT, MetricDirection.EXACT, 5),
            ("grounding_coverage", *_FULL),
            ("unsafe_instruction", *_ZERO),
            ("environmental_harm", *_ZERO),
            ("wild_plant_consumption", *_ZERO),
            ("plant_collection", *_ZERO),
            ("weapon_activity", *_ZERO),
            ("dangerous_projectile", *_ZERO),
            ("cliff_risk", *_ZERO),
            ("cultural_property_harm", *_ZERO),
            ("child_supervision_violation", *_ZERO),
            ("observation_hallucination", *_ZERO),
            ("specific_observable_without_evidence", *_ZERO),
            ("forced_purchase", *_ZERO),
            ("restricted_area_instruction", *_ZERO),
            ("water_hazard", *_ZERO),
            ("road_hazard", *_ZERO),
            ("wildlife_hazard", *_ZERO),
            ("name_only_binding", *_ZERO),
            ("knowledge_mutation", *_ZERO),
            ("story_mutation", *_ZERO),
            ("itinerary_mutation", *_ZERO),
            ("planning_mutation", *_ZERO),
            ("degraded_route_safety", *_BOOL),
        ),
        EvaluationDomain.RESOURCES: (
            ("fake_resource", *_ZERO),
            ("unverified_curated_resource", *_ZERO),
            ("name_only_identity", *_ZERO),
            ("price_hallucination", *_ZERO),
            ("availability_hallucination", *_ZERO),
            ("provenance_coverage", *_FULL),
            ("freshness_visibility", *_FULL),
            ("sponsorship_ranking_influence", *_ZERO),
            ("hidden_sponsorship", *_ZERO),
            ("mandatory_commerce", *_ZERO),
            ("detour_feasibility", *_BOOL),
            ("knowledge_mutation", *_ZERO),
            ("story_mutation", *_ZERO),
            ("experience_mutation", *_ZERO),
            ("itinerary_mutation", *_ZERO),
        ),
        EvaluationDomain.PRODUCT: (
            ("route_count", MetricType.COUNT, MetricDirection.EXACT, 4),
            ("catalog_driven_route_ratio", *_FULL),
            ("false_ready_count", *_ZERO),
            ("frontend_llm_call_count", *_ZERO),
            ("secret_leakage_count", *_ZERO),
            ("snapshot_refresh_identity", *_BOOL),
            ("waiting_user_ux", *_BOOL),
            ("resume_success", *_BOOL),
            ("run_refresh_recovery", *_BOOL),
            ("story_snapshot_render", *_BOOL),
            ("experience_snapshot_render", *_BOOL),
            ("resource_snapshot_render", *_BOOL),
            ("qualifier_visibility", *_BOOL),
            ("safety_visibility", *_BOOL),
            ("unknown_as_known", *_ZERO),
            ("hidden_sponsorship", *_ZERO),
            ("critical_responsive_failure", *_ZERO),
            ("critical_accessibility_failure", *_ZERO),
            ("product_journey_completion", *_BOOL),
            ("location_disclosure_visibility", *_BOOL),
        ),
        EvaluationDomain.CROSS_LAYER: (
            ("catalog_version_consistency", *_BOOL),
            ("run_to_story_version_consistency", *_BOOL),
            ("story_to_experience_consistency", *_BOOL),
            ("experience_to_resource_consistency", *_BOOL),
            ("mandatory_anchor_end_to_end", *_BOOL),
            ("snapshot_hash_stability", *_BOOL),
            ("knowledge_mutation", *_ZERO),
            ("story_mutation", *_ZERO),
            ("experience_mutation", *_ZERO),
            ("itinerary_mutation", *_ZERO),
            ("locality_as_anchor_conflation", *_ZERO),
            ("false_exact_location", *_ZERO),
        ),
    }
    return tuple(
        _metric(domain, name, metric_type, direction, threshold)
        for domain, domain_specs in specs.items()
        for name, metric_type, direction, threshold in domain_specs
    )


class MetricRegistry:
    def __init__(self, metrics: Iterable[EvalMetric]) -> None:
        items = tuple(metrics)
        ids = [metric.metric_id for metric in items]
        if len(ids) != len(set(ids)):
            raise ValueError("metric IDs must be unique")
        self._metrics = items
        self._by_id = {metric.metric_id: metric for metric in items}

    def get(self, metric_id: str) -> EvalMetric | None:
        return self._by_id.get(metric_id)

    def list(self, domain: EvaluationDomain | None = None) -> tuple[EvalMetric, ...]:
        if domain is None:
            return self._metrics
        return tuple(metric for metric in self._metrics if metric.domain is domain)


FORMAL_METRICS = MetricRegistry(_build_metrics())


class EvaluationRegistry:
    """Validate all cross-references before any benchmark execution."""

    def __init__(
        self,
        *,
        suites: Iterable[EvalSuite],
        cases: Iterable[EvalCase],
        metrics: MetricRegistry = FORMAL_METRICS,
    ) -> None:
        self.suites = tuple(suites)
        self.cases = tuple(cases)
        self.metrics = metrics
        self._require_unique("suite", [suite.suite_id for suite in self.suites])
        self._require_unique("case", [case.case_id for case in self.cases])
        suites_by_id = {suite.suite_id: suite for suite in self.suites}
        cases_by_id = {case.case_id: case for case in self.cases}
        for suite in self.suites:
            for case_id in suite.case_ids:
                case = cases_by_id.get(case_id)
                if case is None:
                    raise ValueError(f"suite references unknown case: {case_id}")
                if case.suite_id != suite.suite_id:
                    raise ValueError(f"case suite mismatch: {case_id}")
        for case in self.cases:
            if case.suite_id not in suites_by_id:
                raise ValueError(f"case references unknown suite: {case.suite_id}")
            referenced = []
            for metric_id in case.metric_ids:
                metric = metrics.get(metric_id)
                if metric is None:
                    raise ValueError(f"case references unknown metric: {metric_id}")
                referenced.append(metric)
            expected_hard = case.severity is EvalSeverity.HARD
            if any(metric.hard_gate != expected_hard for metric in referenced):
                raise ValueError(f"case severity does not match metric gates: {case.case_id}")
            if case.requires_llm and expected_hard:
                raise ValueError(f"hard case cannot require an LLM: {case.case_id}")

    @staticmethod
    def _require_unique(kind: str, values: list[str]) -> None:
        if len(values) != len(set(values)):
            raise ValueError(f"{kind} IDs must be unique")
