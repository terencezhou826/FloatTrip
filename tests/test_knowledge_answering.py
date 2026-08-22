from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import KnowledgeClaimType, PromotionPolicyStatus
from app.catalog.retrieval import KnowledgeQuery, KnowledgeRetriever
from app.knowledge import (
    AnswerStatus,
    AnswerabilityLevel,
    CatalogVersionSnapshot,
    GroundedKnowledgeAnswer,
    KnowledgeAnswerRequest,
    KnowledgeAnswerService,
    KnowledgeAnswerServiceError,
    KnowledgeAnswerValidationError,
    KnowledgeCitation,
    evaluate_answerability,
    grounded_answer_messages,
    validate_grounded_answer,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
PACKAGE_ID = "shanxi.changzhi"
ANCHOR_ID = "changzhi.anchor.fajiushan"
THEME_ID = "changzhi.jingwei"
COUNTY_ID = "cn.shanxi.changzhi.changzi"
INTERNAL_CLAIM_ID = "changzhi.claim.fajiushan-yandi-residence"


class FakeStructuredLlm:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(scope="module")
def repository():
    return FileCatalogLoader(CATALOG_ROOT).load()


@pytest.fixture(scope="module")
def retriever(repository):
    return KnowledgeRetriever(repository)


def _context(retriever, question: str, *, limit: int = 10):
    return retriever.retrieve(
        PACKAGE_ID, KnowledgeQuery(query_text=question, limit=limit)
    )


def _hit(context, claim_id: str):
    return next(hit for hit in context.hits if hit.claim_id == claim_id)


def _citation(hit, *, evidence_index: int = 0) -> KnowledgeCitation:
    evidence = hit.evidence[evidence_index]
    source = next(
        item for item in hit.sources if item.source_id == evidence.source_id
    )
    return KnowledgeCitation(
        claim_id=hit.claim_id,
        evidence_id=evidence.evidence_id,
        source_id=source.source_id,
        source_title=source.title,
        locator=evidence.locator,
        url=source.url,
        quote_excerpt=evidence.quote_excerpt,
        claim_type=hit.claim_type,
        promotion_policy=hit.promotion_policy.status,
        required_qualifier=hit.required_qualifier,
        approved_wording=hit.approved_wording,
    )


def _version(context) -> CatalogVersionSnapshot:
    return CatalogVersionSnapshot(
        package_id=context.package_id,
        schema_version=context.schema_version,
        content_version=context.content_version,
    )


def _answer(
    context,
    claim_id: str,
    answer: str,
    *,
    status: AnswerStatus = AnswerStatus.ANSWERED,
    qualifiers_used: tuple[str, ...] = (),
) -> GroundedKnowledgeAnswer:
    hit = _hit(context, claim_id)
    return GroundedKnowledgeAnswer(
        answer=answer,
        answer_status=status,
        used_claim_ids=(hit.claim_id,),
        citations=(_citation(hit),),
        qualifiers_used=qualifiers_used,
        warnings=(),
        catalog_version=_version(context),
    )


def test_request_schema_defaults_and_serialization():
    request = KnowledgeAnswerRequest(
        question="精卫长什么样？",
        package_id=PACKAGE_ID,
        region_ids=(COUNTY_ID,),
        theme_ids=(THEME_ID,),
        anchor_ids=(ANCHOR_ID,),
        claim_types=(KnowledgeClaimType.MYTHOLOGY,),
    )

    assert request.retrieval_limit == 10
    assert request.model_validate_json(request.model_dump_json()) == request
    with pytest.raises(ValidationError, match="at least 1 character"):
        KnowledgeAnswerRequest(question="   ", package_id=PACKAGE_ID)


def test_default_limit_retains_ancient_mythology_and_official_context(retriever):
    request = KnowledgeAnswerRequest(
        question="精卫为什么和发鸠山有关？", package_id=PACKAGE_ID
    )
    context = retriever.retrieve(
        request.package_id,
        KnowledgeQuery(
            query_text=request.question,
            limit=request.retrieval_limit,
        ),
    )

    assert "changzhi.claim.shanhaijing-fajiushan-passage" in {
        hit.claim_id for hit in context.hits
    }
    assert KnowledgeClaimType.MYTHOLOGY in {hit.claim_type for hit in context.hits}
    assert KnowledgeClaimType.OFFICIAL_NARRATIVE in {
        hit.claim_type for hit in context.hits
    }


def test_answerability_gate_direct_and_insufficient(retriever):
    direct = evaluate_answerability(_context(retriever, "精卫长什么样？"))
    insufficient = evaluate_answerability(
        _context(retriever, "发鸠山是不是炎帝居家的地方？")
    )

    assert direct.level is AnswerabilityLevel.DIRECT_SUPPORT
    assert direct.direct_claim_ids
    assert insufficient.level is AnswerabilityLevel.INSUFFICIENT
    assert "insufficient_direct_match" in insufficient.reasons


def test_insufficient_gate_bypasses_llm_and_does_not_leak_internal_claim(
    repository, retriever
):
    llm = FakeStructuredLlm([])
    service = KnowledgeAnswerService(repository, retriever=retriever, llm=llm)

    answer = service.answer(
        KnowledgeAnswerRequest(
            question="发鸠山是不是炎帝居家的地方？",
            package_id=PACKAGE_ID,
        )
    )

    assert answer.answer_status is AnswerStatus.INSUFFICIENT_EVIDENCE
    assert answer.used_claim_ids == ()
    assert answer.citations == ()
    assert INTERNAL_CLAIM_ID not in answer.answer
    assert not llm.calls


def test_valid_citation_and_qualifier_pass(repository, retriever):
    context = _context(retriever, "精卫长什么样？")
    answer = _answer(
        context,
        "changzhi.claim.jingwei-bird-appearance",
        "据《山海经·北山经》记载，精卫被描写为形似乌、花纹头部、白喙、赤足的鸟。",
        qualifiers_used=("据《山海经·北山经》记载",),
    )

    validate_grounded_answer(
        answer, context, repository, evaluate_answerability(context)
    )
    assert answer.used_claim_count == 1
    assert answer.citation_count == 1
    assert answer.qualified_claim_count == 1
    assert answer.qualifier_satisfied_count == 1
    assert answer.grounding_coverage == 1.0
    assert answer.model_validate_json(answer.model_dump_json()) == answer


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("claim_id", "invented.claim", "claim_not_in_context"),
        ("evidence_id", "invented.evidence", "evidence_not_in_claim"),
        ("source_id", "invented.source", "source_not_for_evidence"),
    ],
)
def test_invented_citation_identity_fails(
    repository, retriever, field, value, error
):
    context = _context(retriever, "精卫长什么样？")
    valid = _answer(
        context,
        "changzhi.claim.jingwei-bird-appearance",
        "据《山海经·北山经》记载，精卫被描写为形似乌的鸟。",
        qualifiers_used=("据《山海经·北山经》记载",),
    )
    citation = valid.citations[0].model_copy(update={field: value})
    answer = valid.model_copy(update={"citations": (citation,)})

    with pytest.raises(KnowledgeAnswerValidationError, match=error):
        validate_grounded_answer(
            answer, context, repository, evaluate_answerability(context)
        )


