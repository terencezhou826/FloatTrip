"""Domain models for the curated content catalog."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


StableId = Annotated[
    str,
    Field(min_length=1, max_length=160, pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$"),
]


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ThemeType(StrEnum):
    MYTHOLOGY = "mythology"
    HISTORICAL_FIGURE = "historical_figure"
    ANCIENT_ARCHITECTURE = "ancient_architecture"
    RED_CULTURE = "red_culture"
    FOLK_CUSTOM = "folk_custom"
    FOOD = "food"
    NATURE = "nature"
    HERITAGE = "heritage"
    CUSTOM = "custom"


class RegionType(StrEnum):
    PROVINCE = "province"
    PREFECTURE_CITY = "prefecture_city"
    COUNTY = "county"
    DISTRICT = "district"
    COUNTY_LEVEL_CITY = "county_level_city"


class PoiProvider(StrEnum):
    AMAP = "amap"
    BAIDU = "baidu"
    TENCENT = "tencent"
    OTHER = "other"
    CUSTOM = "custom"


class PoiVerificationStatus(StrEnum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    REJECTED = "rejected"


class PoiVerificationMethod(StrEnum):
    MANUAL_REVIEW = "manual_review"
    PROVIDER_EXACT_ID = "provider_exact_id"
    OFFICIAL_SOURCE = "official_source"
    OTHER = "other"


class KnowledgeSourceType(StrEnum):
    ANCIENT_TEXT = "ancient_text"
    GOVERNMENT = "government"
    ACADEMIC = "academic"
    LOCAL_CHRONICLE = "local_chronicle"
    HERITAGE_RECORD = "heritage_record"
    SCENIC_OFFICIAL = "scenic_official"
    MUSEUM = "museum"
    NEWS = "news"
    TOURISM_OPERATION = "tourism_operation"
    OTHER = "other"


class AuthorityLevel(StrEnum):
    PRIMARY = "primary"
    AUTHORITATIVE = "authoritative"
    SCHOLARLY = "scholarly"
    SECONDARY = "secondary"
    REFERENCE_ONLY = "reference_only"


class KnowledgeClaimType(StrEnum):
    HISTORICAL_FACT = "historical_fact"
    MYTHOLOGY = "mythology"
    LOCAL_LEGEND = "local_legend"
    ACADEMIC_INTERPRETATION = "academic_interpretation"
    OFFICIAL_NARRATIVE = "official_narrative"
    TOURISM_OPERATION = "tourism_operation"
    GEOGRAPHIC_FACT = "geographic_fact"
    HERITAGE_FACT = "heritage_fact"


class KnowledgeVerificationStatus(StrEnum):
    DRAFT = "draft"
    REVIEW_REQUIRED = "review_required"
    VERIFIED = "verified"
    REJECTED = "rejected"
    DISPUTED = "disputed"


class StoryType(StrEnum):
    MYTHOLOGY = "mythology"
    HISTORICAL = "historical"
    HERITAGE = "heritage"
    BIOGRAPHICAL = "biographical"
    EDUCATIONAL = "educational"
    NATURE = "nature"
    FOLK_CULTURE = "folk_culture"
    FOOD_CULTURE = "food_culture"
    RED_CULTURE = "red_culture"
    CUSTOM = "custom"


class StoryAudience(StrEnum):
    GENERAL = "general"
    FAMILY = "family"
    STUDENT = "student"
    CULTURE = "culture"


class StoryChapterType(StrEnum):
    PROLOGUE = "prologue"
    CONTEXT = "context"
    ORIGIN = "origin"
    DEVELOPMENT = "development"
    TURNING_POINT = "turning_point"
    CLIMAX = "climax"
    REFLECTION = "reflection"
    EPILOGUE = "epilogue"


class StoryVerificationStatus(StrEnum):
    DRAFT = "draft"
    REVIEW_REQUIRED = "review_required"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ExperienceType(StrEnum):
    EDUCATIONAL = "educational"
    FAMILY = "family"
    CULTURAL = "cultural"
    NATURE = "nature"
    HERITAGE = "heritage"
    FOLK_CULTURE = "folk_culture"
    FOOD_CULTURE = "food_culture"
    CUSTOM = "custom"


class ExperienceAudience(StrEnum):
    GENERAL = "general"
    FAMILY = "family"
    CHILD = "child"
    STUDENT = "student"
    CULTURE = "culture"


class ExperienceActivityType(StrEnum):
    OBSERVATION = "observation"
    QUESTION = "question"
    REFLECTION = "reflection"
    CREATIVE = "creative"
    FAMILY_COLLABORATION = "family_collaboration"
    PHOTO_PROMPT = "photo_prompt"
    COMPARISON = "comparison"
    SEEK_AND_FIND = "seek_and_find"
    SENSORY = "sensory"
    MICRO_CHALLENGE = "micro_challenge"
    CONTEXT = "context"


class ExperienceContentMode(StrEnum):
    FACILITATION_ONLY = "facilitation_only"
    KNOWLEDGE_GROUNDED = "knowledge_grounded"


class ExperienceRiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    PROHIBITED = "prohibited"


class VisitorOutputType(StrEnum):
    NONE = "none"
    SPOKEN_RESPONSE = "spoken_response"
    TEXT_RESPONSE = "text_response"
    PHOTO = "photo"
    SELECTION = "selection"
    OBSERVATION = "observation"
    DRAWING = "drawing"


class ExperienceVerificationStatus(StrEnum):
    DRAFT = "draft"
    REVIEW_REQUIRED = "review_required"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ExperienceProhibitedAction(StrEnum):
    CLIMB_UNOFFICIAL_FACILITY = "climb_unofficial_facility"
    CROSS_BARRIER = "cross_barrier"
    LEAVE_OFFICIAL_PATH = "leave_official_path"
    ENTER_WATER = "enter_water"
    APPROACH_HAZARDOUS_WATER = "approach_hazardous_water"
    CROSS_ROAD = "cross_road"
    TOUCH_WILDLIFE = "touch_wildlife"
    FEED_WILDLIFE = "feed_wildlife"
    PICK_PLANTS = "pick_plants"
    COLLECT_NATURAL_SPECIMENS = "collect_natural_specimens"
    REMOVE_NATURAL_OBJECTS = "remove_natural_objects"
    TOUCH_OR_CLIMB_CULTURAL_PROPERTY = "touch_or_climb_cultural_property"
    WRITE_ON_CULTURAL_PROPERTY = "write_on_cultural_property"
    MOVE_SITE_FACILITIES = "move_site_facilities"
    ENTER_RESTRICTED_AREA = "enter_restricted_area"
    CHILD_UNSUPERVISED = "child_unsupervised"
    CHILD_OUT_OF_SIGHT = "child_out_of_sight"
    RUNNING_RACE = "running_race"
    DANGEROUS_SELFIE = "dangerous_selfie"
    REQUIRED_PURCHASE = "required_purchase"


class ExperienceObservationTargetMode(StrEnum):
    NONE = "none"
    VERIFIED_ENTITY = "verified_entity"
    VISITOR_SELECTED_VISIBLE_OBJECT = "visitor_selected_visible_object"
    SPECIFIC_CURRENT_OBSERVABLE = "specific_current_observable"


class ExperienceObservationInteractionMode(StrEnum):
    NONE = "none"
    OBSERVE_ONLY = "observe_only"


class ExperienceObservationSelectionRule(StrEnum):
    CURRENTLY_VISIBLE = "currently_visible"


class ExperienceObservationSafetyConstraint(StrEnum):
    NO_TOUCH = "no_touch"
    NO_MOVE = "no_move"
    NO_COLLECT = "no_collect"
    NO_REMOVE = "no_remove"
    NO_CROSS_BARRIER = "no_cross_barrier"
    NORMAL_VISITOR_AREA_ONLY = "normal_visitor_area_only"
    GUARDIAN_SUPERVISION = "guardian_supervision"
    SKIPPABLE = "skippable"


VISITOR_SELECTED_OBSERVATION_SAFETY = frozenset(
    {
        ExperienceObservationSafetyConstraint.NO_TOUCH,
        ExperienceObservationSafetyConstraint.NO_MOVE,
        ExperienceObservationSafetyConstraint.NO_COLLECT,
        ExperienceObservationSafetyConstraint.NO_REMOVE,
        ExperienceObservationSafetyConstraint.NO_CROSS_BARRIER,
        ExperienceObservationSafetyConstraint.NORMAL_VISITOR_AREA_ONLY,
        ExperienceObservationSafetyConstraint.SKIPPABLE,
    }
)


class ExperienceObservationTarget(CatalogModel):
    target_mode: ExperienceObservationTargetMode
    target_text: str | None = Field(default=None, min_length=1, max_length=300)
    entity_refs: tuple[StableId, ...] = ()
    supporting_claim_ids: tuple[StableId, ...] = ()
    interaction_mode: ExperienceObservationInteractionMode
    selection_rule: ExperienceObservationSelectionRule | None = None
    safety_constraints: tuple[ExperienceObservationSafetyConstraint, ...] = ()

    @model_validator(mode="after")
    def validate_mode_contract(self) -> "ExperienceObservationTarget":
        mode = self.target_mode
        if mode is ExperienceObservationTargetMode.NONE:
            if any(
                (
                    self.target_text,
                    self.entity_refs,
                    self.supporting_claim_ids,
                    self.selection_rule,
                    self.safety_constraints,
                )
            ) or self.interaction_mode is not ExperienceObservationInteractionMode.NONE:
                raise ValueError("no-external-target mode cannot carry a target")
            return self
        if not self.target_text:
            raise ValueError("observation target requires target_text")
        if self.interaction_mode is not ExperienceObservationInteractionMode.OBSERVE_ONLY:
            raise ValueError("external observation must be observe-only")
        if mode is ExperienceObservationTargetMode.VERIFIED_ENTITY:
            if not self.entity_refs:
                raise ValueError("verified entity requires a stable identity")
            if self.supporting_claim_ids or self.selection_rule is not None:
                raise ValueError("verified entity cannot use selection or presence Claims")
        elif mode is ExperienceObservationTargetMode.VISITOR_SELECTED_VISIBLE_OBJECT:
            if self.entity_refs or self.supporting_claim_ids:
                raise ValueError("visitor-selected target cannot assert an entity")
            if self.selection_rule is not ExperienceObservationSelectionRule.CURRENTLY_VISIBLE:
                raise ValueError("visitor-selected target must already be visible")
            if not VISITOR_SELECTED_OBSERVATION_SAFETY.issubset(
                self.safety_constraints
            ):
                raise ValueError("visitor-selected target lacks safety constraints")
        elif mode is ExperienceObservationTargetMode.SPECIFIC_CURRENT_OBSERVABLE:
            if not self.supporting_claim_ids:
                raise ValueError(
                    "specific current observable requires current-presence Evidence"
                )
            if self.entity_refs or self.selection_rule is not None:
                raise ValueError(
                    "specific current observable cannot use entity or selection refs"
                )
        return self


PRODUCTION_EXPERIENCE_PROHIBITED_ACTIONS = frozenset(
    ExperienceProhibitedAction
)


class EvidenceRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXTUALIZES = "contextualizes"
    MENTIONS = "mentions"


class PromotionPolicyStatus(StrEnum):
    ALLOWED = "allowed"
    ALLOWED_WITH_QUALIFICATION = "allowed_with_qualification"
    INTERNAL_ONLY = "internal_only"
    FORBIDDEN = "forbidden"


class Region(CatalogModel):
    id: StableId
    name: str = Field(min_length=1, max_length=100)
    parent_id: StableId | None = None
    region_type: RegionType
    admin_code: str | None = Field(default=None, min_length=1, max_length=32)


class CatalogTheme(CatalogModel):
    id: StableId
    type: ThemeType
    name: str = Field(min_length=1, max_length=100)
    region_id: StableId
    custom_type: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_custom_type(self) -> "CatalogTheme":
        if self.type is ThemeType.CUSTOM and self.custom_type is None:
            raise ValueError("custom themes require custom_type")
        if self.type is not ThemeType.CUSTOM and self.custom_type is not None:
            raise ValueError("custom_type is only valid for custom themes")
        return self


class Anchor(CatalogModel):
    id: StableId
    name: str = Field(min_length=1, max_length=100)
    region_id: StableId


class ExternalPoiBinding(CatalogModel):
    binding_id: StableId
    anchor_id: StableId
    provider: PoiProvider
    external_poi_id: str = Field(min_length=1, max_length=256)
    external_name: str = Field(min_length=1, max_length=256)
    verification_status: PoiVerificationStatus
    provider_region_code: str | None = Field(default=None, min_length=1, max_length=64)
    provider_address: str | None = Field(default=None, min_length=1, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    verification_method: PoiVerificationMethod | None = None
    verified_at: datetime | None = None
    verification_note: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_verification_provenance(self) -> "ExternalPoiBinding":
        if self.verification_status is PoiVerificationStatus.VERIFIED:
            missing = []
            if self.verification_method is None:
                missing.append("verification_method")
            if self.verified_at is None:
                missing.append("verified_at")
            if missing:
                raise ValueError(f"verified bindings require {', '.join(missing)}")
        return self

    @property
    def is_runtime_eligible(self) -> bool:
        return self.verification_status is PoiVerificationStatus.VERIFIED


class PromotionPolicy(CatalogModel):
    status: PromotionPolicyStatus
    approved_wording: str | None = Field(
        default=None, min_length=1, max_length=1000
    )
    required_qualifier: str | None = Field(
        default=None, min_length=1, max_length=200
    )
    forbidden_wordings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_qualification(self) -> "PromotionPolicy":
        if (
            self.status is PromotionPolicyStatus.ALLOWED_WITH_QUALIFICATION
            and self.approved_wording is None
            and self.required_qualifier is None
        ):
            raise ValueError(
                "allowed_with_qualification requires approved_wording or "
                "required_qualifier"
            )
        return self


class EvidenceLocator(CatalogModel):
    page: str | None = Field(default=None, min_length=1, max_length=100)
    chapter: str | None = Field(default=None, min_length=1, max_length=200)
    volume: str | None = Field(default=None, min_length=1, max_length=100)
    paragraph: str | None = Field(default=None, min_length=1, max_length=200)
    url_fragment: str | None = Field(default=None, min_length=1, max_length=200)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    other: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_locator(self) -> "EvidenceLocator":
        values = (
            self.page,
            self.chapter,
            self.volume,
            self.paragraph,
            self.url_fragment,
            self.line_start,
            self.line_end,
            self.other,
        )
        if all(value is None for value in values):
            raise ValueError("evidence locator requires at least one location field")
        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_start > self.line_end
        ):
            raise ValueError("line_start must not be after line_end")
        return self


class KnowledgeSource(CatalogModel):
    source_id: StableId
    title: str = Field(min_length=1, max_length=500)
    source_type: KnowledgeSourceType
    publisher_or_author: str = Field(min_length=1, max_length=300)
    publication_date: date | None = None
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    document_reference: str | None = Field(
        default=None, min_length=1, max_length=500
    )
    region_ids: list[StableId] = Field(default_factory=list)
    language: str = Field(min_length=2, max_length=32)
    authority_level: AuthorityLevel
    verification_status: KnowledgeVerificationStatus
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_reference(self) -> "KnowledgeSource":
        if self.url is None and self.document_reference is None:
            raise ValueError("knowledge source requires url or document_reference")
        return self


class KnowledgeClaim(CatalogModel):
    claim_id: StableId
    subject_ids: list[StableId] = Field(min_length=1)
    claim_type: KnowledgeClaimType
    statement: str = Field(min_length=1, max_length=2000)
    normalized_statement: str = Field(min_length=1, max_length=2000)
    region_ids: list[StableId] = Field(default_factory=list)
    theme_ids: list[StableId] = Field(default_factory=list)
    anchor_ids: list[StableId] = Field(default_factory=list)
    verification_status: KnowledgeVerificationStatus
    promotion_policy: PromotionPolicy
    valid_from: date | None = None
    valid_to: date | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_validity_period(self) -> "KnowledgeClaim":
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_from > self.valid_to
        ):
            raise ValueError("valid_from must not be after valid_to")
        return self


class KnowledgeEvidence(CatalogModel):
    evidence_id: StableId
    claim_id: StableId
    source_id: StableId
    locator: EvidenceLocator
    quote_excerpt: str = Field(min_length=1, max_length=1000)
    evidence_relation: EvidenceRelation
    verification_status: KnowledgeVerificationStatus
    metadata: dict[str, Any] = Field(default_factory=dict)


class CuratedRoute(CatalogModel):
    id: StableId
    name: str = Field(min_length=1, max_length=160)
    primary_region_id: StableId
    coverage_region_ids: list[StableId] = Field(min_length=1)
    theme_id: StableId
    anchor_ids: list[StableId] = Field(min_length=1)
    mandatory_anchor_ids: list[StableId] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_mandatory_anchors(self) -> "CuratedRoute":
        if not set(self.mandatory_anchor_ids).issubset(self.anchor_ids):
            raise ValueError("mandatory_anchor_ids must be included in anchor_ids")
        return self


class StoryBlueprint(CatalogModel):
    story_id: StableId
    title: str = Field(min_length=1, max_length=200)
    package_id: StableId
    region_id: StableId
    theme_id: StableId
    route_id: StableId
    story_type: StoryType
    target_audiences: list[StoryAudience] = Field(min_length=1)
    narrative_theme: str = Field(min_length=1, max_length=500)
    narrative_goal: str = Field(min_length=1, max_length=1000)
    chapter_ids: list[StableId] = Field(min_length=1)
    knowledge_claim_ids: list[StableId] = Field(default_factory=list)
    verification_status: StoryVerificationStatus
    enabled: StrictBool
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    media_slot_ids: list[StableId] = Field(default_factory=list)
    experience_slot_ids: list[StableId] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoryChapter(CatalogModel):
    chapter_id: StableId
    story_id: StableId
    sequence: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    chapter_type: StoryChapterType
    narrative_goal: str = Field(min_length=1, max_length=1000)
    anchor_ids: list[StableId] = Field(default_factory=list)
    poi_binding_ids: list[StableId] = Field(default_factory=list)
    required_claim_ids: list[StableId] = Field(default_factory=list)
    optional_claim_ids: list[StableId] = Field(default_factory=list)
    opening_hook: str = Field(min_length=1, max_length=1000)
    transition_goal: str = Field(min_length=1, max_length=1000)
    visitor_takeaway: str = Field(min_length=1, max_length=1000)
    recommended_duration_sec: int = Field(ge=1, le=3600)
    audience_tags: list[StoryAudience] = Field(default_factory=list)
    content_status: StoryVerificationStatus
    media_slot_ids: list[StableId] = Field(default_factory=list)
    experience_slot_ids: list[StableId] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperienceBlueprint(CatalogModel):
    experience_id: StableId
    title: str = Field(min_length=1, max_length=200)
    package_id: StableId
    region_id: StableId
    theme_id: StableId
    route_id: StableId
    story_id: StableId
    experience_type: ExperienceType
    target_audiences: list[ExperienceAudience] = Field(min_length=1)
    experience_goal: str = Field(min_length=1, max_length=1000)
    activity_ids: list[StableId] = Field(min_length=1)
    verification_status: ExperienceVerificationStatus
    enabled: StrictBool
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    estimated_total_duration_sec: int = Field(ge=1, le=86400)
    media_slot_ids: list[StableId] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperienceActivity(CatalogModel):
    activity_id: StableId
    experience_id: StableId
    sequence: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    activity_type: ExperienceActivityType
    content_mode: ExperienceContentMode
    story_chapter_ids: list[StableId] = Field(default_factory=list)
    anchor_ids: list[StableId] = Field(default_factory=list)
    poi_binding_ids: list[StableId] = Field(default_factory=list)
    required_claim_ids: list[StableId] = Field(default_factory=list)
    optional_claim_ids: list[StableId] = Field(default_factory=list)
    experience_goal: str = Field(min_length=1, max_length=1000)
    instruction_intent: str = Field(min_length=1, max_length=1500)
    observation_target: ExperienceObservationTarget
    visitor_output_type: VisitorOutputType
    estimated_duration_sec: int = Field(ge=1, le=3600)
    audience_tags: list[ExperienceAudience] = Field(default_factory=list)
    requires_guardian: StrictBool
    weather_sensitive: StrictBool
    risk_level: ExperienceRiskLevel
    safety_constraints: list[str] = Field(default_factory=list)
    prohibited_actions: list[ExperienceProhibitedAction] = Field(default_factory=list)
    materials_required: list[str] = Field(default_factory=list)
    requires_purchase: StrictBool
    requires_staff: StrictBool
    media_slot_ids: list[StableId] = Field(default_factory=list)
    content_status: ExperienceVerificationStatus
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContentPackageManifest(CatalogModel):
    package_id: StableId
    schema_version: str = Field(pattern=r"^\d+\.\d+$")
    content_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    region_id: StableId
    enabled: StrictBool


class ContentPackage(CatalogModel):
    manifest: ContentPackageManifest
    themes: list[CatalogTheme]
    routes: list[CuratedRoute]
    anchors: list[Anchor]
    poi_bindings: list[ExternalPoiBinding] = Field(default_factory=list)
    knowledge_sources: list[KnowledgeSource] = Field(default_factory=list)
    knowledge_claims: list[KnowledgeClaim] = Field(default_factory=list)
    knowledge_evidence: list[KnowledgeEvidence] = Field(default_factory=list)
    story_blueprints: list[StoryBlueprint] = Field(default_factory=list)
    story_chapters: list[StoryChapter] = Field(default_factory=list)
    experience_blueprints: list[ExperienceBlueprint] = Field(default_factory=list)
    experience_activities: list[ExperienceActivity] = Field(default_factory=list)
