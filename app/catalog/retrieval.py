"""Deterministic, evidence-aware retrieval over a Catalog package snapshot."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from datetime import date

from pydantic import Field, field_validator

from app.catalog.models import (
    AuthorityLevel,
    CatalogModel,
    EvidenceLocator,
    EvidenceRelation,
    KnowledgeClaim,
    KnowledgeClaimType,
    KnowledgeEvidence,
    KnowledgeSource,
    KnowledgeSourceType,
    KnowledgeVerificationStatus,
    PromotionPolicy,
    PromotionPolicyStatus,
    StableId,
)
from app.catalog.repository import CatalogRepository


class KnowledgeRetrievalError(ValueError):
    pass


class KnowledgeQuery(CatalogModel):
    query_text: str = Field(default="", max_length=1000)
    region_ids: tuple[StableId, ...] = ()
    theme_ids: tuple[StableId, ...] = ()
    anchor_ids: tuple[StableId, ...] = ()
    claim_types: tuple[KnowledgeClaimType, ...] = ()
    limit: int = Field(default=10, ge=1, le=100)
    include_disputed: bool = False

    @field_validator("query_text")
    @classmethod
    def strip_query_text(cls, value: str) -> str:
        return value.strip()


class KnowledgeEvidenceSnapshot(CatalogModel):
    evidence_id: StableId
    source_id: StableId
    evidence_relation: EvidenceRelation
    locator: EvidenceLocator
    quote_excerpt: str


class KnowledgeSourceSnapshot(CatalogModel):
    source_id: StableId
    title: str
    source_type: KnowledgeSourceType
    authority_level: AuthorityLevel
    publisher_or_author: str
    publication_date: date | None
    url: str | None
    document_reference: str | None


class KnowledgeHit(CatalogModel):
    claim_id: StableId
    claim_type: KnowledgeClaimType
    statement: str
    normalized_statement: str
    verification_status: KnowledgeVerificationStatus
    promotion_policy: PromotionPolicy
    required_qualifier: str | None
    approved_wording: str | None
    region_ids: tuple[StableId, ...]
    theme_ids: tuple[StableId, ...]
    anchor_ids: tuple[StableId, ...]
    evidence: tuple[KnowledgeEvidenceSnapshot, ...]
    sources: tuple[KnowledgeSourceSnapshot, ...]
    score: float = Field(ge=0)
    match_reasons: tuple[str, ...]


class KnowledgeContext(CatalogModel):
    query: KnowledgeQuery
    hits: tuple[KnowledgeHit, ...]
    claim_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    package_id: StableId
    schema_version: str
    content_version: str
    warnings: tuple[str, ...] = ()


_CJK_RUN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
_WORD_RE = re.compile(r"[a-z0-9]+")

# These are generic Chinese query forms, not content- or Region-specific aliases.
_QUERY_EXPANSIONS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("长什么样", "什么样", "外貌", "外形", "样貌", "长相"),
        ("形似", "形状", "外貌", "外形", "样貌", "长相"),
    ),
    (
        ("为什么", "为何", "原因", "缘由", "起因"),
        ("因此", "原因", "缘由", "起因"),
    ),
    (
        ("在哪里", "在哪", "哪儿", "何处", "位置", "位于", "坐落"),
        ("位于", "处于", "位置", "地点", "坐落"),
    ),
    (
        ("历史", "真实", "事实", "真的"),
        ("神话", "传说", "记载", "文字", "历史"),
    ),
)

_CLAIM_TYPE_TERMS: dict[KnowledgeClaimType, str] = {
    KnowledgeClaimType.HISTORICAL_FACT: "历史 事实 文本 记载",
    KnowledgeClaimType.MYTHOLOGY: "神话 传说",
    KnowledgeClaimType.LOCAL_LEGEND: "地方传说 民间传说",
    KnowledgeClaimType.ACADEMIC_INTERPRETATION: "学术 研究 解释",
    KnowledgeClaimType.OFFICIAL_NARRATIVE: "官方资料 官方表述",
    KnowledgeClaimType.TOURISM_OPERATION: "旅游 运营",
    KnowledgeClaimType.GEOGRAPHIC_FACT: "地理 位置 位于 地点",
    KnowledgeClaimType.HERITAGE_FACT: "非遗 文化遗产 名录",
}

_RELATION_ORDER = {
    EvidenceRelation.SUPPORTS: 0,
    EvidenceRelation.CONTRADICTS: 1,
    EvidenceRelation.CONTEXTUALIZES: 2,
    EvidenceRelation.MENTIONS: 3,
}

_AUTHORITY_SCORE = {
    AuthorityLevel.PRIMARY: 0.25,
    AuthorityLevel.AUTHORITATIVE: 0.25,
    AuthorityLevel.SCHOLARLY: 0.25,
    AuthorityLevel.SECONDARY: 0.1,
    AuthorityLevel.REFERENCE_ONLY: 0.0,
}


class KnowledgeRetriever:
    def __init__(self, repository: CatalogRepository) -> None:
        self._repository = repository

    def retrieve(
        self, package_id: str, query: KnowledgeQuery
    ) -> KnowledgeContext:
        package = self._repository.get_package(package_id)
        if package is None or not package.manifest.enabled:
            raise KnowledgeRetrievalError(
                f"enabled Catalog package not found: {package_id}"
            )

        sources_by_id = {
            source.source_id: source for source in package.knowledge_sources
        }
        evidence_by_claim: dict[str, list[KnowledgeEvidence]] = defaultdict(list)
        for evidence in package.knowledge_evidence:
            evidence_by_claim[evidence.claim_id].append(evidence)

        ranked: list[KnowledgeHit] = []
        for claim in package.knowledge_claims:
            if not self._matches_structured_scope(claim, query):
                continue

            verified_evidence = self._verified_evidence(
                evidence_by_claim.get(claim.claim_id, ()), sources_by_id
            )
            if not self._is_retrievable(claim, verified_evidence, query):
                continue

            sources = self._ordered_sources(verified_evidence, sources_by_id)
            score, reasons = self._rank(claim, sources, query)
            if query.query_text and not self._has_query_match(reasons):
                continue

            ranked.append(
                self._build_hit(
                    claim=claim,
                    evidence=verified_evidence,
                    sources=sources,
                    score=score,
                    reasons=reasons,
                )
            )

        ranked.sort(key=lambda hit: (-hit.score, hit.claim_id))
        hits = tuple(ranked[: query.limit])
        warnings: list[str] = []
        if not hits and query.query_text:
            warnings.append("no_matching_production_knowledge")
        if hits and query.query_text and not any(
            _has_direct_match(hit.match_reasons) for hit in hits
        ):
            warnings.append("insufficient_direct_match")
        if any(
            hit.verification_status is KnowledgeVerificationStatus.DISPUTED
            for hit in hits
        ):
            warnings.append("includes_disputed_claims")

        return KnowledgeContext(
            query=query,
            hits=hits,
            claim_count=len(hits),
            source_count=len(
                {source.source_id for hit in hits for source in hit.sources}
            ),
            package_id=package.manifest.package_id,
            schema_version=package.manifest.schema_version,
            content_version=package.manifest.content_version,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _matches_structured_scope(
        claim: KnowledgeClaim, query: KnowledgeQuery
    ) -> bool:
        filters = (
            (query.region_ids, claim.region_ids),
            (query.theme_ids, claim.theme_ids),
            (query.anchor_ids, claim.anchor_ids),
            (query.claim_types, (claim.claim_type,)),
        )
        return all(
            not requested or bool(set(requested).intersection(actual))
            for requested, actual in filters
        )

    @staticmethod
    def _verified_evidence(
        evidence_items: Iterable[KnowledgeEvidence],
        sources_by_id: dict[str, KnowledgeSource],
    ) -> tuple[KnowledgeEvidence, ...]:
        valid = [
            evidence
            for evidence in evidence_items
            if evidence.verification_status is KnowledgeVerificationStatus.VERIFIED
            and (source := sources_by_id.get(evidence.source_id)) is not None
            and source.verification_status is KnowledgeVerificationStatus.VERIFIED
        ]
        return tuple(
            sorted(
                valid,
                key=lambda item: (
                    _RELATION_ORDER[item.evidence_relation],
                    item.evidence_id,
                ),
            )
        )

    def _is_retrievable(
        self,
        claim: KnowledgeClaim,
        evidence: tuple[KnowledgeEvidence, ...],
        query: KnowledgeQuery,
    ) -> bool:
        if claim.promotion_policy.status not in {
            PromotionPolicyStatus.ALLOWED,
            PromotionPolicyStatus.ALLOWED_WITH_QUALIFICATION,
        }:
            return False
        if claim.verification_status is KnowledgeVerificationStatus.VERIFIED:
            if not self._repository.is_claim_production_eligible(claim.claim_id):
                return False
        elif not (
            query.include_disputed
            and claim.verification_status is KnowledgeVerificationStatus.DISPUTED
        ):
            return False
        return any(
            item.evidence_relation is EvidenceRelation.SUPPORTS for item in evidence
        )

    @staticmethod
    def _ordered_sources(
        evidence: tuple[KnowledgeEvidence, ...],
        sources_by_id: dict[str, KnowledgeSource],
    ) -> tuple[KnowledgeSource, ...]:
        ordered_ids = dict.fromkeys(item.source_id for item in evidence)
        return tuple(sources_by_id[source_id] for source_id in ordered_ids)

    @staticmethod
    def _rank(
        claim: KnowledgeClaim,
        sources: tuple[KnowledgeSource, ...],
        query: KnowledgeQuery,
    ) -> tuple[float, tuple[str, ...]]:
        score = 0.0
        reasons: list[str] = []

        for requested, actual, weight, reason in (
            (query.anchor_ids, claim.anchor_ids, 8.0, "anchor_match"),
            (query.theme_ids, claim.theme_ids, 6.0, "theme_match"),
            (query.region_ids, claim.region_ids, 4.0, "region_match"),
            (query.claim_types, (claim.claim_type,), 2.0, "claim_type_match"),
        ):
            if requested and set(requested).intersection(actual):
                score += weight
                reasons.append(reason)

        normalized_query = _normalize(query.query_text)
        if normalized_query:
            score, query_reasons = _score_query(
                normalized_query=normalized_query,
                claim=claim,
                source_titles=tuple(source.title for source in sources),
                score=score,
            )
            reasons.extend(query_reasons)

        authority_levels = sorted(
            {source.authority_level for source in sources}, key=lambda item: item.value
        )
        if authority_levels:
            score += max(_AUTHORITY_SCORE[level] for level in authority_levels)
            reasons.extend(
                f"source_authority_{level.value}" for level in authority_levels
            )
        if claim.verification_status is KnowledgeVerificationStatus.DISPUTED:
            reasons.append("disputed_claim")

        return round(score, 6), tuple(dict.fromkeys(reasons))

    @staticmethod
    def _has_query_match(reasons: tuple[str, ...]) -> bool:
        return any(
            reason
            in {
                "query_exact_match",
                "statement_match",
                "normalized_statement_match",
                "source_title_match",
                "query_expansion_match",
                "query_subsequence_match",
                "causal_relation_match",
                "claim_type_relevance",
            }
            for reason in reasons
        )

    @staticmethod
    def _build_hit(
        *,
        claim: KnowledgeClaim,
        evidence: tuple[KnowledgeEvidence, ...],
        sources: tuple[KnowledgeSource, ...],
        score: float,
        reasons: tuple[str, ...],
    ) -> KnowledgeHit:
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
                for source in sources
            ),
            score=score,
            match_reasons=reasons,
        )


def _score_query(
    *,
    normalized_query: str,
    claim: KnowledgeClaim,
    source_titles: tuple[str, ...],
    score: float,
) -> tuple[float, tuple[str, ...]]:
    reasons: list[str] = []
    statement = _normalize(claim.statement)
    normalized_statement = _normalize(claim.normalized_statement)
    source_text = _normalize(" ".join(source_titles))
    claim_type_text = _normalize(_CLAIM_TYPE_TERMS[claim.claim_type])

    if normalized_query in statement or normalized_query in normalized_statement:
        score += 12.0
        reasons.append("query_exact_match")

    query_units = _lexical_units(normalized_query)
    for text, weight, reason in (
        (statement, 1.5, "statement_match"),
        (normalized_statement, 2.0, "normalized_statement_match"),
        (source_text, 0.75, "source_title_match"),
    ):
        matches = {unit for unit in query_units if unit in text}
        if matches:
            score += len(matches) * weight
            reasons.append(reason)

    expansions, preferred_types = _query_expansions(normalized_query)
    expansion_matches = {
        term
        for term in expansions
        if term in statement
        or term in normalized_statement
        or term in source_text
        or term in claim_type_text
    }
    if expansion_matches:
        score += len(expansion_matches) * 3.0
        reasons.append("query_expansion_match")

    if _has_causal_question(normalized_query) and any(
        _contains_causal_marker(text) for text in (statement, normalized_statement)
    ):
        score += 7.0
        reasons.append("causal_relation_match")

    content_query = normalized_query
    for phrase in ("为什么", "为何", "长什么样", "什么样", "在哪里", "在哪", "是不是", "是否"):
        content_query = content_query.replace(_normalize(phrase), "")
    query_runs = [run for run in _CJK_RUN_RE.findall(content_query) if len(run) >= 2]
    if any(
        _is_ordered_subsequence(run, text)
        for run in query_runs
        for text in (statement, normalized_statement)
        if run not in text
    ):
        score += 6.0
        reasons.append("query_subsequence_match")

    if claim.claim_type in preferred_types:
        score += 12.0
        reasons.append("claim_type_relevance")

    return score, tuple(reasons)


def _query_expansions(
    normalized_query: str,
) -> tuple[set[str], set[KnowledgeClaimType]]:
    expansions: set[str] = set()
    preferred_types: set[KnowledgeClaimType] = set()
    for triggers, terms in _QUERY_EXPANSIONS:
        if any(_normalize(trigger) in normalized_query for trigger in triggers):
            expansions.update(_normalize(term) for term in terms)

    if any(
        trigger in normalized_query
        for trigger in (_normalize(item) for item in ("在哪里", "在哪", "何处", "位置"))
    ):
        preferred_types.add(KnowledgeClaimType.GEOGRAPHIC_FACT)
    if any(
        trigger in normalized_query
        for trigger in (_normalize(item) for item in ("历史", "真实", "事实"))
    ):
        preferred_types.update(
            {
                KnowledgeClaimType.HISTORICAL_FACT,
                KnowledgeClaimType.MYTHOLOGY,
                KnowledgeClaimType.LOCAL_LEGEND,
            }
        )
    return expansions, preferred_types


def _lexical_units(text: str) -> set[str]:
    units = set(_WORD_RE.findall(text))
    for run in _CJK_RUN_RE.findall(text):
        for size in (2, 3):
            units.update(
                run[index : index + size]
                for index in range(len(run) - size + 1)
            )
    return units


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _is_ordered_subsequence(needle: str, haystack: str) -> bool:
    iterator = iter(haystack)
    return all(character in iterator for character in needle)


def _has_direct_match(reasons: tuple[str, ...]) -> bool:
    direct_reasons = {
        "query_exact_match",
        "query_expansion_match",
        "query_subsequence_match",
        "causal_relation_match",
        "claim_type_relevance",
    }
    return bool(direct_reasons.intersection(reasons))


def _has_causal_question(normalized_query: str) -> bool:
    return any(
        _normalize(term) in normalized_query
        for term in ("为什么", "为何", "原因", "缘由", "起因")
    )


def _contains_causal_marker(text: str) -> bool:
    if any(marker in text for marker in ("因为", "由于", "所以", "因此")):
        return True
    return any(
        text[index] == "故"
        and (index + 1 == len(text) or text[index + 1] != "事")
        for index in range(len(text))
    )
