"""Cross-file integrity checks for a complete Catalog snapshot."""

from __future__ import annotations

from collections import Counter
import re

from app.catalog.models import (
    Anchor,
    CatalogTheme,
    ContentPackage,
    CuratedRoute,
    EvidenceRelation,
    ExperienceActivity,
    ExperienceAudience,
    ExperienceBlueprint,
    ExperienceContentMode,
    ExperienceObservationSafetyConstraint,
    ExperienceObservationTargetMode,
    ExperienceRiskLevel,
    ExperienceVerificationStatus,
    ExternalPoiBinding,
    KnowledgeClaim,
    KnowledgeEvidence,
    KnowledgeSource,
    KnowledgeVerificationStatus,
    Region,
    StoryBlueprint,
    StoryChapter,
    StoryVerificationStatus,
)


SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0"})


class CatalogValidationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = tuple(issues)
        super().__init__("catalog validation failed: " + "; ".join(issues))


def validate_catalog(regions: list[Region], packages: list[ContentPackage]) -> None:
    themes = [item for package in packages for item in package.themes]
    routes = [item for package in packages for item in package.routes]
    anchors = [item for package in packages for item in package.anchors]
    poi_bindings = [item for package in packages for item in package.poi_bindings]
    knowledge_sources = [
        item for package in packages for item in package.knowledge_sources
    ]
    knowledge_claims = [
        item for package in packages for item in package.knowledge_claims
    ]
    knowledge_evidence = [
        item for package in packages for item in package.knowledge_evidence
    ]
    story_blueprints = [
        item for package in packages for item in package.story_blueprints
    ]
    story_chapters = [
        item for package in packages for item in package.story_chapters
    ]
    experience_blueprints = [
        item for package in packages for item in package.experience_blueprints
    ]
    experience_activities = [
        item for package in packages for item in package.experience_activities
    ]
    issues: list[str] = []

    _check_duplicate_ids(
        regions,
        themes,
        routes,
        anchors,
        poi_bindings,
        knowledge_sources,
        knowledge_claims,
        knowledge_evidence,
        story_blueprints,
        story_chapters,
        experience_blueprints,
        experience_activities,
        issues,
    )

    region_ids = {item.id for item in regions}
    parents = {item.id: item.parent_id for item in regions}
    theme_ids = {item.id for item in themes}
    anchor_ids = {item.id for item in anchors}
    anchors_by_id = {item.id: item for item in anchors}
    source_ids = {item.source_id for item in knowledge_sources}
    claim_ids = {item.claim_id for item in knowledge_claims}
    sources_by_id = {item.source_id: item for item in knowledge_sources}
    routes_by_id = {item.id: item for item in routes}
    bindings_by_id = {item.binding_id: item for item in poi_bindings}
    stories_by_id = {item.story_id: item for item in story_blueprints}
    chapters_by_id = {item.chapter_id: item for item in story_chapters}
    experiences_by_id = {
        item.experience_id: item for item in experience_blueprints
    }
    activities_by_id = {
        item.activity_id: item for item in experience_activities
    }

    for region in regions:
        if region.parent_id and region.parent_id not in region_ids:
            issues.append(f"region {region.id} has missing parent {region.parent_id}")

    _check_region_cycles(regions, issues)

    package_ids = [package.manifest.package_id for package in packages]
    for duplicate in _duplicates(package_ids):
        issues.append(f"duplicate package_id {duplicate}")

    for package in packages:
        manifest = package.manifest
        if manifest.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            issues.append(
                f"package {manifest.package_id} uses unsupported schema_version "
                f"{manifest.schema_version}"
            )
        if manifest.region_id not in region_ids:
            issues.append(
                f"package {manifest.package_id} references missing region {manifest.region_id}"
            )

    for theme in themes:
        if theme.region_id not in region_ids:
            issues.append(f"theme {theme.id} references missing region {theme.region_id}")

    for anchor in anchors:
        if anchor.region_id not in region_ids:
            issues.append(f"anchor {anchor.id} references missing region {anchor.region_id}")

    for binding in poi_bindings:
        if binding.anchor_id not in anchor_ids:
            issues.append(
                f"binding {binding.binding_id} references missing anchor "
                f"{binding.anchor_id}"
            )

    for source in knowledge_sources:
        for region_id in source.region_ids:
            if region_id not in region_ids:
                issues.append(
                    f"knowledge source {source.source_id} references missing region "
                    f"{region_id}"
                )

    for claim in knowledge_claims:
        for region_id in claim.region_ids:
            if region_id not in region_ids:
                issues.append(
                    f"knowledge claim {claim.claim_id} references missing region "
                    f"{region_id}"
                )
        for theme_id in claim.theme_ids:
            if theme_id not in theme_ids:
                issues.append(
                    f"knowledge claim {claim.claim_id} references missing theme "
                    f"{theme_id}"
                )
        for anchor_id in claim.anchor_ids:
            if anchor_id not in anchor_ids:
                issues.append(
                    f"knowledge claim {claim.claim_id} references missing anchor "
                    f"{anchor_id}"
                )

    for evidence in knowledge_evidence:
        if evidence.claim_id not in claim_ids:
            issues.append(
                f"knowledge evidence {evidence.evidence_id} references missing claim "
                f"{evidence.claim_id}"
            )
        if evidence.source_id not in source_ids:
            issues.append(
                f"knowledge evidence {evidence.evidence_id} references missing source "
                f"{evidence.source_id}"
            )

    supported_verified_claim_ids = {
        evidence.claim_id
        for evidence in knowledge_evidence
        if evidence.verification_status is KnowledgeVerificationStatus.VERIFIED
        and evidence.evidence_relation is EvidenceRelation.SUPPORTS
        and (
            source := sources_by_id.get(evidence.source_id)
        ) is not None
        and source.verification_status is KnowledgeVerificationStatus.VERIFIED
    }
    for claim in knowledge_claims:
        if (
            claim.verification_status is KnowledgeVerificationStatus.VERIFIED
            and claim.claim_id not in supported_verified_claim_ids
        ):
            issues.append(
                f"verified knowledge claim {claim.claim_id} has no verified supporting "
                "evidence from a verified source"
            )

    coverage = calculate_evidence_coverage(
        knowledge_claims,
        knowledge_evidence,
        verified_source_ids={
            source.source_id
            for source in knowledge_sources
            if source.verification_status is KnowledgeVerificationStatus.VERIFIED
        },
    )
    if coverage < 1.0:
        issues.append(
            f"verified knowledge claim evidence coverage is {coverage:.3f}, not 1.000"
        )

    production_claim_ids = {
        claim.claim_id
        for claim in knowledge_claims
        if claim.verification_status is KnowledgeVerificationStatus.VERIFIED
        and claim.promotion_policy.status.value
        in {"allowed", "allowed_with_qualification"}
        and claim.claim_id in supported_verified_claim_ids
    }
    current_presence_claim_ids = {
        evidence.claim_id
        for evidence in knowledge_evidence
        if evidence.verification_status is KnowledgeVerificationStatus.VERIFIED
        and evidence.evidence_relation is EvidenceRelation.SUPPORTS
        and evidence.metadata.get("current_presence_verified") is True
        and (
            source := sources_by_id.get(evidence.source_id)
        ) is not None
        and source.verification_status is KnowledgeVerificationStatus.VERIFIED
        and evidence.claim_id in production_claim_ids
    }

    binding_identities: dict[tuple[str, str], set[str]] = {}
    for binding in poi_bindings:
        identity = (binding.provider.value, binding.external_poi_id)
        binding_identities.setdefault(identity, set()).add(binding.anchor_id)
    for (provider, external_poi_id), bound_anchor_ids in sorted(
        binding_identities.items()
    ):
        if len(bound_anchor_ids) > 1:
            issues.append(
                f"provider identity {provider}:{external_poi_id} has conflicting anchors "
                f"{', '.join(sorted(bound_anchor_ids))}"
            )

    for route in routes:
        if route.primary_region_id not in region_ids:
            issues.append(
                f"route {route.id} references missing primary region "
                f"{route.primary_region_id}"
            )
        for coverage_id in route.coverage_region_ids:
            if coverage_id not in region_ids:
                issues.append(
                    f"route {route.id} references missing coverage region {coverage_id}"
                )
        if route.primary_region_id in region_ids:
            incompatible = [
                coverage_id
                for coverage_id in route.coverage_region_ids
                if coverage_id in region_ids
                and not is_same_or_descendant(
                    coverage_id, route.primary_region_id, parents
                )
            ]
            if incompatible:
                issues.append(
                    f"route {route.id} primary region {route.primary_region_id} "
                    f"is incompatible with coverage {', '.join(incompatible)}"
                )
        if route.theme_id not in theme_ids:
            issues.append(f"route {route.id} references missing theme {route.theme_id}")
        for anchor_id in route.anchor_ids:
            if anchor_id not in anchor_ids:
                issues.append(f"route {route.id} references missing anchor {anchor_id}")
                continue
            anchor = anchors_by_id[anchor_id]
            covered = any(
                coverage_id in region_ids
                and is_same_or_descendant(anchor.region_id, coverage_id, parents)
                for coverage_id in route.coverage_region_ids
            )
            if not covered:
                issues.append(
                    f"route {route.id} anchor {anchor_id} region {anchor.region_id} "
                    "is outside route coverage"
                )

    for package in packages:
        package_story_ids = {item.story_id for item in package.story_blueprints}
        package_chapter_ids = {item.chapter_id for item in package.story_chapters}
        for story in package.story_blueprints:
            _validate_story(
                story,
                package.manifest.package_id,
                package_chapter_ids,
                chapters_by_id,
                region_ids,
                theme_ids,
                routes_by_id,
                claim_ids,
                production_claim_ids,
                current_presence_claim_ids,
                issues,
            )
        for chapter in package.story_chapters:
            _validate_story_chapter(
                chapter,
                package_story_ids,
                stories_by_id,
                anchor_ids,
                bindings_by_id,
                claim_ids,
                production_claim_ids,
                issues,
            )
        package_experience_ids = {
            item.experience_id for item in package.experience_blueprints
        }
        package_activity_ids = {
            item.activity_id for item in package.experience_activities
        }
        for experience in package.experience_blueprints:
            _validate_experience(
                experience,
                package.manifest.package_id,
                package_activity_ids,
                activities_by_id,
                region_ids,
                theme_ids,
                routes_by_id,
                stories_by_id,
                issues,
            )
        for activity in package.experience_activities:
            _validate_experience_activity(
                activity,
                package_experience_ids,
                experiences_by_id,
                stories_by_id,
                chapters_by_id,
                anchor_ids,
                bindings_by_id,
                claim_ids,
                production_claim_ids,
                issues,
            )

    if issues:
        raise CatalogValidationError(issues)


