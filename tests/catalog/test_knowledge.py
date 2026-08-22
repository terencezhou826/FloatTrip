from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.loader import CatalogLoadError, FileCatalogLoader
from app.catalog.models import (
    AuthorityLevel,
    EvidenceRelation,
    KnowledgeClaim,
    KnowledgeClaimType,
    KnowledgeEvidence,
    KnowledgeSource,
    KnowledgeSourceType,
    KnowledgeVerificationStatus,
    PromotionPolicyStatus,
)
from app.catalog.repository import InMemoryCatalogRepository
from app.catalog.validation import (
    CatalogValidationError,
    calculate_evidence_coverage,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
PACKAGE_ROOT = Path("packages") / "shanxi" / "changzhi"


def _catalog_copy(tmp_path: Path) -> Path:
    target = tmp_path / "catalog"
    shutil.copytree(CATALOG_ROOT, target)
    return target


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _source(source_id: str = "sample.source") -> dict:
    return {
        "source_id": source_id,
        "title": "Sample source",
        "source_type": "government",
        "publisher_or_author": "Sample publisher",
        "publication_date": "2026-01-02",
        "url": "https://example.test/source",
        "document_reference": None,
        "region_ids": ["cn.shanxi.changzhi.changzi"],
        "language": "zh-Hans",
        "authority_level": "authoritative",
        "verification_status": "verified",
        "metadata": {},
    }


def _claim(
    claim_id: str = "sample.claim",
    *,
    status: str = "verified",
    policy: str = "allowed",
) -> dict:
    return {
        "claim_id": claim_id,
        "subject_ids": ["sample.subject"],
        "claim_type": "mythology",
        "statement": "A source frames this as a mythology narrative.",
        "normalized_statement": "source frames mythology narrative",
        "region_ids": ["cn.shanxi.changzhi.changzi"],
        "theme_ids": ["changzhi.jingwei"],
        "anchor_ids": ["changzhi.anchor.fajiushan"],
        "verification_status": status,
        "promotion_policy": {
            "status": policy,
            "approved_wording": None,
            "required_qualifier": None,
            "forbidden_wordings": [],
        },
        "valid_from": None,
        "valid_to": None,
        "metadata": {},
    }


def _evidence(
    evidence_id: str = "sample.evidence",
    *,
    claim_id: str = "sample.claim",
    source_id: str = "sample.source",
    relation: str = "supports",
) -> dict:
    return {
        "evidence_id": evidence_id,
        "claim_id": claim_id,
        "source_id": source_id,
        "locator": {"paragraph": "1"},
        "quote_excerpt": "A short, directly checked excerpt.",
        "evidence_relation": relation,
        "verification_status": "verified",
        "metadata": {},
    }


def _append_knowledge(root: Path, key: str, item: dict) -> None:
    path = root / PACKAGE_ROOT / "knowledge" / f"{key}.json"
    payload = _read_json(path)
    payload[key].append(item)
    _write_json(path, payload)


def test_source_schema_and_controlled_enums():
    source = KnowledgeSource.model_validate(_source())

    assert source.source_type is KnowledgeSourceType.GOVERNMENT
    assert source.authority_level is AuthorityLevel.AUTHORITATIVE
    assert {item.value for item in KnowledgeSourceType} == {
        "ancient_text",
        "government",
        "academic",
        "local_chronicle",
        "heritage_record",
        "scenic_official",
        "museum",
        "news",
        "tourism_operation",
        "other",
    }
    assert {item.value for item in AuthorityLevel} == {
        "primary",
        "authoritative",
        "scholarly",
        "secondary",
        "reference_only",
    }


def test_invalid_source_type_is_rejected():
    payload = _source()
    payload["source_type"] = "mythology"

    with pytest.raises(ValidationError, match="source_type"):
        KnowledgeSource.model_validate(payload)


def test_claim_schema_and_controlled_types():
    claim = KnowledgeClaim.model_validate(_claim(status="draft"))

    assert claim.claim_type is KnowledgeClaimType.MYTHOLOGY
    assert claim.verification_status is KnowledgeVerificationStatus.DRAFT
    assert {item.value for item in KnowledgeClaimType} == {
        "historical_fact",
        "mythology",
        "local_legend",
        "academic_interpretation",
        "official_narrative",
        "tourism_operation",
        "geographic_fact",
        "heritage_fact",
    }


def test_invalid_claim_type_is_rejected():
    payload = _claim(status="draft")
    payload["claim_type"] = "certain_truth"

    with pytest.raises(ValidationError, match="claim_type"):
        KnowledgeClaim.model_validate(payload)


def test_claim_validity_dates_must_be_ordered():
    payload = _claim(status="draft")
    payload["valid_from"] = "2026-02-01"
    payload["valid_to"] = "2026-01-01"

    with pytest.raises(ValidationError, match="valid_from"):
        KnowledgeClaim.model_validate(payload)


def test_promotion_policy_and_qualification_requirement():
    qualified = _claim(status="draft", policy="allowed_with_qualification")
    qualified["promotion_policy"]["required_qualifier"] = "相传"
    claim = KnowledgeClaim.model_validate(qualified)

    assert claim.promotion_policy.status is PromotionPolicyStatus.ALLOWED_WITH_QUALIFICATION
    assert claim.promotion_policy.required_qualifier == "相传"

    missing = _claim(status="draft", policy="allowed_with_qualification")
    with pytest.raises(ValidationError, match="requires approved_wording"):
        KnowledgeClaim.model_validate(missing)


@pytest.mark.parametrize("status", ["rejected", "disputed"])
def test_rejected_and_disputed_claims_are_representable(status):
    claim = KnowledgeClaim.model_validate(_claim(status=status))

    assert claim.verification_status.value == status


@pytest.mark.parametrize("relation", ["supports", "contradicts"])
def test_evidence_supports_and_contradicts_are_distinct(relation):
    evidence = KnowledgeEvidence.model_validate(_evidence(relation=relation))

    assert evidence.evidence_relation is EvidenceRelation(relation)


def test_verified_claim_without_evidence_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    _append_knowledge(root, "claims", _claim("sample.claim.orphan"))

    with pytest.raises(CatalogValidationError, match="has no verified supporting evidence"):
        FileCatalogLoader(root).load()


def test_verified_claim_with_evidence_and_verified_source_is_valid(tmp_path):
    root = _catalog_copy(tmp_path)
    _append_knowledge(root, "sources", _source())
    _append_knowledge(root, "claims", _claim())
    _append_knowledge(root, "evidence", _evidence())

    catalog = FileCatalogLoader(root).load()

    assert catalog.is_claim_production_eligible("sample.claim")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("claim_id", "missing.claim", "missing claim"),
        ("source_id", "missing.source", "missing source"),
    ],
)
def test_evidence_dangling_references_are_rejected(tmp_path, field, value, message):
    root = _catalog_copy(tmp_path)
    payload = _evidence(f"sample.evidence.{field}")
    payload[field] = value
    _append_knowledge(root, "evidence", payload)

    with pytest.raises(CatalogValidationError, match=message):
        FileCatalogLoader(root).load()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("region_ids", ["missing.region"], "missing region"),
        ("theme_ids", ["missing.theme"], "missing theme"),
        ("anchor_ids", ["missing.anchor"], "missing anchor"),
    ],
)
def test_claim_dangling_catalog_references_are_rejected(
    tmp_path, field, value, message
):
    root = _catalog_copy(tmp_path)
    payload = _claim(f"sample.claim.{field}", status="draft")
    payload[field] = value
    _append_knowledge(root, "claims", payload)

    with pytest.raises(CatalogValidationError, match=message):
        FileCatalogLoader(root).load()