def test_modified_locator_fails(repository, retriever):
    context = _context(retriever, "精卫长什么样？")
    valid = _answer(
        context,
        "changzhi.claim.jingwei-bird-appearance",
        "据《山海经·北山经》记载，精卫被描写为形似乌的鸟。",
        qualifiers_used=("据《山海经·北山经》记载",),
    )
    citation = valid.citations[0].model_copy(
        update={"locator": valid.citations[0].locator.model_copy(update={"paragraph": "999"})}
    )

    with pytest.raises(KnowledgeAnswerValidationError, match="locator_mismatch"):
        validate_grounded_answer(
            valid.model_copy(update={"citations": (citation,)}),
            context,
            repository,
            evaluate_answerability(context),
        )


def test_context_outside_and_internal_claim_fails(repository, retriever):
    context = _context(retriever, "精卫长什么样？")
    valid = _answer(
        context,
        "changzhi.claim.jingwei-bird-appearance",
        "据《山海经·北山经》记载，精卫被描写为形似乌的鸟。",
        qualifiers_used=("据《山海经·北山经》记载",),
    )
    answer = valid.model_copy(update={"used_claim_ids": (INTERNAL_CLAIM_ID,)})

    with pytest.raises(KnowledgeAnswerValidationError, match="claim_not_in_context"):
        validate_grounded_answer(
            answer, context, repository, evaluate_answerability(context)
        )


