"""Immutable SQLite persistence for formal LocalResourcePackage snapshots."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import Field, ValidationError

from app.catalog.models import CatalogModel
from app.core.database import get_conn
from app.resources.package import (
    LocalResourcePackage,
    local_resource_package_hash,
)


class LocalResourceSnapshotError(RuntimeError):
    pass


class LocalResourcePackageSnapshot(CatalogModel):
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    package: LocalResourcePackage


class LocalResourcePackageSnapshotRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def save(
        self, package: LocalResourcePackage
    ) -> LocalResourcePackageSnapshot:
        digest = local_resource_package_hash(package)
        if digest != package.snapshot_hash:
            raise LocalResourceSnapshotError("LocalResourcePackage hash mismatch")
        serialized = json.dumps(
            package.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        with get_conn(self.db_path) as conn:
            _require_upstream_associations(conn, package)
            existing = conn.execute(
                "SELECT snapshot_hash FROM local_resource_package_snapshots "
                "WHERE resource_package_id=?",
                (package.resource_package_id,),
            ).fetchone()
            if existing is not None:
                if existing["snapshot_hash"] != digest:
                    raise LocalResourceSnapshotError(
                        "LocalResourcePackage snapshot is immutable"
                    )
                return self.load(package.resource_package_id)
            try:
                conn.execute(
                    """INSERT INTO local_resource_package_snapshots(
                       resource_package_id,run_id,itinerary_id,story_package_id,
                       story_snapshot_hash,experience_package_id,
                       experience_snapshot_hash,catalog_package_id,schema_version,
                       content_version,snapshot_json,snapshot_hash,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        package.resource_package_id,
                        package.run_id,
                        package.itinerary_id,
                        package.story_package_id,
                        package.story_snapshot_hash,
                        package.experience_package_id,
                        package.experience_snapshot_hash,
                        package.package_id,
                        package.schema_version,
                        package.content_version,
                        serialized,
                        digest,
                        package.created_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise LocalResourceSnapshotError(
                    "conflicting LocalResourcePackage snapshot association"
                ) from exc
        return self.load(package.resource_package_id)

    def load(
        self,
        resource_package_id: str,
        *,
        expected_run_id: str | None = None,
        expected_itinerary_id: str | None = None,
        expected_story_package_id: str | None = None,
        expected_experience_package_id: str | None = None,
        expected_package_id: str | None = None,
        expected_schema_version: str | None = None,
        expected_content_version: str | None = None,
    ) -> LocalResourcePackageSnapshot:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM local_resource_package_snapshots "
                "WHERE resource_package_id=?",
                (resource_package_id,),
            ).fetchone()
        if row is None:
            raise LocalResourceSnapshotError(
                f"LocalResourcePackage snapshot not found: {resource_package_id}"
            )
        snapshot = _decode_resource_snapshot(row)
        package = snapshot.package
        expectations = (
            (expected_run_id, package.run_id, "run_id"),
            (expected_itinerary_id, package.itinerary_id, "itinerary_id"),
            (expected_story_package_id, package.story_package_id, "StoryPackage"),
            (
                expected_experience_package_id,
                package.experience_package_id,
                "ExperiencePackage",
            ),
            (expected_package_id, package.package_id, "Catalog package"),
            (expected_schema_version, package.schema_version, "schema version"),
            (expected_content_version, package.content_version, "content version"),
        )
        for expected, actual, label in expectations:
            if expected is not None and expected != actual:
                raise LocalResourceSnapshotError(
                    f"LocalResourcePackage {label} mismatch"
                )
        return snapshot

    def load_for_run(
        self, run_id: str, itinerary_id: str
    ) -> LocalResourcePackageSnapshot:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                "SELECT resource_package_id FROM local_resource_package_snapshots "
                "WHERE run_id=? AND itinerary_id=?",
                (run_id, itinerary_id),
            ).fetchone()
        if row is None:
            raise LocalResourceSnapshotError(
                "LocalResourcePackage snapshot not found for formal run"
            )
        return self.load(
            row["resource_package_id"],
            expected_run_id=run_id,
            expected_itinerary_id=itinerary_id,
        )


def _require_upstream_associations(
    conn: sqlite3.Connection, package: LocalResourcePackage
) -> None:
    run = conn.execute(
        "SELECT status,result_itinerary_id FROM runs WHERE id=?", (package.run_id,)
    ).fetchone()
    if (
        run is None
        or run["status"] != "succeeded"
        or run["result_itinerary_id"] != package.itinerary_id
    ):
        raise LocalResourceSnapshotError(
            "LocalResourcePackage Run/itinerary association mismatch"
        )
    story = conn.execute(
        """SELECT run_id,itinerary_id,snapshot_hash,catalog_package_id,
                  schema_version,content_version
           FROM story_package_snapshots WHERE package_id=?""",
        (package.story_package_id,),
    ).fetchone()
    if (
        story is None
        or story["run_id"] != package.run_id
        or story["itinerary_id"] != package.itinerary_id
        or story["snapshot_hash"] != package.story_snapshot_hash
        or story["catalog_package_id"] != package.package_id
        or story["schema_version"] != package.schema_version
        or story["content_version"] != package.content_version
    ):
        raise LocalResourceSnapshotError(
            "LocalResourcePackage Story snapshot association mismatch"
        )
    experience = conn.execute(
        """SELECT run_id,itinerary_id,story_package_id,snapshot_hash,
                  catalog_package_id,schema_version,content_version
           FROM experience_package_snapshots WHERE package_id=?""",
        (package.experience_package_id,),
    ).fetchone()
    if (
        experience is None
        or experience["run_id"] != package.run_id
        or experience["itinerary_id"] != package.itinerary_id
        or experience["story_package_id"] != package.story_package_id
        or experience["snapshot_hash"] != package.experience_snapshot_hash
        or experience["catalog_package_id"] != package.package_id
        or experience["schema_version"] != package.schema_version
        or experience["content_version"] != package.content_version
    ):
        raise LocalResourceSnapshotError(
            "LocalResourcePackage Experience snapshot association mismatch"
        )


def _decode_resource_snapshot(row) -> LocalResourcePackageSnapshot:
    try:
        package = LocalResourcePackage.model_validate_json(row["snapshot_json"])
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        raise LocalResourceSnapshotError(
            "corrupted LocalResourcePackage snapshot"
        ) from exc
    digest = local_resource_package_hash(package)
    metadata_matches = (
        package.resource_package_id == row["resource_package_id"]
        and package.run_id == row["run_id"]
        and package.itinerary_id == row["itinerary_id"]
        and package.story_package_id == row["story_package_id"]
        and package.story_snapshot_hash == row["story_snapshot_hash"]
        and package.experience_package_id == row["experience_package_id"]
        and package.experience_snapshot_hash == row["experience_snapshot_hash"]
        and package.package_id == row["catalog_package_id"]
        and package.schema_version == row["schema_version"]
        and package.content_version == row["content_version"]
    )
    if (
        digest != package.snapshot_hash
        or digest != row["snapshot_hash"]
        or not metadata_matches
    ):
        raise LocalResourceSnapshotError("corrupted LocalResourcePackage snapshot")
    return LocalResourcePackageSnapshot(snapshot_hash=digest, package=package)