def test_source_dangling_region_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    payload = _source("sample.source.missing-region")
    payload["region_ids"] = ["missing.region"]
    _append_knowledge(root, "sources", payload)

    with pytest.raises(CatalogValidationError, match="missing region"):
        FileCatalogLoader(root).load()


def test_duplicate_knowledge_id_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    sources_path = root / PACKAGE_ROOT / "knowledge" / "sources.json"
    payload = _read_json(sources_path)
    payload["sources"].append(dict(payload["sources"][0]))
    _write_json(sources_path, payload)

    with pytest.raises(CatalogValidationError, match="duplicate id"):
        FileCatalogLoader(root).load()


def test_evidence_coverage_is_one_hundred_percent():
    catalog = FileCatalogLoader(CATALOG_ROOT).load()
    package = catalog.get_package("shanxi.changzhi")

    coverage = calculate_evidence_coverage(
        package.knowledge_claims,
        package.knowledge_evidence,
        verified_source_ids={
            source.source_id
            for source in package.knowledge_sources
            if source.verification_status is KnowledgeVerificationStatus.VERIFIED
        },
    )

    assert coverage == 1.0


def test_repository_queries_and_round_trip():
    catalog = FileCatalogLoader(CATALOG_ROOT).load()

    source = catalog.get_source("changzhi.source.shanhaijing-ctext")
    claim = catalog.get_claim("changzhi.claim.jingwei-fills-sea")
    evidence = catalog.get_evidence("changzhi.evidence.jingwei-fills-sea")
    assert KnowledgeSource.model_validate(source.model_dump(mode="json")) == source
    assert KnowledgeClaim.model_validate(claim.model_dump(mode="json")) == claim
    assert KnowledgeEvidence.model_validate(evidence.model_dump(mode="json")) == evidence
    assert catalog.list_claims(
        region_id="cn.shanxi.changzhi.changzi",
        theme_id="changzhi.jingwei",
        anchor_id="changzhi.anchor.fajiushan",
        claim_type=KnowledgeClaimType.MYTHOLOGY,
        verification_status=KnowledgeVerificationStatus.VERIFIED,
    )
    assert catalog.list_evidence_for_claim(claim.claim_id) == (evidence,)


