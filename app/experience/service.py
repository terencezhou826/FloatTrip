"""Standalone evidence-safe Experience generation service."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from app.catalog.models import (
    ExperienceContentMode,
    ExperienceProhibitedAction,
)
from app.catalog.repository import CatalogRepository
from app.catalog.retrieval import KnowledgeContext, KnowledgeQuery
from app.experience.models import (
    ExperienceActivityContext,
    ExperienceGenerationRequest,
    ExperienceGenerationStatus,
    ExperiencePackageDraft,
    ExperienceSafetyPolicy,
    ExperienceValidationStatus,
    GeneratedExperienceActivity,
    RenderedExperienceActivity,
)
from app.experience.prompts import evidence_safe_experience_messages
from app.experience.rendering import render_experience_activity
from app.experience.safety import (
    observable_reality_issues,
    rendered_observable_reality_issues,
    safety_issues,
)
from app.knowledge.models import (
    AnswerStatus,
    AnswerabilityDecision,
    AnswerabilityLevel,
    CatalogVersionSnapshot,
    GroundedKnowledgeAnswer,
)
from app.knowledge.service import (
    KnowledgeAnswerValidationError,
    validate_grounded_answer,
)
from app.llm.factory import build_structured_llm
from app.story.models import GeneratedStory, StoryPackage
from app.story.service import StoryGenerationService


class ExperienceGenerationError(RuntimeError):
    pass


class ExperienceValidationError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(dict.fromkeys(issues))
        super().__init__(", ".join(self.issues))


class ExperienceGenerationService:
    def __init__(
        self,
        repository: CatalogRepository,
        story: GeneratedStory | StoryPackage,
        *,
        llm: Any | None = None,
    ) -> None:
        self._repository = repository
        self._story = story
        self._llm = llm

    def generate(
        self, request: ExperienceGenerationRequest
    ) -> ExperiencePackageDraft:
        blueprint = self._repository.get_experience(request.experience_id)
        if blueprint is None or not blueprint.enabled:
            raise ExperienceGenerationError(
                f"enabled Experience not found: {request.experience_id}"
            )
        if blueprint.story_id != self._story.story_id:
            raise ExperienceGenerationError(
                "generated Story does not match Experience Blueprint"
            )
        activities = self._repository.list_activities(blueprint.experience_id)
        if tuple(blueprint.activity_ids) != tuple(
            item.activity_id for item in activities
        ):
            raise ExperienceGenerationError(
                "Experience activity order does not match Blueprint"
            )
        audience = request.audience or blueprint.target_audiences[0]
        if audience not in blueprint.target_audiences:
            raise ExperienceGenerationError(
                "requested audience is not supported by Experience"
            )
        client = self._llm or build_structured_llm(
            GeneratedExperienceActivity, temperature=0
        )
        raw_generated = tuple(
            self._generate_activity(request, activity.activity_id, client)
            for activity in activities
        )
        generated = tuple(
            self._render_activity(raw, activity.activity_id, request)
            for raw, activity in zip(raw_generated, activities, strict=True)
        )
        used_claim_ids = tuple(
            dict.fromkeys(
                claim_id
                for activity in generated
                for claim_id in activity.used_claim_ids
            )
        )
        citation_identities = tuple(
            dict.fromkeys(
                (citation.claim_id, citation.evidence_id, citation.source_id)
                for activity in generated
                for citation in activity.citations
            )
        )
        citation_map = {
            (citation.claim_id, citation.evidence_id, citation.source_id): citation
            for activity in generated
            for citation in activity.citations
        }
        package = self._repository.get_package(blueprint.package_id)
        return ExperiencePackageDraft(
            experience_id=blueprint.experience_id,
            experience_version=blueprint.version,
            story_id=self._story.story_id,
            story_version=self._story.story_version,
            catalog_version=CatalogVersionSnapshot(
                package_id=package.manifest.package_id,
                schema_version=package.manifest.schema_version,
                content_version=package.manifest.content_version,
            ),
            audience=audience,
            activities=generated,
            used_claim_ids=used_claim_ids,
            citations=tuple(citation_map[item] for item in citation_identities),
            validation_status=ExperienceValidationStatus.PASSED,
            warnings=tuple(
                dict.fromkeys(
                    warning
                    for activity in generated
                    for warning in activity.warnings
                )
            ),
        )

    def _render_activity(
        self,
        generated: GeneratedExperienceActivity,
        activity_id: str,
        request: ExperienceGenerationRequest,
    ) -> RenderedExperienceActivity:
        context = self.build_activity_context(activity_id)
        rendered = render_experience_activity(generated, context.activity)
        validate_rendered_activity(
            rendered,
            context,
            self._repository,
            max_instruction_length=request.max_instruction_length,
        )
        return rendered

    def build_activity_context(
        self, activity_id: str
    ) -> ExperienceActivityContext:
        activity = self._repository.get_activity(activity_id)
        if activity is None:
            raise ExperienceGenerationError(
                f"Experience Activity not found: {activity_id}"
            )
        blueprint = self._repository.get_experience(activity.experience_id)
        if blueprint is None or not blueprint.enabled:
            raise ExperienceGenerationError(
                f"enabled Experience not found: {activity.experience_id}"
            )
        if blueprint.story_id != self._story.story_id:
            raise ExperienceGenerationError(
                "generated Story does not match Experience Blueprint"
            )
        generated_by_id = {
            chapter.chapter_id: chapter for chapter in self._story.chapters
        }
        story_chapters = tuple(
            self._required_story_chapter(chapter_id)
            for chapter_id in activity.story_chapter_ids
        )
        generated_story_chapters = tuple(
            generated_by_id[chapter.chapter_id]
            for chapter in story_chapters
            if chapter.chapter_id in generated_by_id
        )
        if len(generated_story_chapters) != len(story_chapters):
            raise ExperienceGenerationError(
                "generated Story is missing an Experience-bound Chapter"
            )

        selected_claim_ids = tuple(
            activity.required_claim_ids + activity.optional_claim_ids
        )
        hits_by_id = {}
        story_service = StoryGenerationService(self._repository)
        for chapter in story_chapters:
            context = story_service.build_chapter_context(chapter.chapter_id)
            for hit in context.claim_hits:
                if hit.claim_id in selected_claim_ids:
                    hits_by_id[hit.claim_id] = hit
        missing = set(selected_claim_ids).difference(hits_by_id)
        if missing:
            raise ExperienceGenerationError(
                "Experience Claims are not available from bound Story Chapters: "
                + ", ".join(sorted(missing))
            )
        package = self._repository.get_package(blueprint.package_id)
        return ExperienceActivityContext(
            blueprint=blueprint,
            activity=activity,
            story_chapters=story_chapters,
            generated_story_chapters=generated_story_chapters,
            claim_hits=tuple(hits_by_id[item] for item in selected_claim_ids),
            package_version=CatalogVersionSnapshot(
                package_id=package.manifest.package_id,
                schema_version=package.manifest.schema_version,
                content_version=package.manifest.content_version,
            ),
            safety_policy=ExperienceSafetyPolicy(
                prohibited_actions=tuple(ExperienceProhibitedAction),
                guardian_required=activity.requires_guardian,
                purchase_required=activity.requires_purchase,
            ),
        )

    def _required_story_chapter(self, chapter_id: str):
        chapter = self._repository.get_story_chapter(chapter_id)
        if chapter is None:
            raise ExperienceGenerationError(
                f"Story Chapter not found: {chapter_id}"
            )
        return chapter

    def _generate_activity(
        self,
        request: ExperienceGenerationRequest,
        activity_id: str,
        client: Any,
    ) -> GeneratedExperienceActivity:
        context = self.build_activity_context(activity_id)
        messages = evidence_safe_experience_messages(request, context)
        last_issues: tuple[str, ...] = ()
        for attempt in range(2):
            try:
                raw = client.invoke(messages)
            except Exception as exc:
                raise ExperienceGenerationError(
                    f"structured_provider_failed: {type(exc).__name__}"
                ) from exc
            try:
                if raw is None:
                    raise ExperienceValidationError(["structured_output_none"])
                generated = (
                    raw
                    if isinstance(raw, GeneratedExperienceActivity)
                    else GeneratedExperienceActivity.model_validate(raw)
                )
                validate_generated_activity(
                    generated,
                    context,
                    self._repository,
                    max_instruction_length=request.max_instruction_length,
                )
                return generated
            except (
                ExperienceValidationError,
                KnowledgeAnswerValidationError,
                ValidationError,
            ) as exc:
                last_issues = getattr(exc, "issues", (type(exc).__name__,))
                if attempt == 0:
                    messages = [
                        *messages,
                        HumanMessage(
                            content=(
                                "上一份结构化 Activity 未通过确定性校验："
                                + ", ".join(last_issues)
                                + "。只能使用原始 ExperienceActivityContext 修正一次；"
                                "不得新增事实、现场对象、危险行为、Claim、Evidence 或 Source。"
                            ),
                            name="experience_safety_repair",
                        ),
                    ]
        raise ExperienceGenerationError(
            "validation_failed: " + ", ".join(last_issues)
        )


_FACILITATION_FACT_PATTERN = re.compile(
    r"(?:\d{4}年|经纬度|坐标|考古证明|文保等级|景区历史|据《|记载)"
)


def validate_generated_activity(
    generated: GeneratedExperienceActivity,
    context: ExperienceActivityContext,
    repository: CatalogRepository,
    *,
    max_instruction_length: int | None = None,
) -> None:
    issues: list[str] = []
    activity = context.activity
    hits = {hit.claim_id: hit for hit in context.claim_hits}
    if generated.activity_id != activity.activity_id:
        issues.append("activity_id_mismatch")
    if generated.title != activity.title:
        issues.append("activity_title_mismatch")
    if generated.estimated_duration_sec != activity.estimated_duration_sec:
        issues.append("activity_duration_mismatch")
    if generated.visitor_output_type is not activity.visitor_output_type:
        issues.append("visitor_output_type_mismatch")
    if (
        generated.generation_status
        is not ExperienceGenerationStatus.GENERATED
    ):
        issues.append("generation_status_not_generated")
    if generated.warnings:
        issues.append("experience_warning_not_allowed")
    if (
        max_instruction_length is not None
        and len(generated.instruction) > max_instruction_length
    ):
        issues.append("max_instruction_length_exceeded")
    used = set(generated.used_claim_ids)
    required = set(activity.required_claim_ids)
    available = set(hits)
    if not required.issubset(used):
        issues.append("required_claim_missing")
    if not used.issubset(available):
        issues.append("claim_not_in_activity_context")
    fact_claim_ids = [item.claim_id for item in generated.factual_content]
    if len(fact_claim_ids) != len(set(fact_claim_ids)):
        issues.append("duplicate_fact_claim")
    if set(fact_claim_ids) != used:
        issues.append("factual_content_claim_mismatch")
    for fact in generated.factual_content:
        hit = hits.get(fact.claim_id)
        if hit is None:
            continue
        if fact.text != (hit.approved_wording or hit.statement):
            issues.append("context_fact_violation")

    facilitation_text = "\n".join(
        value
        for value in (
            generated.instruction,
            generated.prompt,
            generated.optional_hint,
            generated.completion_message,
            generated.safety_notice,
        )
        if value
    )
    if activity.content_mode is ExperienceContentMode.FACILITATION_ONLY:
        if used or generated.factual_content or generated.citations:
            issues.append("facilitation_only_contains_knowledge")
        if generated.qualifiers_used:
            issues.append("facilitation_only_contains_qualifier")
        if _FACILITATION_FACT_PATTERN.search(facilitation_text):
            issues.append("facilitation_only_contains_fact_marker")
    else:
        knowledge_context = KnowledgeContext(
            query=KnowledgeQuery(
                query_text=activity.experience_goal,
                limit=len(hits) or 1,
            ),
            hits=tuple(context.claim_hits),
            claim_count=len(hits),
            source_count=len(
                {source.source_id for hit in hits.values() for source in hit.sources}
            ),
            package_id=context.package_version.package_id,
            schema_version=context.package_version.schema_version,
            content_version=context.package_version.content_version,
            warnings=(),
        )
        grounded = GroundedKnowledgeAnswer(
            answer=generated.visible_text,
            answer_status=AnswerStatus.ANSWERED,
            used_claim_ids=generated.used_claim_ids,
            citations=generated.citations,
            qualifiers_used=generated.qualifiers_used,
            warnings=(),
            catalog_version=context.package_version,
        )
        try:
            validate_grounded_answer(
                grounded,
                knowledge_context,
                repository,
                AnswerabilityDecision(
                    level=AnswerabilityLevel.DIRECT_SUPPORT,
                    direct_claim_ids=tuple(required),
                    available_claim_ids=tuple(hits),
                    reasons=("experience_activity_binding",),
                ),
            )
        except KnowledgeAnswerValidationError as exc:
            issues.extend(exc.issues)
        for hit in hits.values():
            approved = hit.approved_wording or hit.statement
            if approved in facilitation_text:
                issues.append("fact_outside_factual_content")

    issues.extend(safety_issues(generated.visible_text))
    issues.extend(
        observable_reality_issues(generated, activity, repository)
    )
    if issues:
        raise ExperienceValidationError(issues)


def validate_rendered_activity(
    rendered: RenderedExperienceActivity,
    context: ExperienceActivityContext,
    repository: CatalogRepository,
    *,
    max_instruction_length: int | None = None,
) -> None:
    validate_generated_activity(
        rendered.raw_generation,
        context,
        repository,
        max_instruction_length=max_instruction_length,
    )
    issues: list[str] = []
    expected = render_experience_activity(
        rendered.raw_generation,
        context.activity,
    )
    if rendered != expected:
        issues.append("rendered_activity_not_deterministic")
    issues.extend(
        rendered_observable_reality_issues(
            rendered,
            context.activity,
            repository,
        )
    )
    for constraint in context.activity.safety_constraints:
        if constraint not in rendered.safety_notice:
            issues.append("safety_constraint_missing")
    if context.activity.requires_guardian and not any(
        marker in rendered.safety_notice for marker in ("同行成年人", "监护")
    ):
        issues.append("guardian_notice_missing")
    issues.extend(safety_issues(rendered.visible_text))
    if issues:
        raise ExperienceValidationError(issues)