def test_missing_qualifier_fails(repository, retriever):
    context = _context(retriever, "精卫长什么样？")
    answer = _answer(
        context,
        "changzhi.claim.jingwei-bird-appearance",
        "精卫被描写为形似乌、白喙、赤足的鸟。",
    )

    with pytest.raises(KnowledgeAnswerValidationError, match="qualifier_missing"):
        validate_grounded_answer(
            answer, context, repository, evaluate_answerability(context)
        )


def test_official_narrative_requires_source_attribution(repository, retriever):
    context = _context(retriever, "精卫为什么和发鸠山有关？")
    answer = _answer(
        context,
        "changzhi.claim.changzi-official-birthplace",
        "发鸠山被表述为精卫填海故事的发祥地。",
    )

    with pytest.raises(KnowledgeAnswerValidationError, match="qualifier_missing"):
        validate_grounded_answer(
            answer, context, repository, evaluate_answerability(context)
        )


def test_allowed_claim_does_not_require_meaningless_qualifier(repository, retriever):
    context = _context(retriever, "精卫填海是不是历史真实事件？")
    answer = _answer(
        context,
        "changzhi.claim.shanhaijing-fajiushan-passage",
        "《山海经·北山经》中存在一段以发鸠之山为起点、记述精卫的文字。",
    )

    validate_grounded_answer(
        answer, context, repository, evaluate_answerability(context)
    )


def test_mythology_cannot_be_promoted_to_historical_fact(repository, retriever):
    context = _context(retriever, "精卫为什么填海？")
    answer = _answer(
        context,
        "changzhi.claim.jingwei-fills-sea",
        "据《山海经·北山经》的神话叙事，这证明精卫填海在历史上确实发生。",
        qualifiers_used=("据《山海经·北山经》的神话叙事",),
    )

    with pytest.raises(KnowledgeAnswerValidationError, match="claim_type_promoted"):
        validate_grounded_answer(
            answer, context, repository, evaluate_answerability(context)
        )


def test_negative_historical_caveat_is_allowed(repository, retriever):
    context = _context(retriever, "精卫为什么填海？")
    answer = _answer(
        context,
        "changzhi.claim.jingwei-fills-sea",
        "据《山海经·北山经》的神话叙事，精卫衔木石填海；这不能证明该事件真实发生。",
        qualifiers_used=("据《山海经·北山经》的神话叙事",),
    )

    validate_grounded_answer(
        answer, context, repository, evaluate_answerability(context)
    )


def test_contrast_does_not_hide_historical_promotion(repository, retriever):
    context = _context(retriever, "精卫为什么填海？")
    answer = _answer(
        context,
        "changzhi.claim.jingwei-fills-sea",
        "据《山海经·北山经》的神话叙事，这不是普通故事但历史上确实发生。",
        qualifiers_used=("据《山海经·北山经》的神话叙事",),
    )

    with pytest.raises(KnowledgeAnswerValidationError, match="claim_type_promoted"):
        validate_grounded_answer(
            answer, context, repository, evaluate_answerability(context)
        )