def _check_duplicate_ids(
    regions: list[Region],
    themes: list[CatalogTheme],
    routes: list[CuratedRoute],
    anchors: list[Anchor],
    poi_bindings: list[ExternalPoiBinding],
    knowledge_sources: list[KnowledgeSource],
    knowledge_claims: list[KnowledgeClaim],
    knowledge_evidence: list[KnowledgeEvidence],
    story_blueprints: list[StoryBlueprint],
    story_chapters: list[StoryChapter],
    experience_blueprints: list[ExperienceBlueprint],
    experience_activities: list[ExperienceActivity],
    issues: list[str],
) -> None:
    typed_items = (
        [("region", item.id) for item in regions]
        + [("theme", item.id) for item in themes]
        + [("route", item.id) for item in routes]
        + [("anchor", item.id) for item in anchors]
        + [("poi_binding", item.binding_id) for item in poi_bindings]
        + [("knowledge_source", item.source_id) for item in knowledge_sources]
        + [("knowledge_claim", item.claim_id) for item in knowledge_claims]
        + [("knowledge_evidence", item.evidence_id) for item in knowledge_evidence]
        + [("story", item.story_id) for item in story_blueprints]
        + [("story_chapter", item.chapter_id) for item in story_chapters]
        + [
            ("experience", item.experience_id)
            for item in experience_blueprints
        ]
        + [
            ("experience_activity", item.activity_id)
            for item in experience_activities
        ]
    )
    counts = Counter(item_id for _, item_id in typed_items)
    for duplicate in sorted(item_id for item_id, count in counts.items() if count > 1):
        kinds = sorted(kind for kind, item_id in typed_items if item_id == duplicate)
        issues.append(f"duplicate id {duplicate} ({', '.join(kinds)})")


