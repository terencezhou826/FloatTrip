from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    AnchorLocalityIdentity,
    AnchorCoordinateIdentity,
    NavigationAccessPoint,
    NavigationAccessType,
    LocalityType,
    SpatialIdentityType,
    SpatialResolutionLevel,
    SpatialVerificationMethod,
    SpatialVerificationStatus,
)
from app.catalog.validation import CatalogValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
PACKAGE_ROOT = Path("packages") / "shanxi" / "changzhi"
ANCHOR_ID = "changzhi.anchor.fajiushan"


def _catalog_copy(tmp_path: Path) -> Path:
    target = tmp_path / "catalog"
    shutil.copytree(CATALOG_ROOT, target)
    return target


def _provenance() -> dict:
    return {
        "provenance_id": "spatial.provenance.sample",
        "verification_method": "manual_map_review",
        "verified_at": "2026-08-22T10:00:00+08:00",
        "source_reference": "internal-review-record:sample",
        "audit_reference": "content-ops-review:sample",
        "verification_note": "Coordinate reviewed against the referenced map record.",
    }


def _coordinate(
    *,
    identity_id: str = "spatial.identity.sample",
    anchor_id: str = ANCHOR_ID,
    status: str = "verified",
) -> dict:
    payload = {
        "spatial_identity_id": identity_id,
        "anchor_id": anchor_id,
        "spatial_identity_type": "verified_coordinate",
        "location": {"longitude": 112.0, "latitude": 36.0},
        "verification_status": status,
    }
    if status == "verified":
        payload.update(
            provenance=_provenance(),
            accuracy="approximate",
            confidence="high",
        )
    return payload


def _access_point(
    *,
    access_point_id: str = "spatial.access.sample",
    anchor_id: str = ANCHOR_ID,
    status: str = "verified",
) -> dict:
    payload = {
        "access_point_id": access_point_id,
        "anchor_id": anchor_id,
        "spatial_identity_type": "navigation_access_point",
        "name": "Sample access point",
        "location": {"longitude": 112.01, "latitude": 36.01},
        "access_type": "trailhead",
        "verification_status": status,
        "note": "Navigation only; does not redefine the cultural Anchor.",
    }
    if status == "verified":
        payload.update(
            provenance=_provenance(),
            accuracy="precise",
            confidence="high",
        )
    return payload


def _locality(
    *,
    locality_identity_id: str = "spatial.locality.sample",
    anchor_id: str = ANCHOR_ID,
    region_id: str = "cn.shanxi.changzhi.changzi",
    status: str = "verified",
    evidence_id: str = "changzhi.evidence.changzi-official-birthplace",
) -> dict:
    payload = {
        "locality_identity_id": locality_identity_id,
        "anchor_id": anchor_id,
        "region_id": region_id,
        "locality_name": "Sample village",
        "locality_type": "village",
        "provider": "amap",
        "external_id": None,
        "location": {"longitude": 112.02, "latitude": 36.02},
        "verification_status": status,
    }
    if status == "verified":
        payload.update(
            verification_method="provider_geocode",
            verified_at="2026-08-23T00:00:00+08:00",
            provenance=[
                {
                    **_provenance(),
                    "verification_method": "provider_geocode",
                    "audit_reference": None,
                }
            ],
            source_reference="https://example.test/official-locality-source",
            administrative_path=[
                "cn.shanxi",
                "cn.shanxi.changzhi",
                region_id,
            ],
            accuracy="area_centroid",
            confidence="high",
            verification_note="Verified locality relationship, not exact Anchor location.",
            relationship_evidence_ids=[evidence_id],
            navigation_reference={
                "provider": "amap",
                "external_poi_id": "TEST-LOCALITY-REFERENCE",
                "name": "Sample village committee",
                "location": {"longitude": 112.021, "latitude": 36.021},
                "provider_region_code": "140428",
                "address": "Sample public address",
                "publicly_navigable": True,
                "safety_reviewed": True,
                "note": "Navigation reference only.",
            },
            disclosure_text="Navigation reaches a locality reference, not the exact cultural place.",
            safety_constraints=[
                "public_reference_only",
                "follow_public_guidance",
                "no_private_land",
            ],
            metadata={},
        )
    return payload


def _write_collection(root: Path, filename: str, key: str, values: list[dict]) -> None:
    (root / PACKAGE_ROOT / filename).write_text(
        json.dumps({key: values}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_spatial_identity_controlled_enums():
    assert {item.value for item in SpatialIdentityType} == {
        "provider_poi",
        "verified_coordinate",
        "navigation_access_point",
        "verified_locality",
        "verified_township",
        "administrative_area",
    }
    assert {item.value for item in SpatialVerificationStatus} == {
        "candidate",
        "verified",
        "rejected",
    }
    assert {item.value for item in SpatialVerificationMethod} == {
        "manual_map_review",
        "provider_geocode",
        "provider_exact_id",
        "official_source",
        "field_survey",
        "authoritative_gis",
        "other",
    }
    assert {item.value for item in SpatialResolutionLevel} == {
        "exact_provider_poi",
        "verified_coordinate",
        "verified_access_point",
        "verified_locality",
        "verified_township",
        "administrative_area",
    }
    assert LocalityType.VILLAGE.value == "village"


def test_verified_coordinate_is_runtime_eligible_with_complete_provenance():
    identity = AnchorCoordinateIdentity.model_validate(_coordinate())

    assert identity.is_runtime_eligible is True
    assert identity.spatial_identity_type is SpatialIdentityType.VERIFIED_COORDINATE
    assert identity.provenance.verification_method is (
        SpatialVerificationMethod.MANUAL_MAP_REVIEW
    )


def test_unverified_coordinate_is_not_runtime_eligible():
    identity = AnchorCoordinateIdentity.model_validate(_coordinate(status="candidate"))

    assert identity.is_runtime_eligible is False


@pytest.mark.parametrize("field", ["provenance", "accuracy", "confidence"])
def test_verified_coordinate_requires_complete_provenance(field):
    payload = _coordinate()
    payload.pop(field)

    with pytest.raises(ValidationError, match=field):
        AnchorCoordinateIdentity.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("longitude", 181), ("longitude", -181), ("latitude", 91), ("latitude", -91)],
)
def test_invalid_coordinate_is_rejected(field, value):
    payload = _coordinate()
    payload["location"][field] = value

    with pytest.raises(ValidationError, match=field):
        AnchorCoordinateIdentity.model_validate(payload)


