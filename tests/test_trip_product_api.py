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
        "content_version": "0.3.0",
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
