from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog.loader import CatalogLoadError, FileCatalogLoader
from app.catalog.models import (
    ExternalPoiBinding,
    PoiProvider,
    PoiVerificationMethod,
    PoiVerificationStatus,
)
from app.catalog.validation import CatalogValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
PACKAGE_ROOT = Path("packages") / "shanxi" / "changzhi"


def _catalog_copy(tmp_path: Path) -> Path:
    target = tmp_path / "catalog"
    shutil.copytree(CATALOG_ROOT, target)
    return target


def _binding(
    binding_id: str,
    *,
    anchor_id: str = "changzhi.anchor.fajiushan",
    external_poi_id: str = "B0001",
    status: str = "candidate",
) -> dict:
    payload = {
        "binding_id": binding_id,
        "anchor_id": anchor_id,
        "provider": "amap",
        "external_poi_id": external_poi_id,
        "external_name": "Provider Candidate",
        "verification_status": status,
        "provider_region_code": "sample-code",
        "provider_address": "Provider supplied address",
        "metadata": {"source": "test"},
    }
    if status == "verified":
        payload.update(
            verification_method="manual_review",
            verified_at="2026-08-21T12:00:00Z",
        )
    return payload


def _write_bindings(root: Path, bindings: list[dict]) -> None:
    path = root / PACKAGE_ROOT / "poi_bindings.json"
    path.write_text(
        json.dumps({"poi_bindings": bindings}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_binding_schema_and_controlled_enums():
    binding = ExternalPoiBinding.model_validate(_binding("binding.sample"))

    assert binding.provider is PoiProvider.AMAP
    assert binding.verification_status is PoiVerificationStatus.CANDIDATE
    assert {item.value for item in PoiProvider} == {
        "amap", "baidu", "tencent", "other", "custom"
    }
    assert {item.value for item in PoiVerificationStatus} == {
        "candidate", "verified", "rejected"
    }
    assert {item.value for item in PoiVerificationMethod} == {
        "manual_review", "provider_exact_id", "official_source", "other"
    }


def test_candidate_without_verification_metadata_is_valid():
    binding = ExternalPoiBinding.model_validate(_binding("binding.candidate"))

    assert binding.verification_method is None
    assert binding.verified_at is None
    assert binding.verification_note is None


def test_verified_binding_requires_verification_method():
    payload = _binding("binding.missing-method", status="verified")
    payload.pop("verification_method")

    with pytest.raises(ValidationError, match="verification_method"):
        ExternalPoiBinding.model_validate(payload)


def test_verified_binding_requires_verified_at():
    payload = _binding("binding.missing-time", status="verified")
    payload.pop("verified_at")

    with pytest.raises(ValidationError, match="verified_at"):
        ExternalPoiBinding.model_validate(payload)


def test_verified_binding_with_manual_review_is_valid():
    binding = ExternalPoiBinding.model_validate(
        _binding("binding.manual-review", status="verified")
    )

    assert binding.verification_method is PoiVerificationMethod.MANUAL_REVIEW
    assert binding.verified_at.isoformat() == "2026-08-21T12:00:00+00:00"


def test_rejected_binding_can_retain_verification_note():
    payload = _binding("binding.rejected-note", status="rejected")
    payload.update(
        verification_method="official_source",
        verification_note="Official source identifies a different place.",
    )

    binding = ExternalPoiBinding.model_validate(payload)

    assert binding.verification_method is PoiVerificationMethod.OFFICIAL_SOURCE
    assert binding.verification_note == "Official source identifies a different place."


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider", "regional_map"),
        ("verification_status", "approved"),
        ("verification_method", "operator_guess"),
        ("external_poi_id", ""),
    ],
)
def test_invalid_binding_fields_are_rejected(field, value):
    payload = _binding("binding.invalid")
    payload[field] = value

    with pytest.raises(ValidationError, match=field):
        ExternalPoiBinding.model_validate(payload)


def test_current_catalog_loads_empty_binding_collection():
    assert (CATALOG_ROOT / PACKAGE_ROOT / "poi_bindings.json").is_file()

    catalog = FileCatalogLoader(CATALOG_ROOT).load()

    assert catalog.list_poi_bindings() == ()
    assert catalog.list_verified_bindings_for_anchor(
        "changzhi.anchor.fajiushan"
    ) == ()


def test_old_catalog_without_binding_file_remains_compatible(tmp_path):
    root = _catalog_copy(tmp_path)
    (root / PACKAGE_ROOT / "poi_bindings.json").unlink()

    catalog = FileCatalogLoader(root).load()

    assert catalog.list_poi_bindings() == ()


def test_missing_anchor_reference_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    _write_bindings(
        root,
        [_binding("binding.missing-anchor", anchor_id="missing.anchor")],
    )

    with pytest.raises(CatalogValidationError, match="missing anchor"):
        FileCatalogLoader(root).load()


def test_duplicate_binding_id_is_rejected(tmp_path):
    root = _catalog_copy(tmp_path)
    _write_bindings(
        root,
        [
            _binding("binding.duplicate", external_poi_id="B0001"),
            _binding("binding.duplicate", external_poi_id="B0002"),
        ],
    )

    with pytest.raises(CatalogValidationError, match="duplicate id binding.duplicate"):
        FileCatalogLoader(root).load()


def test_provider_identity_cannot_bind_conflicting_anchors(tmp_path):
    root = _catalog_copy(tmp_path)
    _write_bindings(
        root,
        [
            _binding("binding.first"),
            _binding(
                "binding.second",
                anchor_id="changzhi.anchor.tiantaishan",
            ),
        ],
    )

    with pytest.raises(CatalogValidationError, match="conflicting anchors"):
        FileCatalogLoader(root).load()


def test_verified_binding_requires_complete_external_identity(tmp_path):
    root = _catalog_copy(tmp_path)
    payload = _binding("binding.incomplete", status="verified")
    payload["external_name"] = ""
    _write_bindings(root, [payload])

    with pytest.raises(CatalogLoadError, match="external_name"):
        FileCatalogLoader(root).load()


def test_repository_queries_all_statuses_but_runtime_query_is_verified_only(tmp_path):
    root = _catalog_copy(tmp_path)
    bindings = [
        _binding("binding.candidate", external_poi_id="B-candidate"),
        _binding(
            "binding.verified",
            external_poi_id="B-verified",
            status="verified",
        ),
        _binding(
            "binding.rejected",
            external_poi_id="B-rejected",
            status="rejected",
        ),
    ]
    _write_bindings(root, bindings)

    catalog = FileCatalogLoader(root).load()

    assert catalog.get_poi_binding("binding.verified").external_poi_id == "B-verified"
    assert len(catalog.list_poi_bindings(provider=PoiProvider.AMAP)) == 3
    assert len(catalog.list_bindings_for_anchor("changzhi.anchor.fajiushan")) == 3
    assert {
        item.binding_id
        for item in catalog.list_verified_bindings_for_anchor(
            "changzhi.anchor.fajiushan"
        )
    } == {"binding.verified"}


def test_loader_repository_and_json_round_trip_verification_provenance(tmp_path):
    root = _catalog_copy(tmp_path)
    payload = _binding("binding.round-trip", status="verified")
    payload["verification_note"] = "Reviewed against the provider record."
    _write_bindings(root, [payload])

    catalog = FileCatalogLoader(root).load()
    binding = catalog.get_poi_binding("binding.round-trip")
    serialized = binding.model_dump(mode="json")
    restored = ExternalPoiBinding.model_validate(serialized)

    assert serialized["verification_method"] == "manual_review"
    assert serialized["verified_at"] == "2026-08-21T12:00:00Z"
    assert restored == binding
