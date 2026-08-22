import pytest

from app.evaluation import (
    EvalCase,
    EvalMetric,
    EvalSuite,
    EvaluationDomain,
    EvaluationRegistry,
    FORMAL_METRICS,
    MetricRegistry,
)


EXPECTED_NAMES = {
    EvaluationDomain.PLANNING: {
        "runtime_completion", "mandatory_anchor_recall", "mandatory_identity_preservation",
        "candidate_provenance", "fake_poi_count", "route_feasibility",
        "road_data_completeness", "meal_coverage", "meal_route_feasible",
        "provider_identity_mismatch", "snapshot_context_preservation",
        "waiting_user_resume", "runtime_recovery",
    },
    EvaluationDomain.KNOWLEDGE: {
        "evidence_coverage", "production_ineligible_leakage", "citation_identity_accuracy",
        "qualifier_preservation", "claim_type_preservation", "unsupported_fact_count",
        "internal_only_leakage", "review_required_leakage",
        "answerability_false_positive", "answerability_false_negative",
    },
    EvaluationDomain.STORY: {
        "story_chapter_count_contract", "story_grounding_coverage",
        "production_claim_leakage", "citation_hallucination", "qualifier_violation",
        "claim_type_promotion", "context_fact_violation", "story_anchor_binding",
        "name_only_binding", "knowledge_mutation", "itinerary_mutation",
    },
    EvaluationDomain.EXPERIENCE: {
        "experience_activity_count_contract", "grounding_coverage", "unsafe_instruction",
        "environmental_harm", "cultural_property_harm", "child_supervision_violation",
        "observation_hallucination", "specific_observable_without_evidence",
        "forced_purchase", "restricted_area_instruction", "water_hazard", "road_hazard",
        "wildlife_hazard", "name_only_binding", "knowledge_mutation", "story_mutation",
        "itinerary_mutation", "planning_mutation",
    },
    EvaluationDomain.RESOURCES: {
        "fake_resource", "unverified_curated_resource", "name_only_identity",
        "price_hallucination", "availability_hallucination", "provenance_coverage",
        "freshness_visibility", "sponsorship_ranking_influence", "hidden_sponsorship",
        "mandatory_commerce", "detour_feasibility", "knowledge_mutation",
        "story_mutation", "experience_mutation", "itinerary_mutation",
    },
    EvaluationDomain.PRODUCT: {
        "route_count", "catalog_driven_route_ratio", "false_ready_count", "frontend_llm_call_count",
        "secret_leakage_count", "snapshot_refresh_identity", "waiting_user_ux",
        "resume_success", "run_refresh_recovery", "story_snapshot_render",
        "experience_snapshot_render", "resource_snapshot_render", "qualifier_visibility",
        "safety_visibility", "unknown_as_known", "hidden_sponsorship",
        "critical_responsive_failure", "critical_accessibility_failure",
        "product_journey_completion",
    },
    EvaluationDomain.CROSS_LAYER: {
        "catalog_version_consistency", "run_to_story_version_consistency",
        "story_to_experience_consistency", "experience_to_resource_consistency",
        "mandatory_anchor_end_to_end", "snapshot_hash_stability", "knowledge_mutation",
        "story_mutation", "experience_mutation", "itinerary_mutation",
    },
}


def test_formal_registry_contains_every_required_metric_once():
    metrics = FORMAL_METRICS.list()
    assert len(metrics) == len({metric.metric_id for metric in metrics})
    for domain, names in EXPECTED_NAMES.items():
        assert {metric.metric_id.split(".", 1)[1] for metric in FORMAL_METRICS.list(domain)} == names


def test_formal_hard_metrics_are_all_deterministic():
    assert not [
        metric for metric in FORMAL_METRICS.list()
        if metric.hard_gate and metric.evaluator_kind.value == "llm_judge"
    ]


def test_registry_rejects_duplicate_metric_ids():
    metric = FORMAL_METRICS.list()[0]
    with pytest.raises(ValueError, match="metric IDs must be unique"):
        MetricRegistry((metric, EvalMetric.model_validate(metric.model_dump())))


def _suite(case_id="planning.case"):
    return EvalSuite(
        suite_id="planning.core",
        name="Planning",
        description="Planning contracts.",
        domain="planning",
        version="1.0.0",
        case_ids=(case_id,),
        required_for_route_readiness=True,
    )


def _case(**changes):
    values = {
        "case_id": "planning.case",
        "suite_id": "planning.core",
        "name": "Planning case",
        "description": "A hard deterministic case.",
        "severity": "hard",
        "input_fixture": "fixture.json",
        "expected_contract": {"value": True},
        "metric_ids": ("planning.runtime_completion",),
    }
    values.update(changes)
    return EvalCase(**values)


def test_evaluation_registry_validates_suite_case_and_metric_references():
    registry = EvaluationRegistry(suites=(_suite(),), cases=(_case(),))
    assert registry.cases[0].case_id == "planning.case"
    with pytest.raises(ValueError, match="suite IDs must be unique"):
        EvaluationRegistry(suites=(_suite(), _suite()), cases=(_case(),))
    with pytest.raises(ValueError, match="case IDs must be unique"):
        EvaluationRegistry(suites=(_suite(),), cases=(_case(), _case()))
    with pytest.raises(ValueError, match="unknown metric"):
        EvaluationRegistry(
            suites=(_suite(),), cases=(_case(metric_ids=("planning.missing",)),)
        )


def test_evaluation_registry_enforces_hard_soft_boundary():
    with pytest.raises(ValueError, match="severity does not match"):
        EvaluationRegistry(
            suites=(_suite(),), cases=(_case(severity="soft"),)
        )
    with pytest.raises(ValueError, match="hard case cannot require an LLM"):
        EvaluationRegistry(
            suites=(_suite(),), cases=(_case(requires_llm=True),)
        )
