"""Standalone evidence-grounded cultural answer service."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from app.catalog.models import (
    EvidenceRelation,
    KnowledgeClaimType,
    PromotionPolicyStatus,
)
from app.catalog.repository import CatalogRepository
from app.catalog.retrieval import KnowledgeContext, KnowledgeQuery, KnowledgeRetriever
from app.knowledge.models import (
    AnswerStatus,
    AnswerabilityDecision,
    AnswerabilityLevel,
    CatalogVersionSnapshot,
    GroundedKnowledgeAnswer,
    KnowledgeAnswerRequest,
)
from app.knowledge.prompts import grounded_answer_messages
from app.llm.factory import build_structured_llm


INSUFFICIENT_ANSWER = "现有可用于公开输出的已核验资料不足以确认这一说法。"

_DIRECT_REASONS = {
    "query_exact_match",
    "query_expansion_match",
    "query_subsequence_match",
    "causal_relation_match",
    "claim_type_relevance",
    "anchor_match",
    "theme_match",
    "region_match",
    "claim_type_match",
}

_PROMOTION_PHRASES = (
    "历史上确实发生",
    "真实发生",
    "就是历史事实",
    "确有其事",
    "已经证实",
    "考古证明",
)

_NEGATION_MARKERS = (
    "不",
    "未",
    "没有",
    "并非",
    "不能",
    "不得",
    "不可",
    "无法",
)

_CLAUSE_BOUNDARIES = ("。", "！", "？", "；", "，", "但", "却", "而", "不过", "然而")


class KnowledgeAnswerValidationError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(dict.fromkeys(issues))
        super().__init__(", ".join(self.issues))


class KnowledgeAnswerServiceError(RuntimeError):
    pass


def evaluate_answerability(context: KnowledgeContext) -> AnswerabilityDecision:
    supporting_hits = tuple(
        hit
        for hit in context.hits
        if any(
            evidence.evidence_relation is EvidenceRelation.SUPPORTS
            for evidence in hit.evidence
        )
    )
    direct_hits = tuple(
        hit
        for hit in supporting_hits
        if _DIRECT_REASONS.intersection(hit.match_reasons)
    )
    reasons = list(context.warnings)
    reasons.extend(
        (
            f"supporting_claim_count:{len(supporting_hits)}",
            f"direct_claim_count:{len(direct_hits)}",
            f"max_retrieval_score:{max((hit.score for hit in supporting_hits), default=0)}",
        )
    )

    if not _precision_requirements_met(context):
        level = AnswerabilityLevel.INSUFFICIENT
        reasons.append("precision_not_supported")
    elif not supporting_hits or {
        "no_matching_production_knowledge",
        "insufficient_direct_match",
    }.intersection(context.warnings):
        level = AnswerabilityLevel.INSUFFICIENT
    elif direct_hits:
        level = AnswerabilityLevel.DIRECT_SUPPORT
    else:
        level = AnswerabilityLevel.PARTIAL_SUPPORT

    return AnswerabilityDecision(
        level=level,
        direct_claim_ids=tuple(hit.claim_id for hit in direct_hits),
        available_claim_ids=tuple(hit.claim_id for hit in supporting_hits),
        reasons=tuple(reasons),
    )


def validate_grounded_answer(
    answer: GroundedKnowledgeAnswer,
    context: KnowledgeContext,
    repository: CatalogRepository,
    answerability: AnswerabilityDecision,
) -> None:
    issues: list[str] = []
    hits = {hit.claim_id: hit for hit in context.hits}
    expected_version = CatalogVersionSnapshot(
        package_id=context.package_id,
        schema_version=context.schema_version,
        content_version=context.content_version,
    )
    if answer.catalog_version != expected_version:
        issues.append("catalog_version_mismatch")

    if (
        answerability.level is AnswerabilityLevel.PARTIAL_SUPPORT
        and answer.answer_status is AnswerStatus.ANSWERED
    ):
        issues.append("partial_support_cannot_be_fully_answered")
    if answer.answer_status is not AnswerStatus.INSUFFICIENT_EVIDENCE:
        if not answer.used_claim_ids:
            issues.append("used_claim_ids_required")
        if not answer.citations:
            issues.append("citations_required")

    used = set(answer.used_claim_ids)
    for claim_id in used:
        if claim_id not in hits:
            issues.append("claim_not_in_context")
        elif not repository.is_claim_production_eligible(claim_id):
            issues.append("claim_not_production_eligible")

    cited_claim_ids: set[str] = set()
    for citation in answer.citations:
        if citation.claim_id not in hits:
            issues.append("claim_not_in_context")
        if citation.claim_id not in used:
            issues.append("citation_claim_not_used")
            continue
        hit = hits.get(citation.claim_id)
        if hit is None:
            issues.append("claim_not_in_context")
            continue
        cited_claim_ids.add(citation.claim_id)
        evidence = next(
            (
                item
                for item in hit.evidence
                if item.evidence_id == citation.evidence_id
            ),
            None,
        )
        if evidence is None:
            issues.append("evidence_not_in_claim")
            continue
        if evidence.evidence_relation is not EvidenceRelation.SUPPORTS:
            issues.append("citation_evidence_not_supports")
        if evidence.source_id != citation.source_id:
            issues.append("source_not_for_evidence")
            continue
        source = next(
            (
                item
                for item in hit.sources
                if item.source_id == citation.source_id
            ),
            None,
        )
        if source is None:
            issues.append("source_not_for_evidence")
            continue
        if citation.locator != evidence.locator:
            issues.append("locator_mismatch")
        if citation.quote_excerpt != evidence.quote_excerpt:
            issues.append("quote_excerpt_mismatch")
        if citation.source_title != source.title or citation.url != source.url:
            issues.append("source_snapshot_mismatch")
        if citation.claim_type is not hit.claim_type:
            issues.append("claim_type_mismatch")
        if citation.promotion_policy is not hit.promotion_policy.status:
            issues.append("promotion_policy_mismatch")
        if citation.required_qualifier != hit.required_qualifier:
            issues.append("required_qualifier_mismatch")
        if citation.approved_wording != hit.approved_wording:
            issues.append("approved_wording_mismatch")

    if answer.answer_status is not AnswerStatus.INSUFFICIENT_EVIDENCE:
        if used.difference(cited_claim_ids):
            issues.append("used_claim_without_citation")

    _validate_qualifiers(answer, hits, issues)
    _validate_claim_types(answer, hits, issues)
    _validate_numbers(answer, context, issues)

    allowed_warnings = set(context.warnings) | {
        "partial_support",
        "insufficient_evidence",
    }
    if set(answer.warnings).difference(allowed_warnings):
        issues.append("warning_not_allowed")

    if issues:
        raise KnowledgeAnswerValidationError(issues)


class KnowledgeAnswerService:
    def __init__(
        self,
        repository: CatalogRepository,
        *,
        retriever: KnowledgeRetriever | None = None,
        llm: Any | None = None,
    ) -> None:
        self._repository = repository
        self._retriever = retriever or KnowledgeRetriever(repository)
        self._llm = llm

    def answer(self, request: KnowledgeAnswerRequest) -> GroundedKnowledgeAnswer:
        context = self._retriever.retrieve(
            request.package_id,
            KnowledgeQuery(
                query_text=request.question,
                region_ids=request.region_ids,
                theme_ids=request.theme_ids,
                anchor_ids=request.anchor_ids,
                claim_types=request.claim_types,
                limit=request.retrieval_limit,
            ),
        )
        answerability = evaluate_answerability(context)
        if answerability.level is AnswerabilityLevel.INSUFFICIENT:
            return _insufficient_answer(context, answerability)

        client = self._llm or build_structured_llm(
            GroundedKnowledgeAnswer, temperature=0
        )
        messages = grounded_answer_messages(
            request.question, context, answerability
        )
        last_issues: tuple[str, ...] = ()
        for attempt in range(2):
            try:
                raw = client.invoke(messages)
            except Exception as exc:
                raise KnowledgeAnswerServiceError(
                    f"structured_provider_failed: {type(exc).__name__}"
                ) from exc
            try:
                if raw is None:
                    raise KnowledgeAnswerValidationError(
                        ["structured_output_none"]
                    )
                answer = (
                    raw
                    if isinstance(raw, GroundedKnowledgeAnswer)
                    else GroundedKnowledgeAnswer.model_validate(raw)
                )
                validate_grounded_answer(
                    answer, context, self._repository, answerability
                )
                return answer
            except (KnowledgeAnswerValidationError, ValidationError) as exc:
                if isinstance(exc, KnowledgeAnswerValidationError):
                    last_issues = exc.issues
                else:
                    last_issues = (type(exc).__name__,)
                if attempt == 0:
                    messages = [
                        *messages,
                        HumanMessage(
                            content=(
                                "上一份结构化结果未通过确定性校验："
                                + ", ".join(last_issues)
                                + "。只能使用原始 KnowledgeContext 修正；"
                                "不得新增事实、Claim、Evidence 或 Source。"
                            ),
                            name="grounding_repair",
                        ),
                    ]
        raise KnowledgeAnswerServiceError(
            "validation_failed: " + ", ".join(last_issues)
        )


def _insufficient_answer(
    context: KnowledgeContext,
    answerability: AnswerabilityDecision,
) -> GroundedKnowledgeAnswer:
    warnings = tuple(dict.fromkeys((*context.warnings, *answerability.reasons)))
    return GroundedKnowledgeAnswer(
        answer=INSUFFICIENT_ANSWER,
        answer_status=AnswerStatus.INSUFFICIENT_EVIDENCE,
        used_claim_ids=(),
        citations=(),
        qualifiers_used=(),
        warnings=warnings,
        catalog_version=CatalogVersionSnapshot(
            package_id=context.package_id,
            schema_version=context.schema_version,
            content_version=context.content_version,
        ),
    )


def _validate_qualifiers(answer, hits, issues: list[str]) -> None:
    used_qualifiers = set(answer.qualifiers_used)
    permitted_qualifiers: set[str] = set()
    for claim_id in answer.used_claim_ids:
        hit = hits.get(claim_id)
        if hit is None:
            continue
        candidates = {
            item
            for item in (hit.required_qualifier, hit.approved_wording)
            if item
        }
        permitted_qualifiers.update(candidates)
        if (
            hit.promotion_policy.status
            is PromotionPolicyStatus.ALLOWED_WITH_QUALIFICATION
            and not any(candidate in answer.answer for candidate in candidates)
        ):
            issues.append("qualifier_missing")
        if (
            hit.promotion_policy.status
            is PromotionPolicyStatus.ALLOWED_WITH_QUALIFICATION
            and not any(
                candidate in answer.answer and candidate in used_qualifiers
                for candidate in candidates
            )
        ):
            issues.append("qualifier_not_recorded")
    if any(
        qualifier not in permitted_qualifiers or qualifier not in answer.answer
        for qualifier in used_qualifiers
    ):
        issues.append("qualifier_not_from_context")


def _validate_claim_types(answer, hits, issues: list[str]) -> None:
    used_types = {
        hits[claim_id].claim_type
        for claim_id in answer.used_claim_ids
        if claim_id in hits
    }
    if used_types.intersection(
        {KnowledgeClaimType.MYTHOLOGY, KnowledgeClaimType.LOCAL_LEGEND}
    ) and _contains_unnegated_promotion(answer.answer):
        issues.append("claim_type_promoted")
    if (
        KnowledgeClaimType.HISTORICAL_FACT in used_types
        and _contains_unnegated_promotion(answer.answer)
    ):
        issues.append("historical_text_overreach")


def _validate_numbers(
    answer: GroundedKnowledgeAnswer,
    context: KnowledgeContext,
    issues: list[str],
) -> None:
    allowed_text = context.query.query_text + context.model_dump_json()
    numbers = set(re.findall(r"\d+(?:\.\d+)?", answer.answer))
    if any(number not in allowed_text for number in numbers):
        issues.append("number_not_grounded")


def _precision_requirements_met(context: KnowledgeContext) -> bool:
    question = context.query.query_text
    searchable = [
        hit.statement
        + hit.normalized_statement
        + "".join(evidence.quote_excerpt for evidence in hit.evidence)
        for hit in context.hits
    ]
    combined = "".join(searchable)
    if any(term in question for term in ("经纬度", "坐标")):
        return any(term in combined for term in ("经纬度", "坐标"))
    if "考古" in question:
        return "考古" in combined
    if any(term in question for term in ("哪一年", "何年", "年份")):
        return any(
            "发生" in text and re.search(r"\d{4}", text)
            for text in searchable
        )
    return True


def _contains_unnegated_promotion(text: str) -> bool:
    for phrase in _PROMOTION_PHRASES:
        start = 0
        while (index := text.find(phrase, start)) >= 0:
            clause_start = max(
                (
                    text.rfind(marker, 0, index) + len(marker)
                    for marker in _CLAUSE_BOUNDARIES
                    if text.rfind(marker, 0, index) >= 0
                ),
                default=0,
            )
            prefix = text[clause_start:index]
            if not any(marker in prefix for marker in _NEGATION_MARKERS):
                return True
            start = index + len(phrase)
    return False
