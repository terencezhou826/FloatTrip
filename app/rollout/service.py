"""Project M7 readiness into an operational, route-neutral rollout audit."""

from __future__ import annotations

from app.evaluation import BenchmarkCorpus, BenchmarkReport, RouteReadinessEvaluator
from app.rollout.models import (
    RolloutLayer,
    RolloutLayerAudit,
    RolloutLayerStatus,
    RouteRolloutAudit,
    RouteRolloutStatus,
)


class RouteRolloutAuditor:
    def __init__(self, corpus: BenchmarkCorpus | None = None, repository=None) -> None:
        self.corpus = corpus or BenchmarkCorpus.load()
        self.readiness = RouteReadinessEvaluator(self.corpus, repository=repository)

    def audit(self, route_id: str, report: BenchmarkReport) -> RouteRolloutAudit:
        profiles = self.readiness.evaluate(report)
        profile = next((item for item in profiles if item.route_id == route_id), None)
        if profile is None:
            raise ValueError(f"route is not available to readiness evaluation: {route_id}")
        layers = (
            self._required_layer(
                RolloutLayer.CATALOG,
                profile.catalog_complete,
                "Catalog Region, Theme, Route, and Anchor references are complete.",
                "Catalog references are incomplete.",
                ("catalog_complete",),
            ),
            self._required_layer(
                RolloutLayer.POI,
                profile.mandatory_spatial_identity,
                "Every mandatory Anchor has a production-capable verified spatial identity.",
                "A mandatory Anchor lacks a production-capable verified spatial identity.",
                ("mandatory_spatial_identity",),
            ),
            self._required_layer(
                RolloutLayer.KNOWLEDGE,
                profile.knowledge_available,
                "Production-eligible Knowledge and evidence gates pass.",
                "Production-eligible Knowledge prerequisites are missing.",
                ("knowledge_available",),
            ),
            self._required_layer(
                RolloutLayer.STORY,
                profile.story_available,
                "Verified grounded Story content passes hard metrics.",
                "Verified Story prerequisites are missing.",
                ("story_available",),
            ),
            self._required_layer(
                RolloutLayer.EXPERIENCE,
                profile.experience_available,
                "Verified safe Experience content passes hard metrics.",
                "Verified Experience prerequisites are missing.",
                ("experience_available",),
            ),
            self._resource_layer(profile),
            self._required_layer(
                RolloutLayer.EVALUATION,
                profile.golden_eval_cases and profile.snapshot_persistence,
                "Route-scoped golden evaluation and snapshot evidence pass.",
                "Route-scoped golden evaluation or snapshot evidence is missing.",
                tuple(
                    item
                    for item in ("golden_eval_cases", "snapshot_persistence")
                    if item in profile.missing_requirements
                ),
            ),
            self._required_layer(
                RolloutLayer.PRODUCT,
                profile.ready,
                "M7 readiness is READY and Product may expose the route as ready.",
                "M7 readiness remains COMING_SOON.",
                profile.missing_requirements,
            ),
        )
        return RouteRolloutAudit(
            package_id=profile.package_id,
            route_id=profile.route_id,
            rollout_status=self._rollout_status(profile),
            readiness=profile.to_result(),
            layers=layers,
        )

    @staticmethod
    def _required_layer(
        layer: RolloutLayer,
        passed: bool,
        pass_details: str,
        missing_details: str,
        missing_requirements: tuple[str, ...],
    ) -> RolloutLayerAudit:
        return RolloutLayerAudit(
            layer=layer,
            status=(RolloutLayerStatus.PASS if passed else RolloutLayerStatus.MISSING),
            details=pass_details if passed else missing_details,
            missing_requirements=() if passed else missing_requirements,
        )

    @staticmethod
    def _resource_layer(profile) -> RolloutLayerAudit:
        if not profile.resources_declared:
            return RolloutLayerAudit(
                layer=RolloutLayer.RESOURCES,
                status=RolloutLayerStatus.OPTIONAL,
                details="Resources are not declared and do not block cultural READY.",
            )
        return RolloutLayerAudit(
            layer=RolloutLayer.RESOURCES,
            status=(
                RolloutLayerStatus.PASS
                if profile.resources_available
                else RolloutLayerStatus.MISSING
            ),
            details=(
                "Declared Resource capability passes."
                if profile.resources_available
                else "Declared Resource capability is incomplete."
            ),
            missing_requirements=(
                () if profile.resources_available else ("resources_available",)
            ),
        )

    @staticmethod
    def _rollout_status(profile) -> RouteRolloutStatus:
        if profile.ready:
            return RouteRolloutStatus.READY
        if not profile.catalog_complete:
            return RouteRolloutStatus.BLOCKED
        if not profile.mandatory_spatial_identity:
            return RouteRolloutStatus.POI_PENDING
        if not profile.knowledge_available:
            return RouteRolloutStatus.KNOWLEDGE_PENDING
        if not profile.story_available:
            return RouteRolloutStatus.STORY_PENDING
        if not profile.experience_available:
            return RouteRolloutStatus.EXPERIENCE_PENDING
        return RouteRolloutStatus.VALIDATION_PENDING


def audit_route_readiness(
    route_id: str,
    report: BenchmarkReport,
    *,
    corpus: BenchmarkCorpus | None = None,
    repository=None,
) -> RouteRolloutAudit:
    return RouteRolloutAuditor(corpus=corpus, repository=repository).audit(
        route_id, report
    )