def _validate_story(
    story: StoryBlueprint,
    package_id: str,
    package_chapter_ids: set[str],
    chapters_by_id: dict[str, StoryChapter],
    region_ids: set[str],
    theme_ids: set[str],
    routes_by_id: dict[str, CuratedRoute],
    claim_ids: set[str],
    production_claim_ids: set[str],
    current_presence_claim_ids: set[str],
    issues: list[str],
) -> None:
    if story.package_id != package_id:
        issues.append(
            f"story {story.story_id} package_id {story.package_id} does not match "
            f"owning package {package_id}"
        )
    if story.region_id not in region_ids:
        issues.append(f"story {story.story_id} references missing region {story.region_id}")
    if story.theme_id not in theme_ids:
        issues.append(f"story {story.story_id} references missing theme {story.theme_id}")
    route = routes_by_id.get(story.route_id)
    if route is None:
        issues.append(f"story {story.story_id} references missing route {story.route_id}")
    elif route.theme_id != story.theme_id:
        issues.append(
            f"story {story.story_id} theme {story.theme_id} does not match route theme"
        )
    if story.enabled and story.verification_status is not StoryVerificationStatus.VERIFIED:
        issues.append(f"enabled story {story.story_id} must be verified")
    for duplicate in _duplicates(story.chapter_ids):
        issues.append(f"story {story.story_id} repeats chapter {duplicate}")
    for chapter_id in story.chapter_ids:
        if chapter_id not in package_chapter_ids:
            issues.append(f"story {story.story_id} references missing chapter {chapter_id}")
    chapters = [
        chapters_by_id[chapter_id]
        for chapter_id in story.chapter_ids
        if chapter_id in chapters_by_id
    ]
    sequences = [chapter.sequence for chapter in chapters]
    if len(sequences) != len(set(sequences)):
        issues.append(f"story {story.story_id} has duplicate chapter sequence")
    if sorted(sequences) != list(range(len(sequences))):
        issues.append(f"story {story.story_id} chapter sequence must be contiguous from 0")
    for claim_id in story.knowledge_claim_ids:
        _check_story_claim(story.story_id, claim_id, claim_ids, production_claim_ids, issues)


