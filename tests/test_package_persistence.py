from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.catalog.loader import FileCatalogLoader
from app.core.database import get_conn, init_db
from app.experience import (
    ExperienceGenerationService,
    ExperiencePackage,
    ExperiencePackageSnapshotRepository,
    ExperienceSnapshotError,
)
from app.knowledge.models import CatalogVersionSnapshot
from app.story import (
    StoryPackage,
    StoryPackageSnapshotRepository,
    StorySnapshotError,
)
from tests.test_experience_binding import _bind as bind_experience
from tests.test_story_binding import _bind as bind_story


CATALOG_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1] / "content" / "catalog"


@pytest.fixture(scope="module")
def repository():
    return FileCatalogLoader(CATALOG_ROOT).load()


@pytest.fixture()
def snapshot_db(tmp_path):
    path = tmp_path / "snapshots.db"
    init_db(path)
    now = datetime.now(timezone.utc).isoformat()
    with get_conn(path) as conn:
        conn.execute(
            "INSERT INTO users(id,username,password_hash,created_at) VALUES(?,?,?,?)",
            ("user-1", "snapshot-user", "unused", now),
        )
        conn.execute(
            """INSERT INTO itineraries(
               id,user_id,query,destination,start_date,end_date,plan_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                "itinerary-1",
                "user-1",
                "snapshot test",
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
                "snapshot-test",
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


def _story_snapshot(repository, snapshot_db):
    package = bind_story(repository)
    snapshot = StoryPackageSnapshotRepository(snapshot_db).save(package)
    return package, snapshot


def _experience_snapshot(repository, snapshot_db):
    story, story_snapshot = _story_snapshot(repository, snapshot_db)
    package = bind_experience(repository)
    assert package.story_package_id == story.package_id
    assert package.story_snapshot_hash == story_snapshot.snapshot_hash
    snapshot = ExperiencePackageSnapshotRepository(snapshot_db).save(package)
    return package, snapshot


def test_story_package_save_load_and_json_round_trip(repository, snapshot_db):
    package, saved = _story_snapshot(repository, snapshot_db)
    loaded = StoryPackageSnapshotRepository(snapshot_db).load(package.package_id)

    assert loaded == saved
    assert StoryPackage.model_validate_json(loaded.package.model_dump_json()) == package
    assert len(loaded.snapshot_hash) == 64


def test_story_snapshot_preserves_formal_associations_and_catalog_version(
    repository, snapshot_db
):
    package, _ = _story_snapshot(repository, snapshot_db)
    loaded = StoryPackageSnapshotRepository(snapshot_db).load(
        package.package_id,
        expected_run_id="run-1",
        expected_itinerary_id="itinerary-1",
        expected_catalog_version=package.catalog_version,
    )

    assert loaded.package.run_id == "run-1"
    assert loaded.package.itinerary_id == "itinerary-1"
    assert loaded.package.catalog_version.content_version == "0.3.0"


def test_story_snapshot_preserves_claim_citation_qualifier_and_identity(
    repository, snapshot_db
):
    package, saved = _story_snapshot(repository, snapshot_db)

    assert saved.package.knowledge_snapshot.used_claim_ids == package.knowledge_snapshot.used_claim_ids
    assert saved.package.knowledge_snapshot.citations == package.knowledge_snapshot.citations
    assert any(chapter.qualifiers_used for chapter in saved.package.chapters)
    assert all(
        identity.provider.value == "amap" and identity.external_poi_id
        for binding in saved.package.chapter_bindings
        for identity in binding.resolved_poi_ids
    )
    assert saved.package.binding_metrics.name_only_binding_count == 0


def test_story_snapshot_load_and_experience_retry_do_not_call_llm(
    repository, snapshot_db, monkeypatch
):
    package, saved = _story_snapshot(repository, snapshot_db)
    monkeypatch.setattr(
        "app.story.service.build_structured_llm",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM called")),
    )
    storage = StoryPackageSnapshotRepository(snapshot_db)

    first = storage.load_for_run("run-1", "itinerary-1", package.story_id)
    retry = storage.load_for_run("run-1", "itinerary-1", package.story_id)

    assert first.snapshot_hash == retry.snapshot_hash == saved.snapshot_hash
    assert first.package == retry.package
    experience = repository.list_experiences(route_id=retry.package.route_id)[0]
    activity = repository.list_activities(experience.experience_id)[0]
    context = ExperienceGenerationService(
        repository, retry.package
    ).build_activity_context(activity.activity_id)
    assert context.generated_story_chapters


def test_story_snapshot_catalog_and_itinerary_mismatch_fail(repository, snapshot_db):
    package, _ = _story_snapshot(repository, snapshot_db)
    storage = StoryPackageSnapshotRepository(snapshot_db)
    wrong_version = CatalogVersionSnapshot(
        package_id=package.catalog_version.package_id,
        schema_version=package.catalog_version.schema_version,
        content_version="9.9.9",
    )

    with pytest.raises(StorySnapshotError, match="Catalog version mismatch"):
        storage.load(package.package_id, expected_catalog_version=wrong_version)
    with pytest.raises(StorySnapshotError, match="itinerary_id mismatch"):
        storage.load(package.package_id, expected_itinerary_id="other-itinerary")


def test_corrupted_story_snapshot_fails_explicitly(repository, snapshot_db):
    package, _ = _story_snapshot(repository, snapshot_db)
    with get_conn(snapshot_db) as conn:
        conn.execute(
            "UPDATE story_package_snapshots SET snapshot_json='not-json' WHERE package_id=?",
            (package.package_id,),
        )

    with pytest.raises(StorySnapshotError, match="corrupted"):
        StoryPackageSnapshotRepository(snapshot_db).load(package.package_id)


def test_story_snapshot_is_immutable(repository, snapshot_db):
    package, _ = _story_snapshot(repository, snapshot_db)
    changed = package.model_copy(update={"presentation_hints": ("changed",)})

    with pytest.raises(StorySnapshotError, match="immutable"):
        StoryPackageSnapshotRepository(snapshot_db).save(changed)


def test_experience_package_save_load_and_json_round_trip(repository, snapshot_db):
    package, saved = _experience_snapshot(repository, snapshot_db)
    loaded = ExperiencePackageSnapshotRepository(snapshot_db).load(package.package_id)

    assert loaded == saved
    assert ExperiencePackage.model_validate_json(loaded.package.model_dump_json()) == package


def test_experience_snapshot_load_for_run_checks_story_association(
    repository, snapshot_db
):
    package, saved = _experience_snapshot(repository, snapshot_db)

    loaded = ExperiencePackageSnapshotRepository(snapshot_db).load_for_run(
        "run-1",
        "itinerary-1",
        package.story_package_id,
        expected_catalog_version=package.catalog_version,
    )

    assert loaded == saved
    assert len(loaded.snapshot_hash) == 64


def test_experience_snapshot_preserves_all_formal_associations(
    repository, snapshot_db
):
    package, _ = _experience_snapshot(repository, snapshot_db)
    loaded = ExperiencePackageSnapshotRepository(snapshot_db).load(
        package.package_id,
        expected_run_id="run-1",
        expected_itinerary_id="itinerary-1",
        expected_story_package_id=package.story_package_id,
        expected_catalog_version=package.catalog_version,
    )

    assert loaded.package.story_snapshot_hash == package.story_snapshot_hash
    assert loaded.package.catalog_version.content_version == "0.3.0"


def test_experience_snapshot_preserves_rendered_content_and_safety(
    repository, snapshot_db
):
    package, saved = _experience_snapshot(repository, snapshot_db)

    assert saved.package.activities == package.activities
    assert all(item.raw_generation for item in saved.package.activities)
    assert saved.package.safety_summary == package.safety_summary
    assert all(value == 0 for value in saved.package.safety_summary.model_dump().values())


def test_experience_snapshot_load_does_not_call_llm(
    repository, snapshot_db, monkeypatch
):
    package, _ = _experience_snapshot(repository, snapshot_db)
    monkeypatch.setattr(
        "app.experience.service.build_structured_llm",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM called")),
    )

    loaded = ExperiencePackageSnapshotRepository(snapshot_db).load(package.package_id)

    assert loaded.package == package


def test_experience_snapshot_rejects_story_association_mismatch(
    repository, snapshot_db
):
    package, _ = _experience_snapshot(repository, snapshot_db)
    changed = package.model_copy(update={"story_snapshot_hash": "0" * 64})

    with pytest.raises(ExperienceSnapshotError, match="Story snapshot association"):
        ExperiencePackageSnapshotRepository(snapshot_db).save(changed)


def test_experience_snapshot_expected_association_mismatch_fails(
    repository, snapshot_db
):
    package, _ = _experience_snapshot(repository, snapshot_db)
    storage = ExperiencePackageSnapshotRepository(snapshot_db)

    with pytest.raises(ExperienceSnapshotError, match="run_id mismatch"):
        storage.load(package.package_id, expected_run_id="other-run")
    with pytest.raises(ExperienceSnapshotError, match="itinerary_id mismatch"):
        storage.load(package.package_id, expected_itinerary_id="other-itinerary")
    with pytest.raises(ExperienceSnapshotError, match="Story snapshot mismatch"):
        storage.load(package.package_id, expected_story_package_id="other.story-package")


def test_corrupted_experience_snapshot_fails_explicitly(repository, snapshot_db):
    package, _ = _experience_snapshot(repository, snapshot_db)
    with get_conn(snapshot_db) as conn:
        conn.execute(
            "UPDATE experience_package_snapshots SET snapshot_hash=? WHERE package_id=?",
            ("0" * 64, package.package_id),
        )

    with pytest.raises(ExperienceSnapshotError, match="corrupted"):
        ExperiencePackageSnapshotRepository(snapshot_db).load(package.package_id)


def test_experience_snapshot_is_immutable(repository, snapshot_db):
    package, _ = _experience_snapshot(repository, snapshot_db)
    changed = package.model_copy(update={"warnings": ("changed",)})

    with pytest.raises(ExperienceSnapshotError, match="immutable"):
        ExperiencePackageSnapshotRepository(snapshot_db).save(changed)
