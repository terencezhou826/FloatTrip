from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import shutil

import pytest
from pydantic import ValidationError

from app.catalog.loader import CatalogLoadError, FileCatalogLoader
from app.catalog.models import (
    AvailabilityInfo,
    AvailabilityStatus,
    CommercialRelationship,
    CurrencyCode,
    LocalResource,
    LocalResourceType,
    PriceInfo,
    PriceStatus,
    ResourceContactInfo,
    ResourceEditorialStatus,
    ResourceIdentityProvider,
    ResourceOperationalStatus,
    ResourceSource,
    ResourceSourceType,
    ResourceVerificationStatus,
    is_resource_recommendation_eligible,
)
from app.catalog.validation import CatalogValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
PACKAGE_ROOT = Path("packages") / "shanxi" / "changzhi"
SOURCE_ID = "test.resource-source.provider"
RESOURCE_ID = "test.resource.sample"
PRODUCTION_CLAIM_ID = "changzhi.claim.fajiushan-zhemu"
INTERNAL_CLAIM_ID = "changzhi.claim.fajiushan-yandi-residence"
NOW = "2026-08-22T10:00:00Z"


def _catalog_copy(tmp_path: Path) -> Path:
    target = tmp_path / "catalog"
    shutil.copytree(CATALOG_ROOT, target)
    return target


def _source(
    source_id: str = SOURCE_ID,
    *,
    verified: bool = True,
) -> dict:
    return {
        "source_id": source_id,
        "source_type": "provider",
        "external_source_id": "TEST-EXTERNAL-SOURCE",
        "provider": "amap",
        "retrieved_at": NOW,
        "verified_at": NOW if verified else None,
        "metadata": {"fixture": True},
    }


def _resource(
    resource_id: str = RESOURCE_ID,
    *,
    resource_type: str = "restaurant",
    verification_status: str = "verified",
    operational_status: str = "open",
    relationship: str = "none",
    provider_id: str | None = "TEST-POI-ID",
) -> dict:
    payload = {
        "resource_id": resource_id,
        "package_id": "shanxi.changzhi",
        "resource_type": resource_type,
        "name": "Synthetic Resource Fixture",
        "region_ids": ["cn.shanxi.changzhi.changzi"],
        "anchor_ids": ["changzhi.anchor.fajiushan"],
        "provider_bindings": [],
        "description": "Test-only marketing description.",
        "verification_status": verification_status,
        "operational_status": operational_status,
        "source_refs": [SOURCE_ID],
        "price_info": {"price_status": "unknown"},
        "availability_info": {"status": "unknown"},
        "commercial_relationship": relationship,
        "editorial_status": "approved",
        "disclosure_required": relationship in {"partner", "sponsored"},
        "disclosure_text": (
            "Test fixture commercial relationship disclosure."
            if relationship in {"partner", "sponsored"}
            else None
        ),
        "last_verified_at": NOW if verification_status == "verified" else None,
        "metadata": {"fixture": True},
    }
    if provider_id is not None:
        payload["provider_bindings"] = [
            {
                "provider": "amap",
                "external_id": provider_id,
                "external_name": "Synthetic Provider Fixture",
            }
        ]
    return payload