def _validate_story_chapter(
    chapter: StoryChapter,
    package_story_ids: set[str],
    stories_by_id: dict[str, StoryBlueprint],
    anchor_ids: set[str],
    bindings_by_id: dict[str, ExternalPoiBinding],
    claim_ids: set[str],
    production_claim_ids: set[str],
    issues: list[str],
) -> None:
    if chapter.story_id not in package_story_ids:
        issues.append(
            f"story chapter {chapter.chapter_id} references missing story "
            f"{chapter.story_id}"
        )
        return
    story = stories_by_id[chapter.story_id]
    if chapter.chapter_id not in story.chapter_ids:
        issues.append(f"orphan story chapter {chapter.chapter_id}")
    if story.enabled and chapter.content_status is not StoryVerificationStatus.VERIFIED:
        issues.append(
            f"chapter {chapter.chapter_id} in enabled story must be verified"
        )
    for anchor_id in chapter.anchor_ids:
        if anchor_id not in anchor_ids:
            issues.append(
                f"story chapter {chapter.chapter_id} references missing anchor {anchor_id}"
            )
    for binding_id in chapter.poi_binding_ids:
        binding = bindings_by_id.get(binding_id)
        if binding is None:
            issues.append(
                f"story chapter {chapter.chapter_id} references missing POI binding "
                f"{binding_id}"
            )
        elif not binding.is_runtime_eligible:
            issues.append(
                f"story chapter {chapter.chapter_id} POI binding {binding_id} is not verified"
            )
        elif binding.anchor_id not in chapter.anchor_ids:
            issues.append(
                f"story chapter {chapter.chapter_id} POI binding {binding_id} "
                "does not belong to a chapter anchor"
            )
    if set(chapter.required_claim_ids).intersection(chapter.optional_claim_ids):
        issues.append(
            f"story chapter {chapter.chapter_id} repeats a required Claim as optional"
        )
    bound_claim_ids = set(chapter.required_claim_ids) | set(chapter.optional_claim_ids)
    if not bound_claim_ids.issubset(story.knowledge_claim_ids):
        issues.append(
            f"story chapter {chapter.chapter_id} references Claim outside blueprint"
        )
    for claim_id in bound_claim_ids:
        _check_story_claim(
            chapter.chapter_id,
            claim_id,
            claim_ids,
            production_claim_ids,
            issues,
        )
    curatorial_text = " ".join(
        (
            chapter.narrative_goal,
            chapter.opening_hook,
            chapter.transition_goal,
            chapter.visitor_takeaway,
        )
    )
    if re.search(r"\d{4}年", curatorial_text) or any(
        marker in curatorial_text
        for marker in ("经纬度", "坐标", "考古证明", "文保等级", "景区等级")
    ):
        issues.append(
            f"story chapter {chapter.chapter_id} curatorial intent contains factual detail"
        )


