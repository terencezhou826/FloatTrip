"""SQLite persistence and atomic transitions for fulfillment jobs."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.database import get_conn
from app.core.http import redact_sensitive_text
from app.product.fulfillment_models import (
    FulfillmentSnapshotRef,
    FulfillmentStage,
    FulfillmentStageStatus,
    ProductFulfillmentJob,
    ProductFulfillmentStatus,
)


class FulfillmentJobNotFound(LookupError):
    pass


class FulfillmentTransitionError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode(row: sqlite3.Row | None) -> ProductFulfillmentJob:
    if row is None:
        raise FulfillmentJobNotFound("fulfillment job not found")
    return ProductFulfillmentJob.model_validate(dict(row))


def _overall_status(statuses: tuple[str, str, str]) -> ProductFulfillmentStatus:
    story, experience, resources = statuses
    terminal_ok = {
        FulfillmentStageStatus.SUCCEEDED.value,
        FulfillmentStageStatus.SKIPPED.value,
        FulfillmentStageStatus.NOT_APPLICABLE.value,
    }
    if story == FulfillmentStageStatus.FAILED.value:
        return ProductFulfillmentStatus.FAILED
    if experience == FulfillmentStageStatus.FAILED.value:
        return ProductFulfillmentStatus.PARTIAL
    if resources == FulfillmentStageStatus.FAILED.value:
        return ProductFulfillmentStatus.PARTIAL
    if all(value in terminal_ok for value in statuses):
        return ProductFulfillmentStatus.SUCCEEDED
    if any(value == FulfillmentStageStatus.RUNNING.value for value in statuses):
        return ProductFulfillmentStatus.RUNNING
    return ProductFulfillmentStatus.PENDING


class ProductFulfillmentRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def create(
        self,
        *,
        owner_id: str,
        run_id: str,
        itinerary_id: str,
        route_id: str,
        package_id: str,
        schema_version: str,
        content_version: str,
    ) -> ProductFulfillmentJob:
        now = _now()
        job_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"floattrip:fulfillment:{run_id}:{itinerary_id}")
        )
        with get_conn(self.db_path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO product_fulfillment_jobs(
                   job_id,owner_id,run_id,itinerary_id,route_id,package_id,
                   schema_version,content_version,status,story_status,
                   experience_status,resources_status,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,'pending','pending','pending','pending',?,?)""",
                (
                    job_id, owner_id, run_id, itinerary_id, route_id, package_id,
                    schema_version, content_version, now, now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM product_fulfillment_jobs WHERE run_id=? AND itinerary_id=?",
                (run_id, itinerary_id),
            ).fetchone()
        job = _decode(row)
        expected = (owner_id, route_id, package_id, schema_version, content_version)
        actual = (
            job.owner_id, job.route_id, job.package_id,
            job.schema_version, job.content_version,
        )
        if actual != expected:
            raise FulfillmentTransitionError("conflicting fulfillment job identity")
        return job

    def get(self, owner_id: str, run_id: str) -> ProductFulfillmentJob:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM product_fulfillment_jobs WHERE owner_id=? AND run_id=?",
                (owner_id, run_id),
            ).fetchone()
        return _decode(row)

    def get_internal(self, job_id: str) -> ProductFulfillmentJob:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM product_fulfillment_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return _decode(row)

    def get_for_run(self, run_id: str, itinerary_id: str) -> ProductFulfillmentJob | None:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM product_fulfillment_jobs WHERE run_id=? AND itinerary_id=?",
                (run_id, itinerary_id),
            ).fetchone()
        return _decode(row) if row is not None else None

    def list_recoverable(self) -> tuple[ProductFulfillmentJob, ...]:
        with get_conn(self.db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM product_fulfillment_jobs
                   WHERE status IN ('pending','running') ORDER BY created_at,job_id"""
            ).fetchall()
        return tuple(_decode(row) for row in rows)

    def discover_eligible_runs(
        self, *, created_after: str | None = None
    ) -> tuple[dict[str, Any], ...]:
        """Return new Catalog runs plus historical runs with a complete snapshot chain."""
        with get_conn(self.db_path) as conn:
            rows = conn.execute(
                """SELECT r.id,r.user_id,r.result_itinerary_id,r.request_snapshot_json,
                          r.finished_at
                   FROM runs r
                   WHERE r.kind='travel_plan' AND r.status='succeeded'
                     AND r.result_itinerary_id IS NOT NULL
                     AND NOT EXISTS(
                       SELECT 1 FROM product_fulfillment_jobs f
                       WHERE f.run_id=r.id AND f.itinerary_id=r.result_itinerary_id
                     )
                   ORDER BY r.finished_at,r.id"""
            ).fetchall()
        result = []
        for row in rows:
            try:
                snapshot = json.loads(row["request_snapshot_json"])
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            context = snapshot.get("catalog_context")
            if not isinstance(context, dict):
                continue
            required = (
                "package_id", "schema_version", "content_version", "route_id"
            )
            if not all(str(context.get(key) or "").strip() for key in required):
                continue
            if created_after is not None and not self._is_run_new_or_complete(
                row, context, created_after
            ):
                continue
            result.append(
                {
                    "owner_id": row["user_id"],
                    "run_id": row["id"],
                    "itinerary_id": row["result_itinerary_id"],
                    "route_id": context["route_id"],
                    "package_id": context["package_id"],
                    "schema_version": context["schema_version"],
                    "content_version": context["content_version"],
                }
            )
        return tuple(result)

    def _is_run_new_or_complete(
        self,
        run: sqlite3.Row,
        context: dict[str, Any],
        created_after: str,
    ) -> bool:
        with get_conn(self.db_path) as conn:
            is_new = conn.execute(
                "SELECT julianday(?) > julianday(?)",
                (run["finished_at"], created_after),
            ).fetchone()[0]
            if is_new:
                return True
            chain = conn.execute(
                """SELECT 1
                   FROM story_package_snapshots s
                   JOIN experience_package_snapshots e
                     ON e.run_id=s.run_id AND e.itinerary_id=s.itinerary_id
                    AND e.story_package_id=s.package_id
                    AND e.story_snapshot_hash=s.snapshot_hash
                   JOIN local_resource_package_snapshots p
                     ON p.run_id=e.run_id AND p.itinerary_id=e.itinerary_id
                    AND p.story_package_id=s.package_id
                    AND p.story_snapshot_hash=s.snapshot_hash
                    AND p.experience_package_id=e.package_id
                    AND p.experience_snapshot_hash=e.snapshot_hash
                   WHERE s.run_id=? AND s.itinerary_id=?
                     AND s.catalog_package_id=? AND e.catalog_package_id=?
                     AND p.catalog_package_id=?
                     AND s.schema_version=? AND e.schema_version=?
                     AND p.schema_version=?
                     AND s.content_version=? AND e.content_version=?
                     AND p.content_version=?
                   LIMIT 1""",
                (
                    run["id"], run["result_itinerary_id"],
                    context["package_id"], context["package_id"],
                    context["package_id"], context["schema_version"],
                    context["schema_version"], context["schema_version"],
                    context["content_version"], context["content_version"],
                    context["content_version"],
                ),
            ).fetchone()
        return chain is not None

    def reset_running_for_startup(self) -> int:
        now = _now()
        with get_conn(self.db_path) as conn:
            result = conn.execute(
                """UPDATE product_fulfillment_jobs SET
                   story_status=CASE WHEN story_status='running' THEN 'pending' ELSE story_status END,
                   experience_status=CASE WHEN experience_status='running' THEN 'pending' ELSE experience_status END,
                   resources_status=CASE WHEN resources_status='running' THEN 'pending' ELSE resources_status END,
                   status='pending',updated_at=?
                   WHERE status='running'""",
                (now,),
            )
        return result.rowcount

    def claim_stage(self, job_id: str, stage: FulfillmentStage) -> bool:
        column = f"{stage.value}_status"
        now = _now()
        with get_conn(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            result = conn.execute(
                f"""UPDATE product_fulfillment_jobs SET {column}='running',
                    status='running',started_at=COALESCE(started_at,?),updated_at=?,
                    attempt_count=attempt_count+1,last_error_stage=NULL,
                    last_error_class=NULL,last_error_code=NULL,last_error_message=NULL
                    WHERE job_id=? AND {column}='pending'""",
                (now, now, job_id),
            )
        return result.rowcount == 1

    def complete_stage(
        self,
        job_id: str,
        stage: FulfillmentStage,
        status: FulfillmentStageStatus,
        snapshot: FulfillmentSnapshotRef | None = None,
    ) -> ProductFulfillmentJob:
        if status not in {
            FulfillmentStageStatus.SUCCEEDED,
            FulfillmentStageStatus.SKIPPED,
            FulfillmentStageStatus.NOT_APPLICABLE,
        }:
            raise FulfillmentTransitionError("invalid successful stage status")
        status_column = f"{stage.value}_status"
        id_column = {
            FulfillmentStage.STORY: "story_package_id",
            FulfillmentStage.EXPERIENCE: "experience_package_id",
            FulfillmentStage.RESOURCES: "resource_package_id",
        }[stage]
        hash_column = {
            FulfillmentStage.STORY: "story_snapshot_hash",
            FulfillmentStage.EXPERIENCE: "experience_snapshot_hash",
            FulfillmentStage.RESOURCES: "resource_snapshot_hash",
        }[stage]
        if status is FulfillmentStageStatus.SUCCEEDED and snapshot is None:
            raise FulfillmentTransitionError("succeeded stage requires snapshot identity")
        now = _now()
        with get_conn(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT * FROM product_fulfillment_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if current is None:
                raise FulfillmentJobNotFound("fulfillment job not found")
            if current[status_column] not in {"running", "pending"}:
                raise FulfillmentTransitionError("stage is not completable")
            values = {
                "story_status": current["story_status"],
                "experience_status": current["experience_status"],
                "resources_status": current["resources_status"],
            }
            values[status_column] = status.value
            overall = _overall_status(tuple(values.values()))
            finished = now if overall in {
                ProductFulfillmentStatus.SUCCEEDED,
                ProductFulfillmentStatus.PARTIAL,
                ProductFulfillmentStatus.FAILED,
            } else None
            conn.execute(
                f"""UPDATE product_fulfillment_jobs SET {status_column}=?,
                    {id_column}=COALESCE(?,{id_column}),
                    {hash_column}=COALESCE(?,{hash_column}),status=?,updated_at=?,
                    finished_at=? WHERE job_id=?""",
                (
                    status.value,
                    snapshot.package_id if snapshot else None,
                    snapshot.snapshot_hash if snapshot else None,
                    overall.value, now, finished, job_id,
                ),
            )
        return self.get_internal(job_id)

    def fail_stage(
        self,
        job_id: str,
        stage: FulfillmentStage,
        *,
        error_class: str,
        error_code: str,
        error_message: str,
    ) -> ProductFulfillmentJob:
        now = _now()
        status_column = f"{stage.value}_status"
        downstream = {
            FulfillmentStage.STORY: "experience_status='blocked',resources_status='blocked',",
            FulfillmentStage.EXPERIENCE: "resources_status='blocked',",
            FulfillmentStage.RESOURCES: "",
        }[stage]
        with get_conn(self.db_path) as conn:
            result = conn.execute(
                f"""UPDATE product_fulfillment_jobs SET {status_column}='failed',
                    {downstream} status=?,updated_at=?,finished_at=?,last_error_stage=?,
                    last_error_class=?,last_error_code=?,last_error_message=?
                    WHERE job_id=? AND {status_column}='running'""",
                (
                    (
                        ProductFulfillmentStatus.FAILED.value
                        if stage is FulfillmentStage.STORY
                        else ProductFulfillmentStatus.PARTIAL.value
                    ),
                    now, now, stage.value, error_class[:200], error_code[:200],
                    redact_sensitive_text(error_message)[:500], job_id,
                ),
            )
        if result.rowcount != 1:
            raise FulfillmentTransitionError("stage is not fail-able")
        return self.get_internal(job_id)

    def retry_failed(self, owner_id: str, run_id: str) -> ProductFulfillmentJob:
        with get_conn(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM product_fulfillment_jobs WHERE owner_id=? AND run_id=?",
                (owner_id, run_id),
            ).fetchone()
            job = _decode(row)
            stage = next(
                (
                    item for item in FulfillmentStage
                    if job.stage_status(item) is FulfillmentStageStatus.FAILED
                ),
                None,
            )
            if stage is None:
                raise FulfillmentTransitionError("no failed stage is retryable")
            updates = {
                FulfillmentStage.STORY: (
                    "story_status='pending',experience_status='pending',resources_status='pending'"
                ),
                FulfillmentStage.EXPERIENCE: (
                    "experience_status='pending',resources_status='pending'"
                ),
                FulfillmentStage.RESOURCES: "resources_status='pending'",
            }[stage]
            now = _now()
            conn.execute(
                f"""UPDATE product_fulfillment_jobs SET {updates},status='pending',
                    updated_at=?,finished_at=NULL,last_error_stage=NULL,
                    last_error_class=NULL,last_error_code=NULL,last_error_message=NULL
                    WHERE job_id=?""",
                (now, job.job_id),
            )
        return self.get_internal(job.job_id)
