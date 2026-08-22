from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    ContentPackage,
    ContentPackageManifest,
    EvidenceLocator,
    EvidenceRelation,
    KnowledgeClaim,
    KnowledgeClaimType,
    KnowledgeEvidence,
    KnowledgeSource,
    KnowledgeVerificationStatus,
    PromotionPolicy,
    PromotionPolicyStatus,
)
from app.catalog.repository import InMemoryCatalogRepository
from app.catalog.retrieval import KnowledgeQuery, KnowledgeRetriever


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
PACKAGE_ID = "shanxi.changzhi"
ANCHOR_ID = "changzhi.anchor.fajiushan"
THEME_ID = "changzhi.jingwei"
COUNTY_ID = "cn.shanxi.changzhi.changzi"
INTERNAL_CLAIM_ID = "changzhi.claim.fajiushan-yandi-residence"


def _source(
    source_id: str = "sample.source",
    *,
    status: KnowledgeVerificationStatus = KnowledgeVerificationStatus.VERIFIED,
) -> KnowledgeSource:
    return KnowledgeSource(
        source_id=source_id,
        title="地方文化资料",
        source_type="government",
        publisher_or_author="测试机构",
        publication_date="2026-01-02",
        url="https://example.test/source",
        document_reference="测试资料第1段",
        region_ids=[COUNTY_ID],
        language="zh-Hans",
        authority_level="authoritative",
        verification_status=status,
    )


def _claim(
    claim_id: str = "sample.claim",
    *,
    status: KnowledgeVerificationStatus = KnowledgeVerificationStatus.VERIFIED,
    policy: PromotionPolicyStatus = PromotionPolicyStatus.ALLOWED,
) -> KnowledgeClaim:
    qualifier = "据测试资料记载" if policy is PromotionPolicyStatus.ALLOWED_WITH_QUALIFICATION else None
    return KnowledgeClaim(
        claim_id=claim_id,
        subject_ids=["sample.subject"],
        claim_type="mythology",
        statement="测试资料记载了一个地方传说。",
        normalized_statement="测试资料记载地方传说",
        region_ids=[COUNTY_ID],
        theme_ids=[THEME_ID],
        anchor_ids=[ANCHOR_ID],
        verification_status=status,
        promotion_policy=PromotionPolicy(
            status=policy,
            required_qualifier=qualifier,
        ),
    )


def _evidence(
    evidence_id: str = "sample.evidence",
    *,
    claim_id: str = "sample.claim",
    source_id: str = "sample.source",
    relation: EvidenceRelation = EvidenceRelation.SUPPORTS,
    status: KnowledgeVerificationStatus = KnowledgeVerificationStatus.VERIFIED,
) -> KnowledgeEvidence:
    return KnowledgeEvidence(
        evidence_id=evidence_id,
        claim_id=claim_id,
        source_id=source_id,
        locator=EvidenceLocator(paragraph="正文第1段"),
        quote_excerpt="测试资料中的直接摘录。",
        evidence_relation=relation,
        verification_status=status,
    )


def _repository(
    *,
    claims: tuple[KnowledgeClaim, ...] | None = None,
    evidence: tuple[KnowledgeEvidence, ...] | None = None,
    sources: tuple[KnowledgeSource, ...] | None = None,
) -> InMemoryCatalogRepository:
    package = ContentPackage(
        manifest=ContentPackageManifest(
            package_id="sample.package",
            schema_version="1.0",
            content_version="1.2.3",
            region_id=COUNTY_ID,
            enabled=True,
        ),
        themes=[],
        routes=[],
        anchors=[],
        knowledge_claims=list(claims or (_claim(),)),
        knowledge_evidence=list(evidence or (_evidence(),)),
        knowledge_sources=list(sources or (_source(),)),
    )
    return InMemoryCatalogRepository(
        regions=(),
        themes=(),
        routes=(),
        anchors=(),
        manifests=(package.manifest,),
        packages=(package,),
        knowledge_claims=package.knowledge_claims,
        knowledge_evidence=package.knowledge_evidence,
        knowledge_sources=package.knowledge_sources,
    )


def _real_retriever() -> KnowledgeRetriever:
    return KnowledgeRetriever(FileCatalogLoader(CATALOG_ROOT).load())


def _ids(context) -> list[str]:
    return [hit.claim_id for hit in context.hits]


def test_query_and_context_are_frozen_serializable_snapshots():
    query = KnowledgeQuery(
        query_text="地方传说",
        region_ids=(COUNTY_ID,),
        theme_ids=(THEME_ID,),
        anchor_ids=(ANCHOR_ID,),
        claim_types=(KnowledgeClaimType.MYTHOLOGY,),
        limit=5,
    )
    context = KnowledgeRetriever(_repository()).retrieve("sample.package", query)

    assert context.package_id == "sample.package"
    assert context.schema_version == "1.0"
    assert context.content_version == "1.2.3"
    assert context.claim_count == 1
    assert context.source_count == 1
    assert context.model_validate_json(context.model_dump_json()) == context
    with pytest.raises(ValidationError, match="frozen"):
        query.limit = 2


