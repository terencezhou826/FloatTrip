"""Frozen contracts for evidence-grounded cultural answers."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, computed_field, field_validator, model_validator

from app.catalog.models import (
    CatalogModel,
    EvidenceLocator,
    KnowledgeClaimType,
    PromotionPolicyStatus,
    StableId,
)


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    PARTIALLY_ANSWERED = "partially_answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AnswerabilityLevel(StrEnum):
    DIRECT_SUPPORT = "direct_support"
    PARTIAL_SUPPORT = "partial_support"
    INSUFFICIENT = "insufficient"


class KnowledgeAnswerRequest(CatalogModel):
    question: str = Field(min_length=1, max_length=1000)
    package_id: StableId
    region_ids: tuple[StableId, ...] = ()
    theme_ids: tuple[StableId, ...] = ()
    anchor_ids: tuple[StableId, ...] = ()
    claim_types: tuple[KnowledgeClaimType, ...] = ()
    retrieval_limit: int = Field(default=10, ge=1, le=100)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must contain at least 1 character")
        return value


class CatalogVersionSnapshot(CatalogModel):
    package_id: StableId
    schema_version: str
    content_version: str


class KnowledgeCitation(CatalogModel):
    claim_id: StableId
    evidence_id: StableId
    source_id: StableId
    source_title: str
    locator: EvidenceLocator
    url: str | None
    quote_excerpt: str
    claim_type: KnowledgeClaimType
    promotion_policy: PromotionPolicyStatus
    required_qualifier: str | None
    approved_wording: str | None


class GroundedKnowledgeAnswer(CatalogModel):
    answer: str = Field(min_length=1, max_length=5000)
    answer_status: AnswerStatus
    used_claim_ids: tuple[StableId, ...]
    citations: tuple[KnowledgeCitation, ...]
    qualifiers_used: tuple[str, ...]
    warnings: tuple[str, ...]
    catalog_version: CatalogVersionSnapshot

    @model_validator(mode="before")
    @classmethod
    def discard_serialized_metrics(cls, value):
        if isinstance(value, dict):
            value = dict(value)
            for field in (
                "used_claim_count",
                "citation_count",
                "qualified_claim_count",
                "qualifier_satisfied_count",
                "grounding_coverage",
            ):
                value.pop(field, None)
        return value

    @field_validator("used_claim_ids", "qualifiers_used", "warnings")
    @classmethod
    def require_unique_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("values must be unique")
        return value

    @computed_field(return_type=int)
    @property
    def used_claim_count(self) -> int:
        return len(self.used_claim_ids)

    @computed_field(return_type=int)
    @property
    def citation_count(self) -> int:
        return len(self.citations)

    @computed_field(return_type=int)
    @property
    def qualified_claim_count(self) -> int:
        return len(
            {
                citation.claim_id
                for citation in self.citations
                if citation.promotion_policy
                is PromotionPolicyStatus.ALLOWED_WITH_QUALIFICATION
            }
        )

    @computed_field(return_type=int)
    @property
    def qualifier_satisfied_count(self) -> int:
        satisfied: set[str] = set()
        for citation in self.citations:
            if (
                citation.promotion_policy
                is not PromotionPolicyStatus.ALLOWED_WITH_QUALIFICATION
            ):
                continue
            candidates = (
                citation.required_qualifier,
                citation.approved_wording,
            )
            if any(candidate and candidate in self.answer for candidate in candidates):
                satisfied.add(citation.claim_id)
        return len(satisfied)

    @computed_field(return_type=float)
    @property
    def grounding_coverage(self) -> float:
        used = set(self.used_claim_ids)
        cited = {citation.claim_id for citation in self.citations}
        denominator = len(used) + self.qualified_claim_count
        if denominator == 0:
            return 1.0
        numerator = len(used.intersection(cited)) + self.qualifier_satisfied_count
        return round(numerator / denominator, 6)


class AnswerabilityDecision(CatalogModel):
    level: AnswerabilityLevel
    direct_claim_ids: tuple[StableId, ...]
    available_claim_ids: tuple[StableId, ...]
    reasons: tuple[str, ...]
