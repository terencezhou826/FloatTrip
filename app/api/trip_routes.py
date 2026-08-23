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
from app.product.fulfillment_models import FulfillmentStageStatus
from app.product.fulfillment_repository import (
    FulfillmentJobNotFound,
    FulfillmentTransitionError,
    ProductFulfillmentRepository,
)
from app.runtime.container import manager, product_fulfillment_executor
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


def _job_stage_status(job, stage: str) -> dict:
    if job is None:
        return {"status": "not_generated"}
    status = getattr(job, f"{stage}_status")
    if status is FulfillmentStageStatus.RUNNING:
        return {"status": "generating"}
    if status is FulfillmentStageStatus.FAILED:
        result = {"status": "failed"}
        if job.last_error_stage and job.last_error_stage.value == stage:
            result.update(
                {
                    "error_code": job.last_error_code,
                    "message": job.last_error_message,
                }
            )
        return result
    return {"status": status.value}


def _fulfillment_view(job) -> dict | None:
    if job is None:
        return None
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "story_status": job.story_status.value,
        "experience_status": job.experience_status.value,
        "resources_status": job.resources_status.value,
        "attempt_count": job.attempt_count,
        "updated_at": job.updated_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
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
    job = ProductFulfillmentRepository().get_for_run(run_id, itinerary_id)
    story_data = _job_stage_status(job, "story")
    experience_data = _job_stage_status(job, "experience")
    resources_data = _job_stage_status(job, "resources")
    if len(story_row) > 1:
        raise HTTPException(status_code=409, detail="Run 存在多个 StoryPackage 快照")
    story = None
    experience = None
    try:
        if story_row:
            story = StoryPackageSnapshotRepository().load(
                story_row[0]["package_id"],
                expected_run_id=run_id,
                expected_itinerary_id=itinerary_id,
                expected_catalog_version=expected_version,
            )
            story_data = _optional_snapshot_status(story.package, story.snapshot_hash)
    except StorySnapshotError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if story is not None:
        try:
            experience = ExperiencePackageSnapshotRepository().load_for_run(
                run_id,
                itinerary_id,
                story.package.package_id,
                expected_catalog_version=expected_version,
            )
            experience_data = _optional_snapshot_status(
                experience.package, experience.snapshot_hash
            )
        except ExperienceSnapshotError as exc:
            if "not found for formal run" not in str(exc):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
    if story is not None and experience is not None:
        try:
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
            resources_data["empty"] = not bool(package.recommendations)
        except LocalResourceSnapshotError as exc:
            if "not found for formal run" not in str(exc):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
    if job is not None:
        for stage, payload in (
            ("story", story_data),
            ("experience", experience_data),
            ("resources", resources_data),
        ):
            persisted = getattr(job, f"{stage}_status")
            if persisted is FulfillmentStageStatus.SUCCEEDED and payload["status"] != "available":
                raise HTTPException(
                    status_code=409,
                    detail=f"{stage} fulfillment snapshot identity mismatch",
                )
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
        "fulfillment": _fulfillment_view(job),
    }


@router.post("/runs/{run_id}/trip/fulfillment/retry")
async def retry_product_fulfillment(
    run_id: str,
    authorization: str | None = Header(default=None),
):
    owner = _owner(authorization)
    try:
        manager.runs.get(owner, run_id)
        job = await product_fulfillment_executor.retry(owner, run_id)
    except (OwnedResourceNotFound, FulfillmentJobNotFound) as exc:
        raise HTTPException(status_code=404, detail="旅程生成任务不存在") from exc
    except FulfillmentTransitionError as exc:
        raise HTTPException(status_code=409, detail="当前没有可重试的失败阶段") from exc
    return {"fulfillment": _fulfillment_view(job)}
