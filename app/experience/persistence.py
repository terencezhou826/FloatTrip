"""Immutable SQLite persistence for formal ExperiencePackage snapshots."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field, ValidationError

from app.catalog.models import CatalogModel
from app.core.database import get_conn
from app.core.package_snapshots import canonical_package_json, package_snapshot_hash
from app.experience.models import (
    ExperiencePackage,
    ExperiencePackageValidationStatus,
)
from app.knowledge.models import CatalogVersionSnapshot


class ExperienceSnapshotError(RuntimeError):
    pass


class ExperiencePackageSnapshot(CatalogModel):
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    package: ExperiencePackage


class ExperiencePackageSnapshotRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def save(self, package: ExperiencePackage) -> ExperiencePackageSnapshot:
        if package.run_id is None:
            raise ExperienceSnapshotError("formal ExperiencePackage requires run_id")
        if package.validation_status is not ExperiencePackageValidationStatus.PASSED:
            raise ExperienceSnapshotError("only passed ExperiencePackage can be persisted")
        serialized = canonical_package_json(package)
        digest = package_snapshot_hash(package)
        created_at = datetime.now(timezone.utc).isoformat()
        with get_conn(self.db_path) as conn:
            _require_story_association(conn, package)
            existing = conn.execute(
                "SELECT snapshot_hash FROM experience_package_snapshots WHERE package_id=?",
                (package.package_id,),
            ).fetchone()
            if existing is not None:
                if existing["snapshot_hash"] != digest:
                    raise ExperienceSnapshotError(
                        "ExperiencePackage snapshot is immutable"
                    )
                return self.load(package.package_id)
            try:
                conn.execute(
                    """INSERT INTO experience_package_snapshots(
                       package_id,run_id,itinerary_id,experience_id,
                       experience_version,story_package_id,story_snapshot_hash,
                       catalog_package_id,schema_version,content_version,
                       snapshot_json,snapshot_hash,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        package.package_id,
                        package.run_id,
                        package.itinerary_id,
                        package.experience_id,
                        package.experience_version,
                        package.story_package_id,
                        package.story_snapshot_hash,
                        package.catalog_version.package_id,
                        package.catalog_version.schema_version,
                        package.catalog_version.content_version,
                        serialized,
                        digest,
                        created_at,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ExperienceSnapshotError(
                    "conflicting ExperiencePackage snapshot association"
                ) from exc
        return self.load(package.package_id)

    def load(
        self,
        package_id: str,
        *,
        expected_run_id: str | None = None,
        expected_itinerary_id: str | None = None,
        expected_story_package_id: str | None = None,
        expected_catalog_version: CatalogVersionSnapshot | None = None,
    ) -> ExperiencePackageSnapshot:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM experience_package_snapshots WHERE package_id=?",
                (package_id,),
            ).fetchone()
        if row is None:
            raise ExperienceSnapshotError(
                f"ExperiencePackage snapshot not found: {package_id}"
            )
        snapshot = _decode_experience_snapshot(row)
        package = snapshot.package
        if expected_run_id is not None and package.run_id != expected_run_id:
            raise ExperienceSnapshotError("ExperiencePackage run_id mismatch")
        if (
            expected_itinerary_id is not None
            and package.itinerary_id != expected_itinerary_id
        ):
            raise ExperienceSnapshotError("ExperiencePackage itinerary_id mismatch")
        if (
            expected_story_package_id is not None
            and package.story_package_id != expected_story_package_id
        ):
            raise ExperienceSnapshotError("ExperiencePackage Story snapshot mismatch")
        if (
            expected_catalog_version is not None
            and package.catalog_version != expected_catalog_version
        ):
            raise ExperienceSnapshotError("ExperiencePackage Catalog version mismatch")
        return snapshot

    def load_for_run(
        self,
        run_id: str,
        itinerary_id: str,
        story_package_id: str,
        *,
        expected_catalog_version: CatalogVersionSnapshot | None = None,
    ) -> ExperiencePackageSnapshot:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                """SELECT package_id FROM experience_package_snapshots
                   WHERE run_id=? AND itinerary_id=? AND story_package_id=?""",
                (run_id, itinerary_id, story_package_id),
            ).fetchone()
        if row is None:
            raise ExperienceSnapshotError(
                "ExperiencePackage snapshot not found for formal run"
            )
        return self.load(
            row["package_id"],
            expected_run_id=run_id,
            expected_itinerary_id=itinerary_id,
            expected_story_package_id=story_package_id,
            expected_catalog_version=expected_catalog_version,
        )


def _require_story_association(
    conn: sqlite3.Connection, package: ExperiencePackage
) -> None:
    row = conn.execute(
        """SELECT run_id,itinerary_id,snapshot_hash,catalog_package_id,
                  schema_version,content_version
           FROM story_package_snapshots WHERE package_id=?""",
        (package.story_package_id,),
    ).fetchone()
    version = package.catalog_version
    if (
        row is None
        or row["run_id"] != package.run_id
        or row["itinerary_id"] != package.itinerary_id
        or row["snapshot_hash"] != package.story_snapshot_hash
        or row["catalog_package_id"] != version.package_id
        or row["schema_version"] != version.schema_version
        or row["content_version"] != version.content_version
    ):
        raise ExperienceSnapshotError(
            "ExperiencePackage Story snapshot association mismatch"
        )


def _decode_experience_snapshot(row) -> ExperiencePackageSnapshot:
    try:
        package = ExperiencePackage.model_validate_json(row["snapshot_json"])
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        raise ExperienceSnapshotError("corrupted ExperiencePackage snapshot") from exc
    digest = package_snapshot_hash(package)
    version = package.catalog_version
    metadata_matches = (
        package.package_id == row["package_id"]
        and package.run_id == row["run_id"]
        and package.itinerary_id == row["itinerary_id"]
        and package.experience_id == row["experience_id"]
        and package.experience_version == row["experience_version"]
        and package.story_package_id == row["story_package_id"]
        and package.story_snapshot_hash == row["story_snapshot_hash"]
        and version.package_id == row["catalog_package_id"]
        and version.schema_version == row["schema_version"]
        and version.content_version == row["content_version"]
    )
    if digest != row["snapshot_hash"] or not metadata_matches:
        raise ExperienceSnapshotError("corrupted ExperiencePackage snapshot")
    return ExperiencePackageSnapshot(
        snapshot_hash=digest,
        created_at=row["created_at"],
        package=package,
    )
