from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.catalog.loader import FileCatalogLoader
from app.core.auth import create_token
from app.core.database import configure_database, get_conn, get_db_path, init_db
from app.experience import ExperiencePackageSnapshotRepository
from app.main import app
from app.product.fulfillment_models import FulfillmentStage, FulfillmentStageStatus
from app.product.fulfillment_repository import ProductFulfillmentRepository
from app.resources import (
    LocalResourcePackageSnapshotRepository,
    build_local_resource_package,
)
from app.story import StoryPackageSnapshotRepository
from tests.test_experience_binding import _bind as bind_experience
from tests.test_resource_recommendation import _candidate, _recommend
from tests.test_story_binding import _bind as bind_story


CATALOG_ROOT = Path(__file__).resolve().parents[1] / "content" / "catalog"
NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def _insert_empty_catalog_run(run_id: str, itinerary_id: str) -> None:
    context = {
        "package_id": "shanxi.changzhi",
        "schema_version": "1.0",
        "content_version": "0.6.0",
        "route_id": "changzhi.route.jingwei-fajiushan",
    }
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO itineraries(
               id,user_id,query,destination,plan_json,created_at)
               VALUES(?,'user-1','trip','长治市','{}',?)""",
            (itinerary_id, NOW.isoformat()),
        )
        conn.execute(
            """INSERT INTO runs(
               id,user_id,kind,status,concurrency_key,request_snapshot_json,
               result_itinerary_id,created_at,queued_at,started_at,finished_at,updated_at)
               VALUES(?,'user-1','travel_plan','succeeded',?,?,?, ?,?,?,?,?)""",
            (
                run_id,
                run_id,
                json.dumps({"catalog_context": context}),
                itinerary_id,
                NOW.isoformat(), NOW.isoformat(), NOW.isoformat(),
                NOW.isoformat(), NOW.isoformat(),
            ),
        )


@pytest.fixture(scope="module")
def catalog():
    return FileCatalogLoader(CATALOG_ROOT).load()


@pytest.fixture()
def trip_client(tmp_path, catalog):
    original = get_db_path()
    db_path = tmp_path / "trip-api.db"
    configure_database(db_path)
    init_db()
    context = {
        "package_id": "shanxi.changzhi",
        "schema_version": "1.0",
        "content_version": "0.6.0",
        "route_id": "changzhi.route.jingwei-fajiushan",
        "route_name": "精卫填海·发鸠山探秘",
    }
    plan = {
        "destination": "长治市",
        "start_date": "2026-08-23",
        "end_date": "2026-08-23",
        "days_count": 1,
        "days": [],
    }
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO users(id,username,password_hash,created_at) VALUES(?,?,?,?)",
            [
                ("user-1", "trip-owner", "unused", NOW.isoformat()),
                ("user-2", "other-owner", "unused", NOW.isoformat()),
            ],
        )
        conn.execute(
            """INSERT INTO itineraries(
               id,user_id,query,destination,start_date,end_date,plan_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                "itinerary-1", "user-1", "trip", "长治市", "2026-08-23",
                "2026-08-23", json.dumps(plan, ensure_ascii=False), NOW.isoformat(),
            ),
        )
        conn.execute(
            """INSERT INTO runs(
               id,user_id,kind,status,concurrency_key,request_snapshot_json,
               result_itinerary_id,created_at,queued_at,started_at,finished_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "run-1", "user-1", "travel_plan", "succeeded", "trip-api",
                json.dumps({"catalog_context": context}), "itinerary-1",
                NOW.isoformat(), NOW.isoformat(), NOW.isoformat(), NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    story = bind_story(catalog)
    story_snapshot = StoryPackageSnapshotRepository().save(story)
    experience = bind_experience(catalog)
    experience_snapshot = ExperiencePackageSnapshotRepository().save(experience)
    candidate = _candidate()
    package = build_local_resource_package(
        catalog_version=story.catalog_version,
        run_id="run-1",
        itinerary_id="itinerary-1",
        story_package_id=story.package_id,
        story_snapshot_hash=story_snapshot.snapshot_hash,
        experience_package_id=experience.package_id,
        experience_snapshot_hash=experience_snapshot.snapshot_hash,
        resources=(candidate,),
        result=_recommend(candidate),
        created_at=NOW,
    )
    resource_snapshot = LocalResourcePackageSnapshotRepository().save(package)
    client = TestClient(app)
    try:
        yield client, story_snapshot, experience_snapshot, resource_snapshot
    finally:
        client.close()
        configure_database(original)


def test_trip_api_loads_exact_persisted_hierarchy(trip_client):
    client, story, experience, resources = trip_client
    response = client.get(
        "/api/runs/run-1/trip",
        headers={"Authorization": f"Bearer {create_token('user-1')}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["itinerary"]["id"] == "itinerary-1"
    assert body["story"]["snapshot_hash"] == story.snapshot_hash
    assert body["experience"]["snapshot_hash"] == experience.snapshot_hash
    assert body["resources"]["snapshot_hash"] == resources.snapshot_hash
    assert (
        body["resources"]["package"]["story_package_id"]
        == body["story"]["package"]["package_id"]
    )
    assert (
        body["resources"]["package"]["experience_package_id"]
        == body["experience"]["package"]["package_id"]
    )


def test_trip_api_enforces_run_ownership(trip_client):
    client, *_ = trip_client

    response = client.get(
        "/api/runs/run-1/trip",
        headers={"Authorization": f"Bearer {create_token('user-2')}"},
    )

    assert response.status_code == 404


def test_trip_api_requires_authentication(trip_client):
    client, *_ = trip_client
    assert client.get("/api/runs/run-1/trip").status_code == 401


def test_trip_api_returns_truthful_partial_package_states(trip_client):
    client, *_ = trip_client
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO itineraries(
               id,user_id,query,destination,plan_json,created_at)
               VALUES(?,?,?,?,?,?)""",
            ("itinerary-2", "user-1", "plain", "太原", "{}", NOW.isoformat()),
        )
        conn.execute(
            """INSERT INTO runs(
               id,user_id,kind,status,concurrency_key,request_snapshot_json,
               result_itinerary_id,created_at,queued_at,started_at,finished_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "run-2", "user-1", "travel_plan", "succeeded", "trip-api-2",
                "{}", "itinerary-2", NOW.isoformat(), NOW.isoformat(),
                NOW.isoformat(), NOW.isoformat(), NOW.isoformat(),
            ),
        )

    response = client.get(
        "/api/runs/run-2/trip",
        headers={"Authorization": f"Bearer {create_token('user-1')}"},
    )

    assert response.status_code == 200
    assert response.json()["story"] == {"status": "not_generated"}
    assert response.json()["experience"] == {"status": "not_generated"}
    assert response.json()["resources"] == {"status": "not_generated"}


def test_trip_api_projects_durable_stage_status_and_safe_error(trip_client):
    client, *_ = trip_client
    repository = ProductFulfillmentRepository()
    job = repository.create(
        owner_id="user-1",
        run_id="run-1",
        itinerary_id="itinerary-1",
        route_id="changzhi.route.jingwei-fajiushan",
        package_id="shanxi.changzhi",
        schema_version="1.0",
        content_version="0.6.0",
    )
    repository.claim_stage(job.job_id, FulfillmentStage.STORY)
    repository.fail_stage(
        job.job_id,
        FulfillmentStage.STORY,
        error_class="ProviderFailure",
        error_code="STORY_GENERATION_FAILED",
        error_message="故事生成未完成。",
    )

    response = client.get(
        "/api/runs/run-1/trip",
        headers={"Authorization": f"Bearer {create_token('user-1')}"},
    )
    body = response.json()
    # Existing immutable snapshots remain authoritative and available.
    assert body["story"]["status"] == "available"
    assert body["experience"]["status"] == "available"
    assert body["resources"]["status"] == "available"
    assert body["fulfillment"]["status"] == "failed"


def test_retry_api_is_owner_protected_and_preserves_successful_upstream(trip_client):
    client, story, experience, _resources = trip_client
    repository = ProductFulfillmentRepository()
    job = repository.create(
        owner_id="user-1",
        run_id="run-1",
        itinerary_id="itinerary-1",
        route_id="changzhi.route.jingwei-fajiushan",
        package_id="shanxi.changzhi",
        schema_version="1.0",
        content_version="0.6.0",
    )
    # Reconcile the two successful upstream package identities before failing resources.
    with get_conn() as conn:
        conn.execute(
            """UPDATE product_fulfillment_jobs SET
               story_status='succeeded',story_package_id=?,story_snapshot_hash=?,
               experience_status='succeeded',experience_package_id=?,experience_snapshot_hash=?,
               resources_status='failed',status='partial',last_error_stage='resources',
               last_error_code='RESOURCE_PROVIDER_UNAVAILABLE',
               last_error_message='附近资源暂时无法核验。' WHERE job_id=?""",
            (
                story.package.package_id,
                story.snapshot_hash,
                experience.package.package_id,
                experience.snapshot_hash,
                job.job_id,
            ),
        )

    denied = client.post(
        "/api/runs/run-1/trip/fulfillment/retry",
        headers={"Authorization": f"Bearer {create_token('user-2')}"},
    )
    assert denied.status_code == 404

    response = client.post(
        "/api/runs/run-1/trip/fulfillment/retry",
        headers={"Authorization": f"Bearer {create_token('user-1')}"},
    )
    assert response.status_code == 200
    retried = repository.get("user-1", "run-1")
    assert retried.story_status is FulfillmentStageStatus.SUCCEEDED
    assert retried.experience_status is FulfillmentStageStatus.SUCCEEDED
    assert retried.resources_status is FulfillmentStageStatus.PENDING


def test_trip_api_exposes_pending_generating_failed_and_blocked(trip_client):
    client, *_ = trip_client
    _insert_empty_catalog_run("run-stage", "itinerary-stage")
    repository = ProductFulfillmentRepository()
    job = repository.create(
        owner_id="user-1",
        run_id="run-stage",
        itinerary_id="itinerary-stage",
        route_id="changzhi.route.jingwei-fajiushan",
        package_id="shanxi.changzhi",
        schema_version="1.0",
        content_version="0.6.0",
    )
    headers = {"Authorization": f"Bearer {create_token('user-1')}"}

    pending = client.get("/api/runs/run-stage/trip", headers=headers).json()
    assert pending["story"]["status"] == "pending"
    assert pending["experience"]["status"] == "pending"

    repository.claim_stage(job.job_id, FulfillmentStage.STORY)
    generating = client.get("/api/runs/run-stage/trip", headers=headers).json()
    assert generating["story"]["status"] == "generating"

    repository.fail_stage(
        job.job_id,
        FulfillmentStage.STORY,
        error_class="StoryValidationError",
        error_code="STORY_VALIDATION_FAILED",
        error_message="故事生成未完成。",
    )
    failed = client.get("/api/runs/run-stage/trip", headers=headers).json()
    assert failed["story"] == {
        "status": "failed",
        "error_code": "STORY_VALIDATION_FAILED",
        "message": "故事生成未完成。",
    }
    assert failed["experience"]["status"] == "blocked"
    assert failed["resources"]["status"] == "blocked"


def test_trip_get_is_snapshot_only_and_stable_across_repeated_reads(trip_client):
    client, story, experience, resources = trip_client
    headers = {"Authorization": f"Bearer {create_token('user-1')}"}
    with get_conn() as conn:
        before = tuple(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "story_package_snapshots",
                "experience_package_snapshots",
                "local_resource_package_snapshots",
            )
        )

    responses = [client.get("/api/runs/run-1/trip", headers=headers).json() for _ in range(5)]

    assert {item["story"]["snapshot_hash"] for item in responses} == {story.snapshot_hash}
    assert {item["experience"]["snapshot_hash"] for item in responses} == {experience.snapshot_hash}
    assert {item["resources"]["snapshot_hash"] for item in responses} == {resources.snapshot_hash}
    with get_conn() as conn:
        after = tuple(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "story_package_snapshots",
                "experience_package_snapshots",
                "local_resource_package_snapshots",
            )
        )
    assert after == before
