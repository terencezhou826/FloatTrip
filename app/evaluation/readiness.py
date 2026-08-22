"""Generic route-readiness evaluation from Catalog and benchmark evidence."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, StrictBool

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    ExperienceVerificationStatus,
    StoryVerificationStatus,
)
from app.evaluation.corpus import BenchmarkCorpus
from app.evaluation.models import (
    BenchmarkReport,
    EvalStatus,
    EvaluationDomain,
    EvaluationModel,
    RouteReadinessResult,
)
from app.product.catalog import CatalogProductService


CATALOG_ROOT = Path(__file__).resolve().parents[2] / "content" / "catalog"


class RouteReadinessProfile(EvaluationModel):
    profile_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    package_id: str
    route_id: str
    catalog_complete: StrictBool
    mandatory_poi_identity: StrictBool
    planning_available: StrictBool
    knowledge_available: StrictBool
    story_available: StrictBool
    experience_available: StrictBool
    snapshot_persistence: StrictBool
    product_renderability: StrictBool
    golden_eval_cases: StrictBool
    resources_declared: StrictBool
    resources_available: StrictBool
    ready: StrictBool
    availability: str
    passed_requirements: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()

    def to_result(self) -> RouteReadinessResult:
        return RouteReadinessResult(
            route_id=self.route_id,
            ready=self.ready,
            availability=self.availability,
            passed_requirements=self.passed_requirements,
            missing_requirements=self.missing_requirements,
            optional_capabilities={"resources_available": self.resources_available},
        )


class RouteReadinessEvaluator:
    REQUIRED = (
        "catalog_complete",
        "planning_available",
        "knowledge_available",
        "story_available",
        "experience_available",
        "snapshot_persistence",
        "product_renderability",
        "golden_eval_cases",
    )

    def __init__(self, corpus: BenchmarkCorpus, repository=None) -> None:
        self.corpus = corpus
        self.repository = repository or FileCatalogLoader(CATALOG_ROOT).load()
        self.product = CatalogProductService(self.repository)

    def evaluate(self, report: BenchmarkReport) -> tuple[RouteReadinessProfile, ...]:
        profiles = []
        for manifest in self.repository.list_manifests():
            package = self.repository.get_package(manifest.package_id)
            if package is None or not manifest.enabled:
                continue
            for route in package.routes:
                profiles.append(self._route_profile(manifest.package_id, route, report))
        return tuple(profiles)

    def _route_profile(self, package_id, route, report) -> RouteReadinessProfile:
        catalog_complete = bool(
            self.repository.get_theme(route.theme_id)
            and self.repository.get_region(route.primary_region_id)
            and route.coverage_region_ids
            and all(self.repository.get_region(item) for item in route.coverage_region_ids)
            and route.anchor_ids
            and all(self.repository.get_anchor(item) for item in route.anchor_ids)
        )
        mandatory_identity = bool(route.mandatory_anchor_ids) and all(
            self.repository.list_verified_bindings_for_anchor(anchor_id)
            for anchor_id in route.mandatory_anchor_ids
        )
        planning = mandatory_identity and self._domain_passes(
            report, EvaluationDomain.PLANNING
        )
        claims = tuple(
            claim
            for claim in self.repository.list_claims()
            if (
                route.theme_id in claim.theme_ids
                or bool(set(route.anchor_ids).intersection(claim.anchor_ids))
            )
            and self.repository.is_claim_production_eligible(claim.claim_id)
        )
        knowledge = bool(claims) and self._domain_passes(
            report, EvaluationDomain.KNOWLEDGE
        )
        stories = tuple(
            story
            for story in self.repository.list_stories(route.id)
            if story.enabled
            and story.verification_status is StoryVerificationStatus.VERIFIED
            and self._story_complete(story)
        )
        story_available = bool(stories) and knowledge and self._domain_passes(
            report, EvaluationDomain.STORY
        )
        experiences = tuple(
            experience
            for experience in self.repository.list_experiences(route_id=route.id)
            if experience.enabled
            and experience.verification_status is ExperienceVerificationStatus.VERIFIED
            and any(story.story_id == experience.story_id for story in stories)
            and self._experience_complete(experience)
        )
        experience_available = (
            bool(experiences)
            and story_available
            and self._domain_passes(report, EvaluationDomain.EXPERIENCE)
        )
        route_golden = (
            self.corpus.golden
            if self.corpus.golden.get("route_id") == route.id
            else None
        )
        snapshot_persistence = bool(
            route_golden and self._snapshot_identity_complete(route_golden)
        )
        product_renderability = bool(
            self.product.get_route(package_id, route.id)
            and self._domain_passes(report, EvaluationDomain.PRODUCT)
        )
        golden_eval_cases = bool(
            route_golden
            and self._route_cases_pass(report, route.id)
            and self._golden_contract_matches(package_id, route, route_golden)
        )
        resources_declared = bool(
            route_golden
            and route_golden.get("capability_expectation", {}).get(
                "resources_available", False
            )
        )
        resources_available = bool(
            resources_declared
            and route_golden
            and route_golden.get("snapshot_identity", {}).get("resource_snapshot_hash")
            and self._domain_passes(report, EvaluationDomain.RESOURCES)
        )
        values = {
            "catalog_complete": catalog_complete,
            "planning_available": planning,
            "knowledge_available": knowledge,
            "story_available": story_available,
            "experience_available": experience_available,
            "snapshot_persistence": snapshot_persistence,
            "product_renderability": product_renderability,
            "golden_eval_cases": golden_eval_cases,
        }
        ready = all(values.values())
        return RouteReadinessProfile(
            profile_version="1.0.0",
            package_id=package_id,
            route_id=route.id,
            catalog_complete=catalog_complete,
            mandatory_poi_identity=mandatory_identity,
            planning_available=planning,
            knowledge_available=knowledge,
            story_available=story_available,
            experience_available=experience_available,
            snapshot_persistence=snapshot_persistence,
            product_renderability=product_renderability,
            golden_eval_cases=golden_eval_cases,
            resources_declared=resources_declared,
            resources_available=resources_available,
            ready=ready,
            availability="ready" if ready else "coming_soon",
            passed_requirements=tuple(key for key in self.REQUIRED if values[key]),
            missing_requirements=tuple(key for key in self.REQUIRED if not values[key]),
        )

    def _story_complete(self, story) -> bool:
        chapters = self.repository.list_story_chapters(story.story_id)
        if tuple(item.chapter_id for item in chapters) != tuple(story.chapter_ids):
            return False
        claim_ids = set(story.knowledge_claim_ids)
        for chapter in chapters:
            if chapter.content_status is not StoryVerificationStatus.VERIFIED:
                return False
            claim_ids.update(chapter.required_claim_ids)
            claim_ids.update(chapter.optional_claim_ids)
        return all(self.repository.is_claim_production_eligible(item) for item in claim_ids)

    def _experience_complete(self, experience) -> bool:
        activities = self.repository.list_activities(experience.experience_id)
        if tuple(item.activity_id for item in activities) != tuple(experience.activity_ids):
            return False
        for activity in activities:
            if activity.content_status is not ExperienceVerificationStatus.VERIFIED:
                return False
            if not all(
                self.repository.is_claim_production_eligible(item)
                for item in (*activity.required_claim_ids, *activity.optional_claim_ids)
            ):
                return False
            if not all(self.repository.get_poi_binding(item) for item in activity.poi_binding_ids):
                return False
        return True

    @staticmethod
    def _domain_passes(report: BenchmarkReport, domain: EvaluationDomain) -> bool:
        results = tuple(
            result
            for suite in report.suite_results
            if suite.domain is domain
            for result in suite.results
            if result.hard_gate
        )
        return bool(results) and all(result.status is EvalStatus.PASS for result in results)

    def _route_cases_pass(self, report: BenchmarkReport, route_id: str) -> bool:
        scoped_ids = {
            case.case_id for case in self.corpus.cases if route_id in case.route_scope
        }
        results = tuple(
            result
            for suite in report.suite_results
            for result in suite.results
            if result.case_id in scoped_ids and result.hard_gate
        )
        return bool(results) and all(result.status is EvalStatus.PASS for result in results)

    @staticmethod
    def _snapshot_identity_complete(golden: dict) -> bool:
        identity = golden.get("snapshot_identity", {})
        required = (
            "run_id",
            "itinerary_id",
            "story_package_id",
            "story_snapshot_hash",
            "experience_package_id",
            "experience_snapshot_hash",
        )
        if not all(identity.get(item) for item in required):
            return False
        hashes = (
            identity.get("story_snapshot_hash"),
            identity.get("experience_snapshot_hash"),
            identity.get("resource_snapshot_hash"),
        )
        return all(
            value is None
            or (
                isinstance(value, str)
                and len(value) == 64
                and all(character in "0123456789abcdef" for character in value)
            )
            for value in hashes
        )

    def _golden_contract_matches(self, package_id: str, route, golden: dict) -> bool:
        package = self.repository.get_package(package_id)
        identity = golden.get("mandatory_anchor_identity", {})
        if package is None or (
            golden.get("package_id") != package_id
            or golden.get("catalog_schema_version") != package.manifest.schema_version
            or golden.get("catalog_content_version") != package.manifest.content_version
            or identity.get("anchor_id") not in route.mandatory_anchor_ids
        ):
            return False
        binding = self.repository.get_poi_binding(identity.get("binding_id", ""))
        if binding is None or (
            binding.anchor_id != identity.get("anchor_id")
            or binding.provider.value != identity.get("provider")
            or binding.external_poi_id != identity.get("external_poi_id")
            or not binding.is_runtime_eligible
        ):
            return False
        expected_chapters = tuple(golden.get("expected_chapter_ids", ()))
        expected_activities = tuple(golden.get("expected_activity_ids", ()))
        stories = self.repository.list_stories(route.id)
        experiences = self.repository.list_experiences(route_id=route.id)
        if not any(tuple(story.chapter_ids) == expected_chapters for story in stories):
            return False
        if not any(
            tuple(experience.activity_ids) == expected_activities
            for experience in experiences
        ):
            return False
        approved = tuple(golden.get("approved_claim_ids", ()))
        forbidden = tuple(golden.get("forbidden_claim_ids", ()))
        return bool(approved and forbidden) and all(
            self.repository.is_claim_production_eligible(claim_id)
            for claim_id in approved
        ) and all(
            not self.repository.is_claim_production_eligible(claim_id)
            for claim_id in forbidden
        )