def _check_story_claim(
    owner_id: str,
    claim_id: str,
    claim_ids: set[str],
    production_claim_ids: set[str],
    issues: list[str],
) -> None:
    if claim_id not in claim_ids:
        issues.append(f"story item {owner_id} references missing Claim {claim_id}")
    elif claim_id not in production_claim_ids:
        issues.append(f"story item {owner_id} Claim {claim_id} is not production eligible")


def _validate_experience(
    experience: ExperienceBlueprint,
    package_id: str,
    package_activity_ids: set[str],
    activities_by_id: dict[str, ExperienceActivity],
    region_ids: set[str],
    theme_ids: set[str],
    routes_by_id: dict[str, CuratedRoute],
    stories_by_id: dict[str, StoryBlueprint],
    issues: list[str],
) -> None:
    if experience.package_id != package_id:
        issues.append(
            f"experience {experience.experience_id} package_id "
            f"{experience.package_id} does not match owning package {package_id}"
        )
    if experience.region_id not in region_ids:
        issues.append(
            f"experience {experience.experience_id} references missing region "
            f"{experience.region_id}"
        )
    if experience.theme_id not in theme_ids:
        issues.append(
            f"experience {experience.experience_id} references missing theme "
            f"{experience.theme_id}"
        )
    route = routes_by_id.get(experience.route_id)
    if route is None:
        issues.append(
            f"experience {experience.experience_id} references missing route "
            f"{experience.route_id}"
        )
    elif route.theme_id != experience.theme_id:
        issues.append(
            f"experience {experience.experience_id} theme does not match route theme"
        )
    story = stories_by_id.get(experience.story_id)
    if story is None:
        issues.append(
            f"experience {experience.experience_id} references missing story "
            f"{experience.story_id}"
        )
    elif (
        story.route_id != experience.route_id
        or story.theme_id != experience.theme_id
        or story.region_id != experience.region_id
    ):
        issues.append(
            f"experience {experience.experience_id} does not match Story scope"
        )
    if (
        experience.enabled
        and experience.verification_status
        is not ExperienceVerificationStatus.VERIFIED
    ):
        issues.append(
            f"enabled experience {experience.experience_id} must be verified"
        )
    for duplicate in _duplicates(experience.activity_ids):
        issues.append(
            f"experience {experience.experience_id} repeats activity {duplicate}"
        )
    for activity_id in experience.activity_ids:
        if activity_id not in package_activity_ids:
            issues.append(
                f"experience {experience.experience_id} references missing activity "
                f"{activity_id}"
            )
    activities = [
        activities_by_id[activity_id]
        for activity_id in experience.activity_ids
        if activity_id in activities_by_id
    ]
    sequences = [activity.sequence for activity in activities]
    if len(sequences) != len(set(sequences)):
        issues.append(
            f"experience {experience.experience_id} has duplicate activity sequence"
        )
    if sorted(sequences) != list(range(len(sequences))):
        issues.append(
            f"experience {experience.experience_id} activity sequence must be "
            "contiguous from 0"
        )
    duration = sum(item.estimated_duration_sec for item in activities)
    if activities and duration != experience.estimated_total_duration_sec:
        issues.append(
            f"experience {experience.experience_id} estimated duration does not "
            "match activities"
        )