def test_limit_is_bounded():
    with pytest.raises(ValidationError, match="less than or equal to 100"):
        KnowledgeQuery(limit=101)


@pytest.mark.parametrize(
    ("status", "policy"),
    [
        (KnowledgeVerificationStatus.DRAFT, PromotionPolicyStatus.ALLOWED),
        (KnowledgeVerificationStatus.REVIEW_REQUIRED, PromotionPolicyStatus.ALLOWED),
        (KnowledgeVerificationStatus.REJECTED, PromotionPolicyStatus.ALLOWED),
        (KnowledgeVerificationStatus.VERIFIED, PromotionPolicyStatus.INTERNAL_ONLY),
        (KnowledgeVerificationStatus.VERIFIED, PromotionPolicyStatus.FORBIDDEN),
    ],
)
def test_non_production_claims_do_not_leak(status, policy):
    claim = _claim(status=status, policy=policy)

    context = KnowledgeRetriever(_repository(claims=(claim,))).retrieve(
        "sample.package", KnowledgeQuery()
    )

    assert context.hits == ()


def test_disputed_is_excluded_by_default_and_explicit_when_included():
    claim = _claim(status=KnowledgeVerificationStatus.DISPUTED)
    retriever = KnowledgeRetriever(_repository(claims=(claim,)))

    assert retriever.retrieve("sample.package", KnowledgeQuery()).hits == ()
    context = retriever.retrieve(
        "sample.package", KnowledgeQuery(include_disputed=True)
    )
    assert _ids(context) == ["sample.claim"]
    assert "includes_disputed_claims" in context.warnings
    assert "disputed_claim" in context.hits[0].match_reasons


def test_unverified_evidence_or_source_does_not_pass_production_filter():
    unverified_evidence = _evidence(status=KnowledgeVerificationStatus.REVIEW_REQUIRED)
    unverified_source = _source(status=KnowledgeVerificationStatus.REVIEW_REQUIRED)

    assert KnowledgeRetriever(_repository(evidence=(unverified_evidence,))).retrieve(
        "sample.package", KnowledgeQuery()
    ).hits == ()
    assert KnowledgeRetriever(_repository(sources=(unverified_source,))).retrieve(
        "sample.package", KnowledgeQuery()
    ).hits == ()


def test_contradicts_is_not_support_and_verified_context_is_preserved():
    contradicts_only = _evidence(relation=EvidenceRelation.CONTRADICTS)
    assert KnowledgeRetriever(_repository(evidence=(contradicts_only,))).retrieve(
        "sample.package", KnowledgeQuery()
    ).hits == ()

    supporting = _evidence()
    contextual = _evidence(
        "sample.evidence.context",
        relation=EvidenceRelation.CONTEXTUALIZES,
    )
    context = KnowledgeRetriever(
        _repository(evidence=(contextual, supporting))
    ).retrieve("sample.package", KnowledgeQuery())

    assert [item.evidence_relation for item in context.hits[0].evidence] == [
        EvidenceRelation.SUPPORTS,
        EvidenceRelation.CONTEXTUALIZES,
    ]


def test_qualified_hit_preserves_all_provenance_fields_and_multiple_sources():
    claim = _claim(policy=PromotionPolicyStatus.ALLOWED_WITH_QUALIFICATION)
    second_source = _source("sample.source.second")
    second_evidence = _evidence(
        "sample.evidence.second", source_id=second_source.source_id
    )
    context = KnowledgeRetriever(
        _repository(
            claims=(claim,),
            evidence=(_evidence(), second_evidence),
            sources=(_source(), second_source),
        )
    ).retrieve("sample.package", KnowledgeQuery(query_text="地方传说"))
    hit = context.hits[0]

    assert hit.required_qualifier == "据测试资料记载"
    assert hit.promotion_policy.required_qualifier == hit.required_qualifier
    assert [item.evidence_id for item in hit.evidence] == [
        "sample.evidence",
        "sample.evidence.second",
    ]
    assert hit.evidence[0].locator.paragraph == "正文第1段"
    assert hit.evidence[0].quote_excerpt == "测试资料中的直接摘录。"
    assert [item.source_id for item in hit.sources] == [
        "sample.source",
        "sample.source.second",
    ]
    assert hit.sources[0].publisher_or_author == "测试机构"
    assert hit.sources[0].url == "https://example.test/source"


def test_real_query_a_returns_fajiushan_mythology_and_official_narrative():
    context = _real_retriever().retrieve(
        PACKAGE_ID,
        KnowledgeQuery(query_text="精卫为什么和发鸠山有关？", limit=12),
    )
    ids = set(_ids(context))

    assert "changzhi.claim.shanhaijing-fajiushan-passage" in ids
    assert any(hit.claim_type is KnowledgeClaimType.MYTHOLOGY for hit in context.hits)
    assert any(
        hit.claim_type is KnowledgeClaimType.OFFICIAL_NARRATIVE
        for hit in context.hits
    )
    assert INTERNAL_CLAIM_ID not in ids