def test_new_number_outside_question_and_context_fails(repository, retriever):
    context = _context(retriever, "发鸠山在哪里？")
    answer = _answer(
        context,
        "changzhi.claim.lingqiu-location",
        "据长子县文化和旅游局资料，发鸠山的经度是112.999度。",
    )

    with pytest.raises(KnowledgeAnswerValidationError, match="number_not_grounded"):
        validate_grounded_answer(
            answer, context, repository, evaluate_answerability(context)
        )


def test_one_repair_attempt_can_restore_qualifier(repository, retriever):
    context = _context(retriever, "精卫长什么样？")
    invalid = _answer(
        context,
        "changzhi.claim.jingwei-bird-appearance",
        "精卫被描写为形似乌、白喙、赤足的鸟。",
    )
    valid = _answer(
        context,
        "changzhi.claim.jingwei-bird-appearance",
        "据《山海经·北山经》记载，精卫被描写为形似乌、白喙、赤足的鸟。",
        qualifiers_used=("据《山海经·北山经》记载",),
    )
    llm = FakeStructuredLlm([invalid, valid])
    service = KnowledgeAnswerService(repository, retriever=retriever, llm=llm)

    answer = service.answer(
        KnowledgeAnswerRequest(question="精卫长什么样？", package_id=PACKAGE_ID)
    )

    assert answer == valid
    assert len(llm.calls) == 2
    assert "qualifier_missing" in llm.calls[1][-1].content


def test_invalid_answer_after_repair_fails_closed(repository, retriever):
    context = _context(retriever, "精卫长什么样？")
    invalid = _answer(
        context,
        "changzhi.claim.jingwei-bird-appearance",
        "精卫被描写为形似乌的鸟。",
    )
    service = KnowledgeAnswerService(
        repository,
        retriever=retriever,
        llm=FakeStructuredLlm([invalid, invalid]),
    )

    with pytest.raises(KnowledgeAnswerServiceError, match="validation_failed"):
        service.answer(
            KnowledgeAnswerRequest(question="精卫长什么样？", package_id=PACKAGE_ID)
        )


def test_structured_provider_failure_does_not_fall_back_to_free_text(
    repository, retriever
):
    service = KnowledgeAnswerService(
        repository,
        retriever=retriever,
        llm=FakeStructuredLlm([RuntimeError("provider unavailable")]),
    )

    with pytest.raises(KnowledgeAnswerServiceError, match="structured_provider_failed"):
        service.answer(
            KnowledgeAnswerRequest(question="精卫长什么样？", package_id=PACKAGE_ID)
        )


@pytest.mark.parametrize(
    "question",
    [
        "精卫填海发生在哪一年？",
        "发鸠山的经纬度是多少？",
        "考古有没有证明精卫存在？",
    ],
)
def test_hallucination_injection_is_rejected_before_llm(
    repository, retriever, question
):
    llm = FakeStructuredLlm([])
    service = KnowledgeAnswerService(repository, retriever=retriever, llm=llm)

    answer = service.answer(
        KnowledgeAnswerRequest(question=question, package_id=PACKAGE_ID)
    )

    assert answer.answer_status is AnswerStatus.INSUFFICIENT_EVIDENCE
    assert answer.used_claim_ids == ()
    assert not llm.calls


def test_grounded_prompt_contains_memory_isolation_and_context(retriever):
    context = _context(retriever, "精卫长什么样？")
    gate = evaluate_answerability(context)
    messages = grounded_answer_messages("精卫长什么样？", context, gate)
    combined = "\n".join(message.content for message in messages)

    assert "只能使用提供的 KnowledgeContext" in combined
    assert "不得使用模型记忆" in combined
    assert "mythology" in combined
    assert "required_qualifier" in combined
    assert "只能复述该相对关系" in combined
    assert context.package_id in combined


def test_knowledge_answering_core_has_no_regional_special_cases():
    prohibited_tokens = {"changzhi", "jingwei", "fajiushan"}
    found = []
    for path in sorted((PROJECT_ROOT / "app" / "knowledge").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for token in prohibited_tokens:
                    if token in node.value.casefold():
                        found.append((path.name, token))

    assert not found
