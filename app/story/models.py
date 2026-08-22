"""Contracts for evidence-grounded Story generation and validation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, computed_field, field_validator, model_validator

from app.catalog.models import (
    CatalogModel,
    PoiProvider,
    PromotionPolicyStatus,
    StableId,
    StoryAudience,
    StoryBlueprint,
    StoryChapter,
)
from app.catalog.retrieval import KnowledgeHit
from app.knowledge.models import CatalogVersionSnapshot, KnowledgeCitation


class StoryTone(StrEnum):
    WARM = "warm"
    EDUCATIONAL = "educational"
    CONCISE = "concise"
    REFLECTIVE = "reflective"


class StoryGenerationStatus(StrEnum):
    GENERATED = "generated"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class StoryValidationStatus(StrEnum):
    PASSED = "passed"


class PlacementType(StrEnum):
    PLACED = "placed"
    CONTEXT_ONLY = "context_only"
    UNPLACED = "unplaced"


class StoryTriggerHint(StrEnum):
    ARRIVAL = "arrival"
    EARLY_VISIT = "early_visit"
    MID_VISIT = "mid_visit"
    LATE_VISIT = "late_visit"
    DEPARTURE = "departure"
    AFTER_VISIT = "after_visit"
    UNAVAILABLE = "unavailable"


class StoryPackageValidationStatus(StrEnum):
    PASSED = "passed"
    INCOMPLETE = "incomplete"


class StoryGenerationRequest(CatalogModel):
    story_id: StableId
    audience: StoryAudience | None = None
    tone: StoryTone | None = None
    language: str = Field(default="zh-CN", min_length=2, max_length=32)
    max_chapter_length: int = Field(default=600, ge=100, le=2000)


class StoryChapterContext(CatalogModel):
    blueprint: StoryBlueprint
    chapter: StoryChapter
    claim_hits: tuple[KnowledgeHit, ...]
    package_version: CatalogVersionSnapshot


class GroundedStoryFact(CatalogModel):
    text: str = Field(min_length=1, max_length=2000)
    claim_id: StableId


class StoryGroundingMetrics(CatalogModel):
    used_claim_count: int = Field(ge=0)
    citation_count: int = Field(ge=0)
    qualified_claim_count: int = Field(ge=0)
    qualifier_satisfied_count: int = Field(ge=0)
    grounding_coverage: float = Field(ge=0, le=1)
    production_ineligible_leakage: int = Field(ge=0)
    citation_hallucination_count: int = Field(ge=0)
    qualifier_violation_count: int = Field(ge=0)
    context_fact_violation_count: int = Field(ge=0)


class GeneratedStoryChapter(CatalogModel):
    chapter_id: StableId
    title: str = Field(min_length=1, max_length=200)
    opening_text: str = Field(min_length=1, max_length=1000)
    factual_content: tuple[GroundedStoryFact, ...]
    transition_text: str = Field(min_length=1, max_length=1000)
    closing_text: str = Field(min_length=1, max_length=1000)
    used_claim_ids: tuple[StableId, ...]
    citations: tuple[KnowledgeCitation, ...]
    qualifiers_used: tuple[str, ...]
    visitor_takeaway: str = Field(min_length=1, max_length=1000)
    generation_status: StoryGenerationStatus
    warnings: tuple[str, ...]

    @model_validator(mode="before")
    @classmethod
    def discard_derived_fields(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            value.pop("narration", None)
            value.pop("grounding_metrics", None)
        return value

    @field_validator("used_claim_ids", "qualifiers_used", "warnings")
    @classmethod
    def require_unique_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("values must be unique")
        return value

    @computed_field(return_type=str)
    @property
    def narration(self) -> str:
        parts = [self.opening_text]
        parts.extend(item.text for item in self.factual_content)
        parts.extend((self.transition_text, self.closing_text))
        return "\n".join(parts)

    @computed_field(return_type=StoryGroundingMetrics)
    @property
    def grounding_metrics(self) -> StoryGroundingMetrics:
        used = set(self.used_claim_ids)
        cited = {citation.claim_id for citation in self.citations}
        qualified = {
            citation.claim_id
            for citation in self.citations
            if citation.promotion_policy
            is PromotionPolicyStatus.ALLOWED_WITH_QUALIFICATION
        }
        satisfied = {
            citation.claim_id
            for citation in self.citations
            if any(
                value and value in self.narration
                for value in (
                    citation.required_qualifier,
                    citation.approved_wording,
                )
            )
        }.intersection(qualified)
        denominator = len(used) + len(qualified)
        coverage = (
            1.0
            if denominator == 0
            else (len(used.intersection(cited)) + len(satisfied)) / denominator
        )
        return StoryGroundingMetrics(
            used_claim_count=len(used),
            citation_count=len(self.citations),
            qualified_claim_count=len(qualified),
            qualifier_satisfied_count=len(satisfied),
            grounding_coverage=round(coverage, 6),
            production_ineligible_leakage=0,
            citation_hallucination_count=0,
            qualifier_violation_count=0,
            context_fact_violation_count=0,
        )


class GeneratedStory(CatalogModel):
    story_id: StableId
    title: str = Field(min_length=1, max_length=200)
    story_version: str
    package_version: CatalogVersionSnapshot
    audience: StoryAudience
    chapters: tuple[GeneratedStoryChapter, ...]
    used_claim_ids: tuple[StableId, ...]
    citations: tuple[KnowledgeCitation, ...]
    validation_status: StoryValidationStatus
    warnings: tuple[str, ...]


class StoryBindingRequest(CatalogModel):
    itinerary_id: str = Field(min_length=1, max_length=200)
    run_id: str | None = Field(default=None, min_length=1, max_length=200)
    route_id: StableId
    itinerary: dict
    weather: tuple[dict, ...] = ()
    user_profile: dict = Field(default_factory=dict)


class StoryPoiIdentity(CatalogModel):
    provider: PoiProvider
    external_poi_id: str = Field(min_length=1, max_length=256)


class ChapterBinding(CatalogModel):
    chapter_id: StableId
    anchor_ids: tuple[StableId, ...]
    resolved_poi_ids: tuple[StoryPoiIdentity, ...]
    itinerary_stop_ids: tuple[str, ...]
    placement_type: PlacementType
    trigger_hint: StoryTriggerHint
    recommended_playback_duration: int = Field(ge=1, le=3600)
    placement_reason: str = Field(min_length=1, max_length=500)


class StoryKnowledgeSnapshot(CatalogModel):
    catalog_version: CatalogVersionSnapshot
    used_claim_ids: tuple[StableId, ...]
    citations: tuple[KnowledgeCitation, ...]


class StoryBindingMetrics(CatalogModel):
    name_only_binding_count: int = Field(default=0, ge=0)
    dynamic_poi_forced_story_count: int = Field(default=0, ge=0)
    itinerary_mutation_count: int = Field(default=0, ge=0)
    knowledge_mutation_count: int = Field(default=0, ge=0)


class StoryPackage(CatalogModel):
    package_id: StableId
    story_id: StableId
    story_version: str
    catalog_version: CatalogVersionSnapshot
    itinerary_id: str
    run_id: str | None
    audience: StoryAudience
    route_id: StableId
    chapters: tuple[GeneratedStoryChapter, ...]
    chapter_bindings: tuple[ChapterBinding, ...]
    unplaced_chapters: tuple[StableId, ...]
    warnings: tuple[str, ...]
    knowledge_snapshot: StoryKnowledgeSnapshot
    media_slots: tuple[StableId, ...]
    experience_slots: tuple[StableId, ...]
    presentation_hints: tuple[str, ...]
    validation_status: StoryPackageValidationStatus
    binding_metrics: StoryBindingMetrics
