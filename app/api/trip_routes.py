"""Ownership-protected, snapshot-only product Trip reads."""

from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException

from app.core.auth import decode_token
from app.core.database import get_conn
from app.experience.persistence import (
    ExperiencePackageSnapshotRepository,
    ExperienceSnapshotError,
)
from app.knowledge.models import CatalogVersionSnapshot
from app.resources.persistence import (
    LocalResourcePackageSnapshotRepository,
    LocalResourceSnapshotError,
)
from app.runtime.container import manager
from app.runtime.repositories import OwnedResourceNotFound
from app.story.persistence import StoryPackageSnapshotRepository, StorySnapshotError


router = APIRouter(prefix="/api", tags=["product-trip"])


def _owner(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="需要登录")
    owner = decode_token(authorization[7:])
    if not owner:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    return owner


def _optional_snapshot_status(package, snapshot_hash: str):
    return {
        "status": "available",
        "snapshot_hash": snapshot_hash,
        "package": package.model_dump(mode="json"),
    }


@router.get("/runs/{run_id}/trip")
def get_product_trip(
    run_id: str,
    authorization: str | None = Header(default=None),
):
    owner = _owner(authorization)
    try:
        run = manager.runs.get(owner, run_id)
    except OwnedResourceNotFound as exc:
        raise HTTPException(status_code=404, detail="旅程不存在") from exc
    itinerary_id = run.get("result_itinerary_id")
    if not itinerary_id:
        raise HTTPException(status_code=409, detail="旅程尚未生成正式行程")
    with get_conn() as conn:
        itinerary = conn.execute(
            "SELECT id,user_id,plan_json FROM itineraries WHERE id=? AND user_id=?",
            (itinerary_id, owner),
        ).fetchone()
        story_row = conn.execute(
            """SELECT package_id FROM story_package_snapshots
               WHERE run_id=? AND itinerary_id=? ORDER BY created_at DESC""",
            (run_id, itinerary_id),
        ).fetchall()
    if itinerary is None:
        raise HTTPException(status_code=409, detail="Run 与行程归属关系不一致")
    try:
        plan = json.loads(itinerary["plan_json"])
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=409, detail="正式行程快照损坏") from exc
    context = run.get("request_snapshot", {}).get("catalog_context") or {}
    expected_version = None
    if all(context.get(key) for key in ("package_id", "schema_version", "content_version")):
        expected_version = CatalogVersionSnapshot(
            package_id=context["package_id"],
            schema_version=context["schema_version"],
            content_version=context["content_version"],
        )
    story_data = {"status": "not_generated"}
    experience_data = {"status": "not_generated"}
    resources_data = {"status": "not_generated"}
    if len(story_row) > 1:
        raise HTTPException(status_code=409, detail="Run 存在多个 StoryPackage 快照")
    try:
        if story_row:
            story = StoryPackageSnapshotRepository().load(
                story_row[0]["package_id"],
                expected_run_id=run_id,
                expected_itinerary_id=itinerary_id,
                expected_catalog_version=expected_version,
            )
            story_data = _optional_snapshot_status(story.package, story.snapshot_hash)
            experience = ExperiencePackageSnapshotRepository().load_for_run(
                run_id,
                itinerary_id,
                story.package.package_id,
                expected_catalog_version=expected_version,
            )
            experience_data = _optional_snapshot_status(
                experience.package, experience.snapshot_hash
            )
            resources = LocalResourcePackageSnapshotRepository().load_for_run(
                run_id, itinerary_id
            )
            package = resources.package
            if (
                package.story_package_id != story.package.package_id
                or package.story_snapshot_hash != story.snapshot_hash
                or package.experience_package_id != experience.package.package_id
                or package.experience_snapshot_hash != experience.snapshot_hash
            ):
                raise LocalResourceSnapshotError(
                    "LocalResourcePackage upstream snapshot mismatch"
                )
            resources_data = _optional_snapshot_status(
                package, resources.snapshot_hash
            )
    except ExperienceSnapshotError as exc:
        if "not found for formal run" not in str(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LocalResourceSnapshotError as exc:
        if "not found for formal run" not in str(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    except StorySnapshotError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "run": {
            "id": run["id"],
            "status": run["status"],
            "request_snapshot": run.get("request_snapshot") or {},
        },
        "itinerary": {"id": itinerary_id, "plan": plan},
        "story": story_data,
        "experience": experience_data,
        "resources": resources_data,
    }
