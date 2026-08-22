"""Immutable SQLite persistence for formal StoryPackage snapshots."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field, ValidationError

from app.catalog.models import CatalogModel
from app.core.database import get_conn
from app.core.package_snapshots import canonical_package_json, package_snapshot_hash
from app.knowledge.models import CatalogVersionSnapshot
from app.story.models import StoryPackage, StoryPackageValidationStatus


class StorySnapshotError(RuntimeError):
    pass


class StoryPackageSnapshot(CatalogModel):
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    package: StoryPackage


class StoryPackageSnapshotRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def save(self, package: StoryPackage) -> StoryPackageSnapshot:
        if package.run_id is None:
            raise StorySnapshotError("formal StoryPackage requires run_id")
        if package.validation_status is not StoryPackageValidationStatus.PASSED:
            raise StorySnapshotError("only passed StoryPackage can be persisted")
        serialized = canonical_package_json(package)
        digest = package_snapshot_hash(package)
        created_at = datetime.now(timezone.utc).isoformat()
        with get_conn(self.db_path) as conn:
            _require_run_itinerary(conn, package.run_id, package.itinerary_id)
            existing = conn.execute(
                "SELECT snapshot_hash FROM story_package_snapshots WHERE package_id=?",
                (package.package_id,),
            ).fetchone()
            if existing is not None:
                if existing["snapshot_hash"] != digest:
                    raise StorySnapshotError("StoryPackage snapshot is immutable")
                return self.load(package.package_id)
            try:
                conn.execute(
                    """INSERT INTO story_package_snapshots(
                       package_id,run_id,itinerary_id,story_id,story_version,
                       catalog_package_id,schema_version,content_version,
                       snapshot_json,snapshot_hash,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        package.package_id,
                        package.run_id,
                        package.itinerary_id,
                        package.story_id,
                        package.story_version,
                        package.catalog_version.package_id,
                        package.catalog_version.schema_version,
                        package.catalog_version.content_version,
                        serialized,
                        digest,
                        created_at,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise StorySnapshotError(
                    "conflicting StoryPackage snapshot association"
                ) from exc
        return self.load(package.package_id)

    def load(
        self,
        package_id: str,
        *,
        expected_run_id: str | None = None,
        expected_itinerary_id: str | None = None,
        expected_catalog_version: CatalogVersionSnapshot | None = None,
    ) -> StoryPackageSnapshot:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM story_package_snapshots WHERE package_id=?",
                (package_id,),
            ).fetchone()
        if row is None:
            raise StorySnapshotError(f"StoryPackage snapshot not found: {package_id}")
        snapshot = _decode_story_snapshot(row)
        package = snapshot.package
        if expected_run_id is not None and package.run_id != expected_run_id:
            raise StorySnapshotError("StoryPackage run_id mismatch")
        if (
            expected_itinerary_id is not None
            and package.itinerary_id != expected_itinerary_id
        ):
            raise StorySnapshotError("StoryPackage itinerary_id mismatch")
        if (
            expected_catalog_version is not None
            and package.catalog_version != expected_catalog_version
        ):
            raise StorySnapshotError("StoryPackage Catalog version mismatch")
        return snapshot

    def load_for_run(
        self,
        run_id: str,
        itinerary_id: str,
        story_id: str,
        *,
        expected_catalog_version: CatalogVersionSnapshot | None = None,
    ) -> StoryPackageSnapshot:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                """SELECT package_id FROM story_package_snapshots
                   WHERE run_id=? AND itinerary_id=? AND story_id=?""",
                (run_id, itinerary_id, story_id),
            ).fetchone()
        if row is None:
            raise StorySnapshotError("StoryPackage snapshot not found for formal run")
        return self.load(
            row["package_id"],
            expected_run_id=run_id,
            expected_itinerary_id=itinerary_id,
            expected_catalog_version=expected_catalog_version,
        )


def _require_run_itinerary(
    conn: sqlite3.Connection, run_id: str, itinerary_id: str
) -> None:
    row = conn.execute(
        "SELECT status,result_itinerary_id FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    if (
        row is None
        or row["status"] != "succeeded"
        or row["result_itinerary_id"] != itinerary_id
    ):
        raise StorySnapshotError("StoryPackage Run/itinerary association mismatch")
    if conn.execute(
        "SELECT 1 FROM itineraries WHERE id=?", (itinerary_id,)
    ).fetchone() is None:
        raise StorySnapshotError("StoryPackage itinerary not found")


def _decode_story_snapshot(row) -> StoryPackageSnapshot:
    try:
        package = StoryPackage.model_validate_json(row["snapshot_json"])
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        raise StorySnapshotError("corrupted StoryPackage snapshot") from exc
    digest = package_snapshot_hash(package)
    version = package.catalog_version
    metadata_matches = (
        package.package_id == row["package_id"]
        and package.run_id == row["run_id"]
        and package.itinerary_id == row["itinerary_id"]
        and package.story_id == row["story_id"]
        and package.story_version == row["story_version"]
        and version.package_id == row["catalog_package_id"]
        and version.schema_version == row["schema_version"]
        and version.content_version == row["content_version"]
    )
    if digest != row["snapshot_hash"] or not metadata_matches:
        raise StorySnapshotError("corrupted StoryPackage snapshot")
    return StoryPackageSnapshot(
        snapshot_hash=digest,
        created_at=row["created_at"],
        package=package,
    )