def _validate_experience_activity(
    activity: ExperienceActivity,
    package_experience_ids: set[str],
    experiences_by_id: dict[str, ExperienceBlueprint],
    stories_by_id: dict[str, StoryBlueprint],
    chapters_by_id: dict[str, StoryChapter],
    anchor_ids: set[str],
    bindings_by_id: dict[str, ExternalPoiBinding],
    claim_ids: set[str],
    production_claim_ids: set[str],
    issues: list[str],
) -> None:
    if activity.experience_id not in package_experience_ids:
        issues.append(
            f"experience activity {activity.activity_id} references missing experience "
            f"{activity.experience_id}"
        )
        return
    experience = experiences_by_id[activity.experience_id]
    if activity.activity_id not in experience.activity_ids:
        issues.append(f"orphan experience activity {activity.activity_id}")
    if (
        experience.enabled
        and activity.content_status is not ExperienceVerificationStatus.VERIFIED
    ):
        issues.append(
            f"activity {activity.activity_id} in enabled experience must be verified"
        )
    story = stories_by_id.get(experience.story_id)
    for chapter_id in activity.story_chapter_ids:
        chapter = chapters_by_id.get(chapter_id)
        if chapter is None:
            issues.append(
                f"experience activity {activity.activity_id} references missing story "
                f"chapter {chapter_id}"
            )
        elif story is None or chapter_id not in story.chapter_ids:
            issues.append(
                f"experience activity {activity.activity_id} references chapter "
                "outside Story"
            )
    for anchor_id in activity.anchor_ids:
        if anchor_id not in anchor_ids:
            issues.append(
                f"experience activity {activity.activity_id} references missing anchor "
                f"{anchor_id}"
            )
    for binding_id in activity.poi_binding_ids:
        binding = bindings_by_id.get(binding_id)
        if binding is None:
            issues.append(
                f"experience activity {activity.activity_id} references missing POI "
                f"binding {binding_id}"
            )
        elif not binding.is_runtime_eligible:
            issues.append(
                f"experience activity {activity.activity_id} POI binding "
                f"{binding_id} is not verified"
            )
        elif binding.anchor_id not in activity.anchor_ids:
            issues.append(
                f"experience activity {activity.activity_id} POI binding "
                f"{binding_id} does not belong to an activity anchor"
            )
    if set(activity.required_claim_ids).intersection(activity.optional_claim_ids):
        issues.append(
            f"experience activity {activity.activity_id} repeats a required Claim "
            "as optional"
        )
    bound_claim_ids = set(activity.required_claim_ids) | set(
        activity.optional_claim_ids
    )
    if (
        activity.content_mode is ExperienceContentMode.KNOWLEDGE_GROUNDED
        and not activity.required_claim_ids
    ):
        issues.append(
            f"knowledge-grounded activity {activity.activity_id} requires a Claim"
        )
    if (
        activity.content_mode is ExperienceContentMode.FACILITATION_ONLY
        and bound_claim_ids
    ):
        issues.append(
            f"facilitation-only activity {activity.activity_id} cannot bind Claims"
        )
    if story is not None and not bound_claim_ids.issubset(story.knowledge_claim_ids):
        issues.append(
            f"experience activity {activity.activity_id} references Claim outside Story"
        )
    chapter_claim_ids = {
        claim_id
        for chapter_id in activity.story_chapter_ids
        if (chapter := chapters_by_id.get(chapter_id)) is not None
        for claim_id in chapter.required_claim_ids + chapter.optional_claim_ids
    }
    if activity.story_chapter_ids and not bound_claim_ids.issubset(chapter_claim_ids):
        issues.append(
            f"experience activity {activity.activity_id} references Claim outside "
            "bound Story Chapter"
        )
    for claim_id in bound_claim_ids:
        if claim_id not in claim_ids:
            issues.append(
                f"experience activity {activity.activity_id} references missing Claim "
                f"{claim_id}"
            )
        elif claim_id not in production_claim_ids:
            issues.append(
                f"experience activity {activity.activity_id} Claim {claim_id} is not "
                "production eligible"
            )
    target = activity.observation_target
    if target.target_mode is ExperienceObservationTargetMode.VERIFIED_ENTITY:
        allowed_refs = set(activity.anchor_ids + activity.poi_binding_ids)
        if not set(target.entity_refs).issubset(allowed_refs):
            issues.append(
                f"experience activity {activity.activity_id} observation identity "
                "is not bound to the Activity"
            )
    elif (
        target.target_mode
        is ExperienceObservationTargetMode.VISITOR_SELECTED_VISIBLE_OBJECT
    ):
        if (
            activity.requires_guardian
            and ExperienceObservationSafetyConstraint.GUARDIAN_SUPERVISION
            not in target.safety_constraints
        ):
            issues.append(
                f"experience activity {activity.activity_id} visitor-selected "
                "observation requires guardian supervision"
            )
    elif (
        target.target_mode
        is ExperienceObservationTargetMode.SPECIFIC_CURRENT_OBSERVABLE
    ):
        if not set(target.supporting_claim_ids).issubset(bound_claim_ids):
            issues.append(
                f"experience activity {activity.activity_id} current observation "
                "references Claim outside Activity"
            )
        for claim_id in target.supporting_claim_ids:
            if claim_id not in current_presence_claim_ids:
                issues.append(
                    f"experience activity {activity.activity_id} current observation "
                    f"Claim {claim_id} lacks verified current-presence Evidence"
                )
    if experience.enabled:
        if activity.risk_level is not ExperienceRiskLevel.LOW:
            issues.append(
                f"production activity {activity.activity_id} must have low risk"
            )
        if activity.requires_purchase:
            issues.append(
                f"production activity {activity.activity_id} cannot require purchase"
            )
        child_audiences = {
            ExperienceAudience.FAMILY,
            ExperienceAudience.CHILD,
            ExperienceAudience.STUDENT,
        }
        if child_audiences.intersection(experience.target_audiences) and not (
            activity.requires_guardian
        ):
            issues.append(
                f"child activity {activity.activity_id} requires guardian"
            )
    unsafe = _unsafe_experience_intent(activity.instruction_intent)
    if unsafe:
        issues.append(
            f"experience activity {activity.activity_id} contains unsafe instruction "
            f"{unsafe}"
        )
    if _OBSERVABLE_REALITY_PATTERN.search(activity.instruction_intent):
        issues.append(
            f"experience activity {activity.activity_id} converts narrative into "
            "current observable reality"
        )