@pytest.mark.parametrize(
    ("status", "policy"),
    [
        ("rejected", "allowed"),
        ("disputed", "allowed"),
        ("verified", "forbidden"),
        ("verified", "internal_only"),
    ],
)
def test_rejected_disputed_and_blocked_claims_are_not_production_eligible(
    status, policy
):
    source = KnowledgeSource.model_validate(_source())
    claim = KnowledgeClaim.model_validate(_claim(status=status, policy=policy))
    evidence = KnowledgeEvidence.model_validate(_evidence())
    catalog = InMemoryCatalogRepository(
        regions=(),
        themes=(),
        routes=(),
        anchors=(),
        manifests=(),
        knowledge_sources=(source,),
        knowledge_claims=(claim,),
        knowledge_evidence=(evidence,),
    )

    assert not catalog.is_claim_production_eligible(claim.claim_id)


def test_review_required_sample_is_not_production_eligible():
    catalog = FileCatalogLoader(CATALOG_ROOT).load()

    assert catalog.is_claim_production_eligible("changzhi.claim.jingwei-fills-sea")
    assert not catalog.is_claim_production_eligible(
        "changzhi.claim.fajiushan-yandi-residence"
    )
    assert not catalog.is_claim_production_eligible("missing.claim")


def test_recursive_multi_file_loading_order_is_deterministic(tmp_path):
    root = _catalog_copy(tmp_path)
    knowledge_root = root / PACKAGE_ROOT / "knowledge"
    shutil.rmtree(knowledge_root)
    _write_json(knowledge_root / "z" / "sources.json", {"sources": [_source("z.source")]})
    _write_json(knowledge_root / "a" / "sources.json", {"sources": [_source("a.source")]})

    catalog = FileCatalogLoader(root).load()

    assert [source.source_id for source in catalog.list_sources()] == [
        "a.source",
        "z.source",
    ]


def test_knowledge_file_requires_exactly_one_known_collection(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / PACKAGE_ROOT / "knowledge" / "invalid.json"
    _write_json(path, {"sources": [], "claims": []})

    with pytest.raises(CatalogLoadError, match="exactly one"):
        FileCatalogLoader(root).load()


def test_old_package_without_knowledge_directory_remains_compatible(tmp_path):
    root = _catalog_copy(tmp_path)
    shutil.rmtree(root / PACKAGE_ROOT / "knowledge")

    catalog = FileCatalogLoader(root).load()
    package = catalog.get_package("shanxi.changzhi")

    assert package.knowledge_sources == []
    assert package.knowledge_claims == []
    assert package.knowledge_evidence == []
    assert catalog.list_sources() == ()
    assert catalog.list_claims() == ()


def test_existing_routes_and_mandatory_binding_remain_intact():
    catalog = FileCatalogLoader(CATALOG_ROOT).load()

    assert len(catalog.list_routes()) == 4
    assert all(len(route.mandatory_anchor_ids) == 1 for route in catalog.list_routes())
    assert len(
        catalog.list_verified_bindings_for_anchor("changzhi.anchor.fajiushan")
    ) == 1


def test_catalog_python_contains_no_regional_knowledge_special_cases():
    prohibited_tokens = {"changzhi", "jingwei", "fajiushan"}
    found: list[tuple[str, str]] = []

    for path in sorted((PROJECT_ROOT / "app" / "catalog").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            value = node.value.casefold()
            for token in prohibited_tokens:
                if token in value:
                    found.append((path.name, token))

    assert not found