def _write_resources(
    root: Path,
    *,
    sources: list[dict] | None = None,
    resources: list[dict] | None = None,
) -> None:
    directory = root / PACKAGE_ROOT / "resources"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "sources.json").write_text(
        json.dumps({"sources": sources or []}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (directory / "resources.json").write_text(
        json.dumps({"resources": resources or []}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def test_local_resource_type_is_controlled():
    assert {item.value for item in LocalResourceType} == {
        "restaurant",
        "lodging",
        "local_product",
        "agricultural_product",
        "cultural_product",
        "heritage_experience",
        "paid_experience",
        "tour_service",
        "transport_service",
        "ticket",
        "event",
        "other",
    }


def test_resource_identity_provider_is_provider_neutral():
    assert {item.value for item in ResourceIdentityProvider} >= {
        "amap",
        "baidu",
        "tencent",
        "official_catalog",
        "internal",
        "custom",
    }


def test_resource_verification_status_is_controlled():
    assert {item.value for item in ResourceVerificationStatus} == {
        "candidate",
        "review_required",
        "verified",
        "rejected",
        "expired",
    }


def test_operational_status_is_separate_and_controlled():
    assert {item.value for item in ResourceOperationalStatus} == {
        "unknown",
        "open",
        "temporarily_closed",
        "seasonal",
        "appointment_required",
        "inactive",
    }


def test_price_and_availability_statuses_are_controlled():
    assert {item.value for item in PriceStatus} == {
        "unknown", "free", "fixed", "range", "per_person", "from_price"
    }
    assert {item.value for item in AvailabilityStatus} == {
        "unknown", "available", "seasonal", "appointment_required", "sold_out", "inactive"
    }
    assert {item.value for item in CurrencyCode} == {"CNY"}


def test_commercial_relationship_is_controlled():
    assert {item.value for item in CommercialRelationship} == {
        "none", "public_resource", "partner", "sponsored", "unknown"
    }


def test_candidate_resource_schema_is_valid():
    resource = LocalResource.model_validate(
        _resource(verification_status="candidate")
    )
    assert resource.verification_status is ResourceVerificationStatus.CANDIDATE


def test_verified_resource_requires_provenance_refs():
    payload = _resource()
    payload["source_refs"] = []
    with pytest.raises(ValidationError, match="provenance"):
        LocalResource.model_validate(payload)


def test_verified_resource_requires_last_verified_at():
    payload = _resource()
    payload["last_verified_at"] = None
    with pytest.raises(ValidationError, match="last_verified_at"):
        LocalResource.model_validate(payload)


def test_name_only_merchant_identity_is_not_complete():
    resource = LocalResource.model_validate(_resource(provider_id=None))
    assert resource.has_complete_identity is False
    assert is_resource_recommendation_eligible(
        resource, as_of=date(2026, 8, 22)
    ) is False


@pytest.mark.parametrize(
    "resource_type",
    ["local_product", "agricultural_product", "cultural_product"],
)
def test_sourced_internal_product_has_stable_identity(resource_type):
    resource = LocalResource.model_validate(
        _resource(resource_type=resource_type, provider_id=None)
    )
    assert resource.has_complete_identity is True


def test_duplicate_provider_identity_in_one_resource_is_rejected():
    payload = _resource()
    payload["provider_bindings"].append(deepcopy(payload["provider_bindings"][0]))
    with pytest.raises(ValidationError, match="duplicate identities"):
        LocalResource.model_validate(payload)


def test_resource_source_requires_external_identity_or_reference():
    payload = _source()
    payload.pop("external_source_id")
    with pytest.raises(ValidationError, match="resource source requires"):
        ResourceSource.model_validate(payload)


def test_provider_source_requires_provider():
    payload = _source()
    payload["provider"] = None
    with pytest.raises(ValidationError, match="requires provider"):
        ResourceSource.model_validate(payload)


def test_unknown_price_is_valid_and_does_not_claim_amount():
    price = PriceInfo()
    assert price.price_status is PriceStatus.UNKNOWN
    assert price.amount is None


def test_unknown_price_cannot_carry_amount():
    with pytest.raises(ValidationError, match="unknown price"):
        PriceInfo(price_status="unknown", amount="10")


def test_fixed_price_requires_source_and_timestamp():
    with pytest.raises(ValidationError, match="source_ref and updated_at"):
        PriceInfo(price_status="fixed", currency="CNY", amount="10")


def test_fixed_price_is_structured():
    price = PriceInfo(
        price_status="fixed",
        currency="CNY",
        amount="10.50",
        source_ref=SOURCE_ID,
        updated_at=NOW,
    )
    assert str(price.amount) == "10.50"


def test_range_price_requires_both_bounds():
    with pytest.raises(ValidationError, match="requires min_amount and max_amount"):
        PriceInfo(
            price_status="range",
            currency="CNY",
            min_amount="10",
            source_ref=SOURCE_ID,
            updated_at=NOW,
        )


def test_range_price_rejects_inverted_bounds():
    with pytest.raises(ValidationError, match="must not exceed"):
        PriceInfo(
            price_status="range",
            currency="CNY",
            min_amount="20",
            max_amount="10",
            source_ref=SOURCE_ID,
            updated_at=NOW,
        )


@pytest.mark.parametrize("status", ["per_person", "from_price"])
def test_amount_price_variants_are_valid(status):
    price = PriceInfo(
        price_status=status,
        currency="CNY",
        amount="20",
        unit="person" if status == "per_person" else None,
        source_ref=SOURCE_ID,
        updated_at=NOW,
    )
    assert price.amount == 20


def test_free_price_requires_source_but_no_amount():
    price = PriceInfo(
        price_status="free",
        currency="CNY",
        source_ref=SOURCE_ID,
        updated_at=NOW,
    )
    assert price.amount is None


def test_invalid_currency_is_rejected():
    with pytest.raises(ValidationError, match="currency"):
        PriceInfo(
            price_status="fixed",
            currency="RMB",
            amount="10",
            source_ref=SOURCE_ID,
            updated_at=NOW,
        )


def test_price_freshness_is_explicit_and_deterministic():
    price = PriceInfo(
        price_status="fixed",
        currency="CNY",
        amount="10",
        source_ref=SOURCE_ID,
        updated_at="2026-07-01T00:00:00Z",
    )
    as_of = datetime(2026, 8, 22, tzinfo=timezone.utc)
    assert price.is_stale(as_of=as_of, max_age=timedelta(days=30)) is True
    assert price.is_stale(as_of=as_of, max_age=timedelta(days=60)) is False


def test_known_availability_requires_own_source_and_timestamp():
    with pytest.raises(ValidationError, match="known availability"):
        AvailabilityInfo(status="available")


def test_known_availability_is_structured():
    availability = AvailabilityInfo(
        status="seasonal", source_ref=SOURCE_ID, updated_at=NOW
    )
    assert availability.status is AvailabilityStatus.SEASONAL


def test_empty_contact_info_is_rejected():
    with pytest.raises(ValidationError, match="phone or email"):
        ResourceContactInfo()


def test_invalid_validity_period_is_rejected():
    payload = _resource()
    payload.update(valid_from="2026-09-01", valid_to="2026-08-01")
    with pytest.raises(ValidationError, match="valid_from"):
        LocalResource.model_validate(payload)


@pytest.mark.parametrize("relationship", ["partner", "sponsored"])
def test_commercial_relationship_requires_disclosure(relationship):
    payload = _resource(relationship=relationship)
    payload["disclosure_required"] = False
    payload["disclosure_text"] = None
    with pytest.raises(ValidationError, match="commercial disclosure"):
        LocalResource.model_validate(payload)


def test_non_commercial_resource_does_not_require_disclosure():
    resource = LocalResource.model_validate(_resource(relationship="none"))
    assert resource.disclosure_required is False


def test_verified_resource_is_eligible_when_all_truth_gates_pass():
    resource = LocalResource.model_validate(_resource())
    assert is_resource_recommendation_eligible(
        resource, as_of=date(2026, 8, 22)
    ) is True


@pytest.mark.parametrize("status", ["candidate", "review_required", "rejected", "expired"])
def test_non_verified_resource_is_not_eligible(status):
    resource = LocalResource.model_validate(
        _resource(verification_status=status)
    )
    assert is_resource_recommendation_eligible(
        resource, as_of=date(2026, 8, 22)
    ) is False


def test_inactive_resource_is_not_eligible():
    resource = LocalResource.model_validate(
        _resource(operational_status="inactive")
    )
    assert is_resource_recommendation_eligible(
        resource, as_of=date(2026, 8, 22)
    ) is False


def test_resource_outside_validity_window_is_not_eligible():
    payload = _resource()
    payload["valid_to"] = "2026-08-21"
    resource = LocalResource.model_validate(payload)
    assert is_resource_recommendation_eligible(
        resource, as_of=date(2026, 8, 22)
    ) is False


def test_commercial_relationship_does_not_change_truth_eligibility():
    results = []
    for relationship in CommercialRelationship:
        resource = LocalResource.model_validate(
            _resource(relationship=relationship.value)
        )
        results.append(
            is_resource_recommendation_eligible(
                resource, as_of=date(2026, 8, 22)
            )
        )
    assert results == [True] * len(CommercialRelationship)


def test_current_catalog_loads_empty_resource_collections():
    catalog = FileCatalogLoader(CATALOG_ROOT).load()
    assert catalog.list_resources() == ()
    assert catalog.get_resource(RESOURCE_ID) is None


def test_legacy_package_without_resources_directory_is_compatible(tmp_path):
    root = _catalog_copy(tmp_path)
    shutil.rmtree(root / PACKAGE_ROOT / "resources")
    catalog = FileCatalogLoader(root).load()
    assert catalog.list_resources() == ()


def test_resource_loader_repository_round_trip(tmp_path):
    root = _catalog_copy(tmp_path)
    _write_resources(root, sources=[_source()], resources=[_resource()])
    catalog = FileCatalogLoader(root).load()
    resource = catalog.get_resource(RESOURCE_ID)
    assert resource is not None
    assert LocalResource.model_validate(resource.model_dump(mode="json")) == resource
    assert catalog.is_resource_recommendation_eligible(
        RESOURCE_ID, as_of=date(2026, 8, 22)
    ) is True


def test_repository_filters_resources(tmp_path):
    root = _catalog_copy(tmp_path)
    second = _resource(
        "test.resource.product",
        resource_type="local_product",
        verification_status="candidate",
        provider_id=None,
    )
    _write_resources(root, sources=[_source()], resources=[_resource(), second])
    catalog = FileCatalogLoader(root).load()
    assert len(catalog.list_resources(resource_type=LocalResourceType.RESTAURANT)) == 1
    assert len(catalog.list_resources(region_id="cn.shanxi.changzhi.changzi")) == 2
    assert len(catalog.list_resources(anchor_id="changzhi.anchor.fajiushan")) == 2
    assert len(
        catalog.list_resources(
            verification_status=ResourceVerificationStatus.CANDIDATE
        )
    ) == 1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("region_ids", ["missing.region"], "missing region"),
        ("anchor_ids", ["missing.anchor"], "missing anchor"),
        ("source_refs", ["missing.source"], "missing provenance source"),
    ],
)
def test_resource_references_must_exist(tmp_path, field, value, message):
    root = _catalog_copy(tmp_path)
    resource = _resource()
    resource[field] = value
    _write_resources(root, sources=[_source()], resources=[resource])
    with pytest.raises(CatalogValidationError, match=message):
        FileCatalogLoader(root).load()


def test_verified_resource_requires_verified_provenance(tmp_path):
    root = _catalog_copy(tmp_path)
    _write_resources(root, sources=[_source(verified=False)], resources=[_resource()])
    with pytest.raises(CatalogValidationError, match="no verified provenance"):
        FileCatalogLoader(root).load()


def test_duplicate_resource_id_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    _write_resources(
        root,
        sources=[_source()],
        resources=[_resource(), _resource(provider_id="SECOND-ID")],
    )
    with pytest.raises(CatalogValidationError, match="duplicate id"):
        FileCatalogLoader(root).load()


def test_duplicate_resource_source_id_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    _write_resources(
        root,
        sources=[_source(), _source()],
        resources=[_resource()],
    )
    with pytest.raises(CatalogValidationError, match="duplicate id"):
        FileCatalogLoader(root).load()


def test_provider_identity_cannot_bind_conflicting_resources(tmp_path):
    root = _catalog_copy(tmp_path)
    _write_resources(
        root,
        sources=[_source()],
        resources=[_resource(), _resource("test.resource.second")],
    )
    with pytest.raises(CatalogValidationError, match="conflicting resources"):
        FileCatalogLoader(root).load()


def test_price_source_must_exist_separately(tmp_path):
    root = _catalog_copy(tmp_path)
    resource = _resource()
    resource["price_info"] = {
        "price_status": "fixed",
        "currency": "CNY",
        "amount": "10",
        "source_ref": "missing.price-source",
        "updated_at": NOW,
    }
    _write_resources(root, sources=[_source()], resources=[resource])
    with pytest.raises(CatalogValidationError, match="missing freshness source"):
        FileCatalogLoader(root).load()


def test_resource_package_id_must_match_owner(tmp_path):
    root = _catalog_copy(tmp_path)
    resource = _resource()
    resource["package_id"] = "other.package"
    _write_resources(root, sources=[_source()], resources=[resource])
    with pytest.raises(CatalogValidationError, match="does not match owning package"):
        FileCatalogLoader(root).load()


def test_product_cultural_claim_must_exist(tmp_path):
    root = _catalog_copy(tmp_path)
    resource = _resource(resource_type="cultural_product", provider_id=None)
    resource["cultural_claim_ids"] = ["missing.claim"]
    _write_resources(root, sources=[_source()], resources=[resource])
    with pytest.raises(CatalogValidationError, match="missing cultural Claim"):
        FileCatalogLoader(root).load()


def test_product_cultural_claim_must_be_production_eligible(tmp_path):
    root = _catalog_copy(tmp_path)
    resource = _resource(resource_type="cultural_product", provider_id=None)
    resource["cultural_claim_ids"] = [INTERNAL_CLAIM_ID]
    _write_resources(root, sources=[_source()], resources=[resource])
    with pytest.raises(CatalogValidationError, match="not production eligible"):
        FileCatalogLoader(root).load()


def test_product_can_reference_production_eligible_claim(tmp_path):
    root = _catalog_copy(tmp_path)
    resource = _resource(resource_type="cultural_product", provider_id=None)
    resource["cultural_claim_ids"] = [PRODUCTION_CLAIM_ID]
    _write_resources(root, sources=[_source()], resources=[resource])
    catalog = FileCatalogLoader(root).load()
    assert catalog.get_resource(RESOURCE_ID).cultural_claim_ids == [PRODUCTION_CLAIM_ID]


def test_resource_loading_does_not_mutate_other_domains(tmp_path):
    baseline = FileCatalogLoader(CATALOG_ROOT).load()
    knowledge_before = tuple(item.model_dump_json() for item in baseline.list_claims())
    stories_before = tuple(item.model_dump_json() for item in baseline.list_stories())
    experiences_before = tuple(
        item.model_dump_json() for item in baseline.list_experiences()
    )

    root = _catalog_copy(tmp_path)
    _write_resources(root, sources=[_source()], resources=[_resource()])
    loaded = FileCatalogLoader(root).load()

    assert tuple(item.model_dump_json() for item in loaded.list_claims()) == knowledge_before
    assert tuple(item.model_dump_json() for item in loaded.list_stories()) == stories_before
    assert tuple(
        item.model_dump_json() for item in loaded.list_experiences()
    ) == experiences_before


def test_resource_collection_requires_exactly_one_known_key(tmp_path):
    root = _catalog_copy(tmp_path)
    path = root / PACKAGE_ROOT / "resources" / "resources.json"
    path.write_text('{"resources": [], "sources": []}\n', encoding="utf-8")
    with pytest.raises(CatalogLoadError, match="exactly one"):
        FileCatalogLoader(root).load()
