from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from app.catalog.loader import FileCatalogLoader
from app.core.database import get_conn, init_db
from app.experience import ExperiencePackageSnapshotRepository
from app.resources import (
    LocalResourcePackage,
    LocalResourcePackageSnapshotRepository,
    LocalResourceSnapshotError,
    RecommendationResult,
    build_local_resource_package,
    local_resource_package_hash,
)
from app.story import StoryPackageSnapshotRepository
from tests.test_experience_binding import _bind as bind_experience
from tests.test_resource_recommendation import _candidate, _recommend
from tests.test_story_binding import _bind as bind_story


CATALOG_ROOT = Path(__file__).resolve().parents[1] / "content" / "catalog"
CREATED_AT = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def repository():
    return FileCatalogLoader(CATALOG_ROOT).load()


@pytest.fixture()
def snapshot_db(tmp_path):
    path = tmp_path / "resource-snapshots.db"
    init_db(path)
    now = CREATED_AT.isoformat()
    with get_conn(path) as conn:
        conn.execute(
            "INSERT INTO users(id,username,password_hash,created_at) VALUES(?,?,?,?)",
            ("user-1", "resource-snapshot-user", "unused", now),
        )
        conn.execute(
            """INSERT INTO itineraries(
               id,user_id,query,destination,start_date,end_date,plan_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                "itinerary-1",
                "user-1",
                "resource snapshot test",
                "destination",
                "2026-08-23",
                "2026-08-23",
                "{}",
                now,
            ),
        )
        conn.execute(
            """INSERT INTO runs(
               id,user_id,kind,status,concurrency_key,request_snapshot_json,
               result_itinerary_id,created_at,queued_at,started_at,finished_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "run-1",
                "user-1",
                "travel_plan",
                "succeeded",
                "resource-snapshot-test",
                "{}",
                "itinerary-1",
                now,
                now,
                now,
                now,
                now,
            ),
        )
    return path


def _package(repository, snapshot_db, **updates):
    story = bind_story(repository)
    story_snapshot = StoryPackageSnapshotRepository(snapshot_db).save(story)
    experience = bind_experience(repository)
    experience_snapshot = ExperiencePackageSnapshotRepository(snapshot_db).save(
        experience
    )
    resource = _candidate()
    result = _recommend(resource)
    values = {
        "catalog_version": story.catalog_version,
        "run_id": "run-1",
        "itinerary_id": "itinerary-1",
        "story_package_id": story.package_id,
        "story_snapshot_hash": story_snapshot.snapshot_hash,
        "experience_package_id": experience.package_id,
        "experience_snapshot_hash": experience_snapshot.snapshot_hash,
        "resources": (resource,),
        "result": result,
        "created_at": CREATED_AT,
    }
    values.update(updates)
    return build_local_resource_package(**values)


def test_resource_package_save_load_round_trip(repository, snapshot_db):
    package = _package(repository, snapshot_db)
    saved = LocalResourcePackageSnapshotRepository(snapshot_db).save(package)
    loaded = LocalResourcePackageSnapshotRepository(snapshot_db).load(
        package.resource_package_id
    )
    assert loaded == saved
    assert LocalResourcePackage.model_validate_json(
        loaded.package.model_dump_json()
    ) == package


def test_empty_resource_package_is_a_valid_persisted_terminal_result(
    repository, snapshot_db
):
    package = _package(
        repository,
        snapshot_db,
        resources=(),
        result=RecommendationResult(recommendations=(), warnings=()),
    )
    saved = LocalResourcePackageSnapshotRepository(snapshot_db).save(package)

    assert saved.package.resources == ()
    assert saved.package.recommendations == ()


def test_resource_package_hash_is_canonical(repository, snapshot_db):
    package = _package(repository, snapshot_db)
    assert package.snapshot_hash == local_resource_package_hash(package)
    assert len(package.snapshot_hash) == 64


def test_resource_package_preserves_catalog_version(repository, snapshot_db):
    package = _package(repository, snapshot_db)
    assert (package.package_id, package.schema_version, package.content_version) == (
        "shanxi.changzhi", "1.0", "0.6.0"
    )


def test_run_association_mismatch_fails(repository, snapshot_db):
    package = _package(repository, snapshot_db, run_id="other-run")
    with pytest.raises(LocalResourceSnapshotError, match="Run/itinerary"):
        LocalResourcePackageSnapshotRepository(snapshot_db).save(package)


def test_itinerary_association_mismatch_fails(repository, snapshot_db):
    package = _package(repository, snapshot_db, itinerary_id="other-itinerary")
    with pytest.raises(LocalResourceSnapshotError, match="Run/itinerary"):
        LocalResourcePackageSnapshotRepository(snapshot_db).save(package)


def test_story_association_mismatch_fails(repository, snapshot_db):
    package = _package(
        repository,
        snapshot_db,
        story_package_id="story-package.missing",
    )
    with pytest.raises(LocalResourceSnapshotError, match="Story snapshot"):
        LocalResourcePackageSnapshotRepository(snapshot_db).save(package)


def test_experience_association_mismatch_fails(repository, snapshot_db):
    package = _package(
        repository,
        snapshot_db,
        experience_package_id="experience-package.missing",
    )
    with pytest.raises(LocalResourceSnapshotError, match="Experience snapshot"):
        LocalResourcePackageSnapshotRepository(snapshot_db).save(package)


def test_corrupt_snapshot_fails(repository, snapshot_db):
    package = _package(repository, snapshot_db)
    storage = LocalResourcePackageSnapshotRepository(snapshot_db)
    storage.save(package)
    with get_conn(snapshot_db) as conn:
        payload = json.loads(
            conn.execute(
                "SELECT snapshot_json FROM local_resource_package_snapshots"
            ).fetchone()[0]
        )
        payload["warnings"] = ["tampered"]
        conn.execute(
            "UPDATE local_resource_package_snapshots SET snapshot_json=?",
            (json.dumps(payload, ensure_ascii=False),),
        )
    with pytest.raises(LocalResourceSnapshotError, match="corrupted"):
        storage.load(package.resource_package_id)


def test_expected_version_mismatch_fails(repository, snapshot_db):
    package = _package(repository, snapshot_db)
    storage = LocalResourcePackageSnapshotRepository(snapshot_db)
    storage.save(package)
    with pytest.raises(LocalResourceSnapshotError, match="content version"):
        storage.load(
            package.resource_package_id,
            expected_content_version="9.9.9",
        )


def test_load_for_run_validates_association(repository, snapshot_db):
    package = _package(repository, snapshot_db)
    storage = LocalResourcePackageSnapshotRepository(snapshot_db)
    storage.save(package)
    loaded = storage.load_for_run("run-1", "itinerary-1")
    assert loaded.package == package


def test_load_does_not_call_provider(repository, snapshot_db, monkeypatch):
    package = _package(repository, snapshot_db)
    storage = LocalResourcePackageSnapshotRepository(snapshot_db)
    storage.save(package)

    async def fail_provider(*args, **kwargs):
        raise AssertionError("Provider must not be called while loading a snapshot")

    monkeypatch.setattr(
        "app.providers.amap.poi.search_around_pois_async", fail_provider
    )
    assert storage.load(package.resource_package_id).package == package


def test_changed_package_with_stale_hash_is_rejected(repository, snapshot_db):
    package = _package(repository, snapshot_db)
    changed = package.model_copy(update={"warnings": ("changed",)})
    with pytest.raises(LocalResourceSnapshotError, match="hash mismatch"):
        LocalResourcePackageSnapshotRepository(snapshot_db).save(changed)
