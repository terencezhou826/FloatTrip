from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    AnchorCoordinateIdentity,
    NavigationAccessPoint,
    NavigationAccessType,
    SpatialIdentityType,
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
    }
    assert {item.value for item in SpatialVerificationStatus} == {
        "candidate",
        "verified",
        "rejected",
    }
    assert {item.value for item in SpatialVerificationMethod} == {
        "manual_map_review",
        "official_source",
        "field_survey",
        "authoritative_gis",
        "other",
    }


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

    catalog = FileCatalogLoader(root).load()

    identity = catalog.get_spatial_identity("spatial.identity.sample")
    access = catalog.get_navigation_access_point("spatial.access.sample")
    assert identity.anchor_id == ANCHOR_ID
    assert access.anchor_id == ANCHOR_ID
    assert catalog.list_verified_spatial_identities_for_anchor(ANCHOR_ID) == (
        identity,
    )
    assert catalog.list_verified_navigation_access_points_for_anchor(ANCHOR_ID) == (
        access,
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
