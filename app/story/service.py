"""Standalone evidence-grounded Story generation service."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from app.catalog.models import (
    EvidenceRelation,
    KnowledgeVerificationStatus,
    PromotionPolicyStatus,
    StoryAudience,
)
from app.catalog.repository import CatalogRepository
from app.catalog.retrieval import (
    KnowledgeContext,
    KnowledgeEvidenceSnapshot,
    KnowledgeHit,
    KnowledgeQuery,
    KnowledgeSourceSnapshot,
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
from app.story.models import (
    GeneratedStory,
    GeneratedStoryChapter,
    StoryChapterContext,
    StoryGenerationRequest,
    StoryGenerationStatus,
    StoryValidationStatus,
)
from app.story.prompts import grounded_story_messages


class StoryGenerationError(RuntimeError):
    pass


class StoryValidationError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(dict.fromkeys(issues))
        super().__init__(", ".join(self.issues))


class StoryGenerationService:
    def __init__(
        self,
        repository: CatalogRepository,
        *,
        llm: Any | None = None,
    ) -> None:
        self._repository = repository
        self._llm = llm

    def generate(self, request: StoryGenerationRequest) -> GeneratedStory:
        blueprint = self._repository.get_story(request.story_id)
        if blueprint is None or not blueprint.enabled:
            raise StoryGenerationError(f"enabled Story not found: {request.story_id}")
        chapters = self._repository.list_story_chapters(blueprint.story_id)
        if tuple(blueprint.chapter_ids) != tuple(item.chapter_id for item in chapters):
            raise StoryGenerationError("Story chapter order does not match Blueprint")
        audience = request.audience or blueprint.target_audiences[0]
        if audience not in blueprint.target_audiences:
            raise StoryGenerationError("requested audience is not supported by Story")

        client = self._llm or build_structured_llm(
            GeneratedStoryChapter, temperature=0
        )
        generated = tuple(
            self._generate_chapter(request, chapter.chapter_id, client)
            for chapter in chapters
        )
        used_claim_ids = tuple(
            dict.fromkeys(
                claim_id
                for chapter in generated
                for claim_id in chapter.used_claim_ids
            )
        )
        citations = tuple(
            dict.fromkeys(
                (
                    citation.claim_id,
                    citation.evidence_id,
                    citation.source_id,
                )
                for chapter in generated
                for citation in chapter.citations
            )
        )
        citation_by_identity = {
            (citation.claim_id, citation.evidence_id, citation.source_id): citation
            for chapter in generated
            for citation in chapter.citations
        }
        package = self._repository.get_package(blueprint.package_id)
        package_version = CatalogVersionSnapshot(
            package_id=package.manifest.package_id,
            schema_version=package.manifest.schema_version,
            content_version=package.manifest.content_version,
        )
        return GeneratedStory(
            story_id=blueprint.story_id,
            title=blueprint.title,
            story_version=blueprint.version,
            package_version=package_version,
            audience=audience,
            chapters=generated,
            used_claim_ids=used_claim_ids,
            citations=tuple(citation_by_identity[item] for item in citations),
            validation_status=StoryValidationStatus.PASSED,
            warnings=tuple(
                dict.fromkeys(
                    warning for chapter in generated for warning in chapter.warnings
                )
            ),
        )

    def build_chapter_context(self, chapter_id: str) -> StoryChapterContext:
        chapter = self._repository.get_story_chapter(chapter_id)
        if chapter is None:
            raise StoryGenerationError(f"Story Chapter not found: {chapter_id}")
        blueprint = self._repository.get_story(chapter.story_id)
        if blueprint is None:
            raise StoryGenerationError(f"Story not found: {chapter.story_id}")
        package = self._repository.get_package(blueprint.package_id)
        if package is None or not package.manifest.enabled:
            raise StoryGenerationError(
                f"enabled Catalog package not found: {blueprint.package_id}"
            )
        required = set(chapter.required_claim_ids)
        claim_ids = tuple(chapter.required_claim_ids + chapter.optional_claim_ids)
        hits = tuple(
            self._hydrate_claim(
                claim_id,
                "story_required_claim" if claim_id in required else "story_optional_claim",
            )
            for claim_id in claim_ids
        )
        return StoryChapterContext(
            blueprint=blueprint,
            chapter=chapter,
            claim_hits=hits,
            package_version=CatalogVersionSnapshot(
                package_id=package.manifest.package_id,
                schema_version=package.manifest.schema_version,
                content_version=package.manifest.content_version,
            ),
        )

    def _generate_chapter(
        self,
        request: StoryGenerationRequest,
        chapter_id: str,
        client: Any,
    ) -> GeneratedStoryChapter:
        context = self.build_chapter_context(chapter_id)
        messages = grounded_story_messages(request, context)
        last_issues: tuple[str, ...] = ()
        for attempt in range(2):
            try:
                raw = client.invoke(messages)
            except Exception as exc:
                raise StoryGenerationError(
                    f"structured_provider_failed: {type(exc).__name__}"
                ) from exc
            try:
                if raw is None:
                    raise StoryValidationError(["structured_output_none"])
                chapter = (
                    raw
                    if isinstance(raw, GeneratedStoryChapter)
                    else GeneratedStoryChapter.model_validate(raw)
                )
                validate_generated_chapter(
                    chapter,
                    context,
                    self._repository,
                    max_chapter_length=request.max_chapter_length,
                )
                return chapter
            except (StoryValidationError, KnowledgeAnswerValidationError, ValidationError) as exc:
                last_issues = getattr(exc, "issues", (type(exc).__name__,))
                if attempt == 0:
                    messages = [
                        *messages,
                        HumanMessage(
                            content=(
                                "上一份结构化章节未通过确定性校验："
                                + ", ".join(last_issues)
                                + "。只能使用原始 StoryChapterContext 修正，"
                                "不得新增事实、Claim、Evidence 或 Source。"
                            ),
                            name="story_grounding_repair",
                        ),
                    ]
        raise StoryGenerationError("validation_failed: " + ", ".join(last_issues))

    def _hydrate_claim(self, claim_id: str, reason: str) -> KnowledgeHit:
        claim = self._repository.get_claim(claim_id)
        if claim is None or not self._repository.is_claim_production_eligible(claim_id):
            raise StoryGenerationError(f"Claim is not production eligible: {claim_id}")
        evidence = tuple(
            item
            for item in self._repository.list_evidence_for_claim(claim_id)
            if item.verification_status is KnowledgeVerificationStatus.VERIFIED
            and item.evidence_relation is EvidenceRelation.SUPPORTS
            and (source := self._repository.get_source(item.source_id)) is not None
            and source.verification_status is KnowledgeVerificationStatus.VERIFIED
        )
        sources = {
            item.source_id: self._repository.get_source(item.source_id)
            for item in evidence
        }
        return KnowledgeHit(
            claim_id=claim.claim_id,
            claim_type=claim.claim_type,
            statement=claim.statement,
            normalized_statement=claim.normalized_statement,
            verification_status=claim.verification_status,
            promotion_policy=claim.promotion_policy,
            required_qualifier=claim.promotion_policy.required_qualifier,
            approved_wording=claim.promotion_policy.approved_wording,
            region_ids=tuple(claim.region_ids),
            theme_ids=tuple(claim.theme_ids),
            anchor_ids=tuple(claim.anchor_ids),
            evidence=tuple(
                KnowledgeEvidenceSnapshot(
                    evidence_id=item.evidence_id,
                    source_id=item.source_id,
                    evidence_relation=item.evidence_relation,
                    locator=item.locator,
                    quote_excerpt=item.quote_excerpt,
                )
                for item in evidence
            ),
            sources=tuple(
                KnowledgeSourceSnapshot(
                    source_id=source.source_id,
                    title=source.title,
                    source_type=source.source_type,
                    authority_level=source.authority_level,
                    publisher_or_author=source.publisher_or_author,
                    publication_date=source.publication_date,
                    url=source.url,
                    document_reference=source.document_reference,
                )
                for source in sources.values()
            ),
            score=0,
            match_reasons=(reason,),
        )


def validate_generated_chapter(
    generated: GeneratedStoryChapter,
    context: StoryChapterContext,
    repository: CatalogRepository,
    *,
    max_chapter_length: int | None = None,
) -> None:
    issues: list[str] = []
    chapter = context.chapter
    hits = {hit.claim_id: hit for hit in context.claim_hits}
    if generated.chapter_id != chapter.chapter_id:
        issues.append("chapter_id_mismatch")
    if generated.title != chapter.title:
        issues.append("chapter_title_mismatch")
    if generated.opening_text != chapter.opening_hook:
        issues.append("opening_text_not_curated")
    if generated.transition_text != chapter.transition_goal:
        issues.append("transition_text_not_curated")
    if generated.closing_text != chapter.visitor_takeaway:
        issues.append("closing_text_not_curated")
    if generated.visitor_takeaway != chapter.visitor_takeaway:
        issues.append("visitor_takeaway_not_curated")
    if generated.generation_status is not StoryGenerationStatus.GENERATED:
        issues.append("generation_status_not_generated")
    if generated.warnings:
        issues.append("story_warning_not_allowed")
    if max_chapter_length is not None and len(generated.narration) > max_chapter_length:
        issues.append("max_chapter_length_exceeded")

    used = set(generated.used_claim_ids)
    required = set(chapter.required_claim_ids)
    available = set(hits)
    if not required.issubset(used):
        issues.append("required_claim_missing")
    if not used.issubset(available):
        issues.append("claim_not_in_chapter_context")
    fact_claim_ids = [item.claim_id for item in generated.factual_content]
    if len(fact_claim_ids) != len(set(fact_claim_ids)):
        issues.append("duplicate_fact_claim")
    if set(fact_claim_ids) != used:
        issues.append("factual_content_claim_mismatch")
    for fact in generated.factual_content:
        hit = hits.get(fact.claim_id)
        if hit is None:
            continue
        approved = hit.approved_wording or hit.statement
        if fact.text != approved:
            issues.append("context_fact_violation")

    knowledge_context = KnowledgeContext(
        query=KnowledgeQuery(query_text=chapter.narrative_goal, limit=len(hits) or 1),
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
        answer=generated.narration,
        answer_status=AnswerStatus.ANSWERED,
        used_claim_ids=generated.used_claim_ids,
        citations=generated.citations,
        qualifiers_used=generated.qualifiers_used,
        warnings=(),
        catalog_version=context.package_version,
    )
    answerability = AnswerabilityDecision(
        level=AnswerabilityLevel.DIRECT_SUPPORT,
        direct_claim_ids=tuple(required),
        available_claim_ids=tuple(hits),
        reasons=("story_chapter_binding",),
    )
    try:
        validate_grounded_answer(
            grounded,
            knowledge_context,
            repository,
            answerability,
        )
    except KnowledgeAnswerValidationError as exc:
        issues.extend(exc.issues)
    if issues:
        raise StoryValidationError(issues)