def test_real_query_b_prioritizes_appearance():
    context = _real_retriever().retrieve(
        PACKAGE_ID, KnowledgeQuery(query_text="精卫长什么样？")
    )

    assert context.hits[0].claim_id == "changzhi.claim.jingwei-bird-appearance"
    assert "query_expansion_match" in context.hits[0].match_reasons


def test_real_query_c_prioritizes_drowning_and_filling_with_qualifiers():
    context = _real_retriever().retrieve(
        PACKAGE_ID, KnowledgeQuery(query_text="精卫为什么填海？")
    )
    top_ids = set(_ids(context)[:2])

    assert top_ids == {
        "changzhi.claim.nuwa-drowning",
        "changzhi.claim.jingwei-fills-sea",
    }
    assert all(context.hits[index].required_qualifier for index in range(2))


def test_real_query_d_prioritizes_geographic_claim_without_inventing_coordinates():
    context = _real_retriever().retrieve(
        PACKAGE_ID, KnowledgeQuery(query_text="发鸠山在哪里？")
    )

    assert context.hits[0].claim_id == "changzhi.claim.lingqiu-location"
    assert "claim_type_relevance" in context.hits[0].match_reasons
    assert "经度" not in context.hits[0].statement
    assert "纬度" not in context.hits[0].statement


def test_real_query_e_preserves_fact_layering_instead_of_answering_yes_or_no():
    context = _real_retriever().retrieve(
        PACKAGE_ID,
        KnowledgeQuery(query_text="精卫填海是不是历史真实事件？", limit=12),
    )
    types = {hit.claim_type for hit in context.hits}

    assert KnowledgeClaimType.MYTHOLOGY in types
    assert KnowledgeClaimType.HISTORICAL_FACT in types
    assert INTERNAL_CLAIM_ID not in _ids(context)


def test_real_query_f_never_leaks_internal_yandi_claim():
    context = _real_retriever().retrieve(
        PACKAGE_ID,
        KnowledgeQuery(query_text="发鸠山是不是炎帝居家的地方？", limit=100),
    )

    assert INTERNAL_CLAIM_ID not in _ids(context)
    assert context.warnings == ("insufficient_direct_match",)
    assert all(
        hit.promotion_policy.status
        not in {PromotionPolicyStatus.INTERNAL_ONLY, PromotionPolicyStatus.FORBIDDEN}
        for hit in context.hits
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("anchor_ids", (ANCHOR_ID,)),
        ("theme_ids", (THEME_ID,)),
        ("region_ids", (COUNTY_ID,)),
    ],
)
def test_structured_filters_limit_results(field, value):
    query = KnowledgeQuery(query_text="", **{field: value}, limit=100)
    context = _real_retriever().retrieve(PACKAGE_ID, query)

    assert context.hits
    assert all(set(value).intersection(getattr(hit, field)) for hit in context.hits)
    assert INTERNAL_CLAIM_ID not in _ids(context)


def test_claim_type_filter_and_limit_are_applied():
    context = _real_retriever().retrieve(
        PACKAGE_ID,
        KnowledgeQuery(
            claim_types=(KnowledgeClaimType.MYTHOLOGY,),
            limit=2,
        ),
    )

    assert len(context.hits) == 2
    assert all(hit.claim_type is KnowledgeClaimType.MYTHOLOGY for hit in context.hits)


def test_empty_query_with_anchor_filter_works():
    context = _real_retriever().retrieve(
        PACKAGE_ID, KnowledgeQuery(anchor_ids=(ANCHOR_ID,), limit=100)
    )

    assert context.hits
    assert all("anchor_match" in hit.match_reasons for hit in context.hits)


def test_no_text_match_returns_empty_context_without_fallback_content():
    context = _real_retriever().retrieve(
        PACKAGE_ID, KnowledgeQuery(query_text="量子芯片制造工艺")
    )

    assert context.hits == ()
    assert context.claim_count == 0
    assert context.source_count == 0
    assert context.warnings == ("no_matching_production_knowledge",)


def test_tied_results_sort_deterministically_by_claim_id():
    first = _claim("sample.claim.a")
    second = _claim("sample.claim.b")
    first_evidence = _evidence("sample.evidence.a", claim_id=first.claim_id)
    second_evidence = _evidence("sample.evidence.b", claim_id=second.claim_id)
    retriever = KnowledgeRetriever(
        _repository(
            claims=(second, first),
            evidence=(second_evidence, first_evidence),
        )
    )

    context = retriever.retrieve("sample.package", KnowledgeQuery())

    assert _ids(context) == ["sample.claim.a", "sample.claim.b"]
    assert context.hits[0].score == context.hits[1].score


def test_retrieval_python_contains_no_regional_or_theme_special_cases():
    path = PROJECT_ROOT / "app" / "catalog" / "retrieval.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    prohibited_tokens = {"changzhi", "jingwei", "fajiushan"}

    found = {
        token
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        for token in prohibited_tokens
        if token in node.value.casefold()
    }

    assert not found
