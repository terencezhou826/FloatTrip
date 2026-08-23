from __future__ import annotations

import inspect

import pytest

from app.evaluation import BenchmarkCorpus, BenchmarkRunner
from app.rollout import (
    RolloutLayer,
    RolloutLayerStatus,
    RouteRolloutAuditor,
    RouteRolloutStatus,
)


def _auditor_and_report():
    corpus = BenchmarkCorpus.load()
    return RouteRolloutAuditor(corpus), BenchmarkRunner(corpus).run()


def test_ready_route_audit_reuses_m7_readiness():
    auditor, report = _auditor_and_report()
    ready_route = next(item.route_id for item in report.route_readiness if item.ready)

    audit = auditor.audit(ready_route, report)

    assert audit.rollout_status is RouteRolloutStatus.READY
    assert audit.readiness.ready
    assert all(
        item.status in {RolloutLayerStatus.PASS, RolloutLayerStatus.OPTIONAL}
        for item in audit.layers
    )


def test_non_ready_routes_report_stage_from_missing_capabilities():
    auditor, report = _auditor_and_report()
    coming_soon_routes = [
        item.route_id for item in report.route_readiness if not item.ready
    ]
    for route_id in coming_soon_routes:
        audit = auditor.audit(route_id, report)
        assert audit.layer(RolloutLayer.CATALOG).status is RolloutLayerStatus.PASS
        assert audit.layer(RolloutLayer.RESOURCES).status in {
            RolloutLayerStatus.PASS,
            RolloutLayerStatus.OPTIONAL,
        }
        assert audit.layer(RolloutLayer.PRODUCT).status is RolloutLayerStatus.MISSING
        assert audit.rollout_status in {
            RouteRolloutStatus.POI_PENDING,
            RouteRolloutStatus.KNOWLEDGE_PENDING,
            RouteRolloutStatus.STORY_PENDING,
            RouteRolloutStatus.EXPERIENCE_PENDING,
            RouteRolloutStatus.VALIDATION_PENDING,
        }


def test_unknown_route_is_rejected():
    auditor, report = _auditor_and_report()
    with pytest.raises(ValueError, match="not available"):
        auditor.audit("unknown.route", report)


def test_rollout_framework_contains_no_route_or_city_business_values():
    import app.rollout.models as models
    import app.rollout.service as service

    source = inspect.getsource(models).lower() + inspect.getsource(service).lower()
    for value in (
        "jingwei", "nuwa", "shennong", "houyi", "fajiushan", "changzhi"
    ):
        assert value not in source