_UNSAFE_EXPERIENCE_MARKERS = (
    "攀爬",
    "翻越",
    "跨过护栏",
    "进入水域",
    "离开官方步道",
    "离开步道",
    "靠近危险水边",
    "穿越道路",
    "接触野生动物",
    "投喂野生动物",
    "采摘",
    "折树枝",
    "采集自然标本",
    "带走石块",
    "触摸文物",
    "攀爬文物",
    "刻字",
    "涂写",
    "移动景区设施",
    "进入限制区域",
    "自己去寻找",
    "分头行动",
    "奔跑竞赛",
    "危险自拍",
    "购买商品才能完成",
)
_SAFETY_NEGATIONS = ("不", "不得", "不要", "禁止", "无需", "无须", "避免")
_OBSERVABLE_REALITY_PATTERN = re.compile(
    r"(?:寻找|找到|看看|观察|拍摄).{0,12}(?:柘木|精卫.{0,6}石头|女娃.{0,6}溺水|炎帝.{0,6}居住)"
)


def _unsafe_experience_intent(text: str) -> str | None:
    clauses = re.split(r"[。！？；，]", text)
    for clause in clauses:
        for marker in _UNSAFE_EXPERIENCE_MARKERS:
            index = clause.find(marker)
            if index < 0:
                continue
            prefix = clause[:index]
            if any(negation in prefix for negation in _SAFETY_NEGATIONS):
                continue
            return marker
    return None


def _check_region_cycles(regions: list[Region], issues: list[str]) -> None:
    parents = {item.id: item.parent_id for item in regions}
    for region in regions:
        seen: set[str] = set()
        current: str | None = region.id
        while current is not None and current in parents:
            if current in seen:
                issues.append(f"region parent cycle includes {current}")
                break
            seen.add(current)
            current = parents[current]


def is_same_or_descendant(
    region_id: str,
    ancestor_id: str,
    parents: dict[str, str | None],
) -> bool:
    current: str | None = region_id
    visited: set[str] = set()
    while current is not None and current not in visited:
        if current == ancestor_id:
            return True
        visited.add(current)
        current = parents.get(current)
    return False


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def calculate_evidence_coverage(
    claims: list[KnowledgeClaim],
    evidence: list[KnowledgeEvidence],
    *,
    verified_source_ids: set[str],
) -> float:
    verified_claim_ids = {
        claim.claim_id
        for claim in claims
        if claim.verification_status is KnowledgeVerificationStatus.VERIFIED
    }
    if not verified_claim_ids:
        return 1.0
    covered_claim_ids = {
        item.claim_id
        for item in evidence
        if item.claim_id in verified_claim_ids
        and item.source_id in verified_source_ids
        and item.verification_status is KnowledgeVerificationStatus.VERIFIED
        and item.evidence_relation is EvidenceRelation.SUPPORTS
    }
    return len(covered_claim_ids) / len(verified_claim_ids)