def test_manual_review_requires_non_sensitive_audit_reference():
    payload = _coordinate()
    payload["provenance"].pop("audit_reference")

    with pytest.raises(ValidationError, match="audit_reference"):
        AnchorCoordinateIdentity.model_validate(payload)


def test_verified_navigation_access_point_is_runtime_eligible():
    access = NavigationAccessPoint.model_validate(_access_point())

    assert access.is_runtime_eligible is True
    assert access.access_type is NavigationAccessType.TRAILHEAD
    assert access.anchor_id == ANCHOR_ID
    assert access.name != "发鸠山"


def test_old_package_without_spatial_collections_loads_empty():
    catalog = FileCatalogLoader(CATALOG_ROOT).load()

    assert catalog.list_spatial_identities_for_anchor(ANCHOR_ID) == ()
    assert catalog.list_navigation_access_points_for_anchor(ANCHOR_ID) == ()
    assert catalog.list_locality_identities_for_anchor(ANCHOR_ID) == ()


def test_verified_locality_schema_and_resolution_level():
    locality = AnchorLocalityIdentity.model_validate(_locality())

    assert locality.is_runtime_eligible is True
    assert locality.resolution_level is SpatialResolutionLevel.VERIFIED_LOCALITY
    assert locality.navigation_reference.name != "发鸠山"


def test_unverified_locality_is_not_runtime_eligible():
    locality = AnchorLocalityIdentity.model_validate(_locality(status="candidate"))

    assert locality.is_runtime_eligible is False


def test_loader_repository_round_trip(tmp_path):
    root = _catalog_copy(tmp_path)
    _write_collection(
        root,
        "spatial_identities.json",
        "spatial_identities",
        [_coordinate()],
    )
    _write_collection(
        root,
        "navigation_access_points.json",
        "navigation_access_points",
        [_access_point()],
    )
    _write_collection(
        root,
        "anchor_localities.json",
        "locality_identities",
        [_locality()],
    )

    catalog = FileCatalogLoader(root).load()

    identity = catalog.get_spatial_identity("spatial.identity.sample")
    access = catalog.get_navigation_access_point("spatial.access.sample")
    locality = catalog.get_locality_identity("spatial.locality.sample")
    assert identity.anchor_id == ANCHOR_ID
    assert access.anchor_id == ANCHOR_ID
    assert catalog.list_verified_spatial_identities_for_anchor(ANCHOR_ID) == (
        identity,
    )
    assert catalog.list_verified_navigation_access_points_for_anchor(ANCHOR_ID) == (
        access,
    )
    assert catalog.list_verified_locality_identities_for_anchor(ANCHOR_ID) == (
        locality,
    )


@pytest.mark.parametrize(
    ("filename", "key", "payload", "message"),
    [
        (
            "spatial_identities.json",
            "spatial_identities",
            _coordinate(anchor_id="missing.anchor"),
            "spatial identity.*missing anchor",
        ),
        (
            "navigation_access_points.json",
            "navigation_access_points",
            _access_point(anchor_id="missing.anchor"),
            "navigation access point.*missing anchor",
        ),
        (
            "anchor_localities.json",
            "locality_identities",
            _locality(anchor_id="missing.anchor"),
            "locality identity.*missing anchor",
        ),
    ],
)
def test_spatial_collections_reject_missing_anchor(
    tmp_path, filename, key, payload, message
):
    root = _catalog_copy(tmp_path)
    _write_collection(root, filename, key, [payload])

    with pytest.raises(CatalogValidationError, match=message):
        FileCatalogLoader(root).load()


def test_spatial_identity_ids_are_globally_unique(tmp_path):
    root = _catalog_copy(tmp_path)
    _write_collection(
        root,
        "spatial_identities.json",
        "spatial_identities",
        [_coordinate(), _coordinate()],
    )

    with pytest.raises(CatalogValidationError, match="duplicate id spatial.identity.sample"):
        FileCatalogLoader(root).load()


def test_locality_requires_verified_relationship_evidence(tmp_path):
    root = _catalog_copy(tmp_path)
    _write_collection(
        root,
        "anchor_localities.json",
        "locality_identities",
        [_locality(evidence_id="missing.evidence")],
    )

    with pytest.raises(CatalogValidationError, match="missing relationship evidence"):
        FileCatalogLoader(root).load()


def test_same_locality_with_wrong_anchor_evidence_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    _write_collection(
        root,
        "anchor_localities.json",
        "locality_identities",
        [
            _locality(
                anchor_id="changzhi.anchor.tiantaishan",
                region_id="cn.shanxi.changzhi.shangdang",
                evidence_id="changzhi.evidence.changzi-official-birthplace",
            )
        ],
    )

    with pytest.raises(CatalogValidationError, match="does not support its anchor"):
        FileCatalogLoader(root).load()
