"""Contracts for evidence-safe Experience generation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import StrictBool, Field, computed_field, field_validator, model_validator

from app.catalog.models import (
    CatalogModel,
    ExperienceActivity,
    ExperienceAudience,
    ExperienceBlueprint,
    ExperienceObservationTarget,
    ExperienceProhibitedAction,
    PromotionPolicyStatus,
    StableId,
    StoryChapter,
    VisitorOutputType,
)
from app.catalog.retrieval import KnowledgeHit
from app.knowledge.models import CatalogVersionSnapshot, KnowledgeCitation
from app.story.models import GeneratedStoryChapter
from app.story.models import StoryPoiIdentity, StoryTriggerHint


class ExperienceTone(StrEnum):
    WARM = "warm"
    PLAYFUL = "playful"
    EDUCATIONAL = "educational"
    CONCISE = "concise"
    REFLECTIVE = "reflective"


class ExperienceGenerationStatus(StrEnum):
    GENERATED = "generated"


class ExperienceValidationStatus(StrEnum):
    PASSED = "passed"


class ExperiencePackageValidationStatus(StrEnum):
    PASSED = "passed"
    INCOMPLETE = "incomplete"


class ExperiencePlacementType(StrEnum):
    PLACED = "placed"
    CONTEXT_ONLY = "context_only"
    WEATHER_ADAPTED = "weather_adapted"
    SKIPPED = "skipped"
    UNPLACED = "unplaced"


class ExperienceSafetyPolicy(CatalogModel):
    prohibited_actions: tuple[ExperienceProhibitedAction, ...]
    guardian_required: bool
    purchase_required: bool = False
    normal_visitor_area_only: bool = True


class ExperienceGenerationRequest(CatalogModel):
    experience_id: StableId
    audience: ExperienceAudience | None = None
    language: str = Field(default="zh-CN", min_length=2, max_length=32)
    tone: ExperienceTone | None = None
    max_instruction_length: int = Field(default=500, ge=50, le=2000)
    weather_context: tuple[dict, ...] = ()


class ExperienceActivityContext(CatalogModel):
    blueprint: ExperienceBlueprint
    activity: ExperienceActivity
    story_chapters: tuple[StoryChapter, ...]
    generated_story_chapters: tuple[GeneratedStoryChapter, ...]
    claim_hits: tuple[KnowledgeHit, ...]
    package_version: CatalogVersionSnapshot
    safety_policy: ExperienceSafetyPolicy


class GroundedExperienceFact(CatalogModel):
    text: str = Field(min_length=1, max_length=2000)
    claim_id: StableId


class ExperienceGroundingMetrics(CatalogModel):
    used_claim_count: int = Field(ge=0)
    citation_count: int = Field(ge=0)
    qualified_claim_count: int = Field(ge=0)
    qualifier_satisfied_count: int = Field(ge=0)
    grounding_coverage: float = Field(ge=0, le=1)
    production_ineligible_leakage: int = Field(ge=0)
    citation_hallucination_count: int = Field(ge=0)
    qualifier_violation_count: int = Field(ge=0)
    context_fact_violation_count: int = Field(ge=0)
    unsafe_instruction_count: int = Field(ge=0)
    environmental_harm_count: int = Field(ge=0)
    cultural_property_harm_count: int = Field(ge=0)
    child_unsupervised_count: int = Field(ge=0)
    forced_purchase_count: int = Field(ge=0)
    current_observation_hallucination_count: int = Field(ge=0)
    restricted_area_instruction_count: int = Field(ge=0)
    water_hazard_count: int = Field(ge=0)
    road_hazard_count: int = Field(ge=0)
    wildlife_interaction_count: int = Field(ge=0)


class GeneratedExperienceActivity(CatalogModel):
    activity_id: StableId
    title: str = Field(min_length=1, max_length=200)
    instruction: str = Field(min_length=1, max_length=2000)
    factual_content: tuple[GroundedExperienceFact, ...]
    prompt: str = Field(min_length=1, max_length=2000)
    optional_hint: str | None = Field(default=None, min_length=1, max_length=1000)
    completion_message: str = Field(min_length=1, max_length=1000)
    observation_target: ExperienceObservationTarget
    used_claim_ids: tuple[StableId, ...]
    citations: tuple[KnowledgeCitation, ...]
    qualifiers_used: tuple[str, ...]
    safety_notice: str = Field(min_length=1, max_length=1500)
    estimated_duration_sec: int = Field(ge=1, le=3600)
    visitor_output_type: VisitorOutputType
    generation_status: ExperienceGenerationStatus
    warnings: tuple[str, ...]

    @model_validator(mode="before")
    @classmethod
    def discard_derived_fields(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            value.pop("visible_text", None)
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
    def visible_text(self) -> str:
        values = [self.instruction]
        values.extend(item.text for item in self.factual_content)
        values.append(self.prompt)
        if self.optional_hint:
            values.append(self.optional_hint)
        values.extend((self.completion_message, self.safety_notice))
        return "\n".join(values)

    @computed_field(return_type=ExperienceGroundingMetrics)
    @property
    def grounding_metrics(self) -> ExperienceGroundingMetrics:
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
                value and value in self.visible_text
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
        return ExperienceGroundingMetrics(
            used_claim_count=len(used),
            citation_count=len(self.citations),
            qualified_claim_count=len(qualified),
            qualifier_satisfied_count=len(satisfied),
            grounding_coverage=round(coverage, 6),
            production_ineligible_leakage=0,
            citation_hallucination_count=0,
            qualifier_violation_count=0,
            context_fact_violation_count=0,
            unsafe_instruction_count=0,
            environmental_harm_count=0,
            cultural_property_harm_count=0,
            child_unsupervised_count=0,
            forced_purchase_count=0,
            current_observation_hallucination_count=0,
            restricted_area_instruction_count=0,
            water_hazard_count=0,
            road_hazard_count=0,
            wildlife_interaction_count=0,
        )


class RenderedExperienceActivity(CatalogModel):
    raw_generation: GeneratedExperienceActivity
    activity_id: StableId
    title: str = Field(min_length=1, max_length=200)
    observation_text: str | None = Field(default=None, min_length=1, max_length=300)
    instruction: str = Field(min_length=1, max_length=2000)
    factual_content: tuple[GroundedExperienceFact, ...]
    prompt: str = Field(min_length=1, max_length=2000)
    optional_hint: str | None = Field(default=None, min_length=1, max_length=1000)
    completion_message: str = Field(min_length=1, max_length=1000)
    observation_target: ExperienceObservationTarget
    used_claim_ids: tuple[StableId, ...]
    citations: tuple[KnowledgeCitation, ...]
    qualifiers_used: tuple[str, ...]
    safety_notice: str = Field(min_length=1, max_length=3000)
    estimated_duration_sec: int = Field(ge=1, le=3600)
    visitor_output_type: VisitorOutputType
    generation_status: ExperienceGenerationStatus
    warnings: tuple[str, ...]

    @model_validator(mode="before")
    @classmethod
    def discard_derived_fields(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            value.pop("visible_text", None)
            value.pop("grounding_metrics", None)
        return value

    @computed_field(return_type=str)
    @property
    def visible_text(self) -> str:
        values = [self.observation_text, self.instruction]
        values.extend(item.text for item in self.factual_content)
        values.append(self.prompt)
        if self.optional_hint:
            values.append(self.optional_hint)
        values.extend((self.completion_message, self.safety_notice))
        return "\n".join(value for value in values if value)

    @computed_field(return_type=ExperienceGroundingMetrics)
    @property
    def grounding_metrics(self) -> ExperienceGroundingMetrics:
        return self.raw_generation.grounding_metrics


class ExperiencePackageDraft(CatalogModel):
    experience_id: StableId
    experience_version: str
    story_id: StableId
    story_version: str
    catalog_version: CatalogVersionSnapshot
    audience: ExperienceAudience
    activities: tuple[RenderedExperienceActivity, ...]
    used_claim_ids: tuple[StableId, ...]
    citations: tuple[KnowledgeCitation, ...]
    validation_status: ExperienceValidationStatus
    warnings: tuple[str, ...]


class ExperienceBindingRequest(CatalogModel):
    itinerary_id: str = Field(min_length=1, max_length=200)
    run_id: str | None = Field(default=None, min_length=1, max_length=200)
    route_id: StableId
    itinerary: dict
    weather: tuple[dict, ...] = ()


class ActivityBinding(CatalogModel):
    activity_id: StableId
    story_chapter_ids: tuple[StableId, ...]
    anchor_ids: tuple[StableId, ...]
    resolved_poi_ids: tuple[StoryPoiIdentity, ...]
    resolved_spatial_identity_ids: tuple[StableId, ...] = ()
    itinerary_stop_ids: tuple[str, ...]
    placement_type: ExperiencePlacementType
    trigger_hint: StoryTriggerHint
    recommended_duration_sec: int = Field(ge=1, le=3600)
    placement_reason: str = Field(min_length=1, max_length=500)
    safety_context: tuple[str, ...]
    spatial_degraded: StrictBool = False
    location_disclosure: str | None = Field(default=None, min_length=1, max_length=1000)


class ExperienceKnowledgeSnapshot(CatalogModel):
    catalog_version: CatalogVersionSnapshot
    used_claim_ids: tuple[StableId, ...]
    citations: tuple[KnowledgeCitation, ...]


class ExperienceSafetySummary(CatalogModel):
    unsafe_instruction_count: int = Field(default=0, ge=0)
    environmental_harm_count: int = Field(default=0, ge=0)
    cultural_property_harm_count: int = Field(default=0, ge=0)
    child_unsupervised_count: int = Field(default=0, ge=0)
    forced_purchase_count: int = Field(default=0, ge=0)
    current_observation_hallucination_count: int = Field(default=0, ge=0)
    restricted_area_instruction_count: int = Field(default=0, ge=0)
    water_hazard_count: int = Field(default=0, ge=0)
    road_hazard_count: int = Field(default=0, ge=0)
    wildlife_interaction_count: int = Field(default=0, ge=0)


class ExperienceBindingMetrics(CatalogModel):
    name_only_binding_count: int = Field(default=0, ge=0)
    dynamic_poi_forced_experience_count: int = Field(default=0, ge=0)
    unsafe_weather_placement_count: int = Field(default=0, ge=0)
    itinerary_mutation_count: int = Field(default=0, ge=0)
    story_mutation_count: int = Field(default=0, ge=0)
    knowledge_mutation_count: int = Field(default=0, ge=0)


class ExperiencePackage(CatalogModel):
    package_id: StableId
    experience_id: StableId
    experience_version: str
    story_package_id: StableId
    story_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    story_id: StableId
    story_version: str
    catalog_version: CatalogVersionSnapshot
    run_id: str | None
    itinerary_id: str
    audience: ExperienceAudience
    activities: tuple[RenderedExperienceActivity, ...]
    activity_bindings: tuple[ActivityBinding, ...]
    unplaced_activities: tuple[StableId, ...]
    warnings: tuple[str, ...]
    safety_summary: ExperienceSafetySummary
    knowledge_snapshot: ExperienceKnowledgeSnapshot
    validation_status: ExperiencePackageValidationStatus
    media_slots: tuple[StableId, ...]
    completion_tracking_slots: tuple[StableId, ...]
    binding_metrics: ExperienceBindingMetrics
