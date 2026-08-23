"""Independent, durable orchestration for post-planning product layers."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from app.catalog.loader import FileCatalogLoader
from app.catalog.models import (
    ExperienceVerificationStatus,
    LocalResourceType,
    PoiProvider,
    StoryVerificationStatus,
)
from app.catalog.repository import CatalogRepository
from app.core.database import get_conn
from app.experience import (
    ExperienceBindingRequest,
    ExperienceGenerationRequest,
    ExperienceGenerationService,
    ExperienceItineraryBinder,
    ExperiencePackageSnapshotRepository,
    ExperienceSnapshotError,
)
from app.knowledge.models import CatalogVersionSnapshot
from app.planning.route_feasibility import TravelTimeMatrix
from app.product.catalog import CatalogProductService
from app.product.fulfillment_models import (
    FulfillmentSnapshotRef,
    FulfillmentStage,
    FulfillmentStageResult,
    FulfillmentStageStatus,
    ProductFulfillmentJob,
    ProductFulfillmentStatus,
)
from app.product.fulfillment_repository import (
    FulfillmentJobNotFound,
    FulfillmentTransitionError,
    ProductFulfillmentRepository,
)
from app.providers.amap import AmapRuntimeResourceProvider
from app.providers.amap.travel_time import AmapTravelTimeProvider
from app.resources import (
    BudgetPreference,
    LocalResourcePackageSnapshotRepository,
    LocalResourceRecommendationEngine,
    LocalResourceRecommendationRequest,
    LocalResourceSnapshotError,
    ResourceDiscoveryService,
    build_local_resource_package,
    itinerary_stop_id,
    recommendation_candidate_from_catalog,
    recommendation_candidate_from_runtime,
)
from app.story import (
    StoryBindingRequest,
    StoryGenerationRequest,
    StoryGenerationService,
    StoryItineraryBinder,
    StoryPackageSnapshotRepository,
    StorySnapshotError,
)


CATALOG_ROOT = Path(__file__).resolve().parents[2] / "content" / "catalog"


class FulfillmentStageError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        self.code = code
        self.public_message = message
        self.retryable = retryable
        super().__init__(message)


class FulfillmentStageRunner(Protocol):
    async def story(self, job: ProductFulfillmentJob) -> FulfillmentStageResult: ...

    async def experience(
        self, job: ProductFulfillmentJob
    ) -> FulfillmentStageResult: ...

    async def resources(self, job: ProductFulfillmentJob) -> FulfillmentStageResult: ...


def _is_missing_snapshot(exc: Exception) -> bool:
    return "not found for formal run" in str(exc)


def _is_transient(exc: BaseException) -> bool:
    transient_markers = (
        "timeout", "timed out", "429", "rate limit", "connection reset",
        "connection error", "http 500", "http 502", "http 503", "http 504",
    )
    current: BaseException | None = exc
    while current is not None:
        text = f"{type(current).__name__}: {current}".casefold()
        if any(marker in text for marker in transient_markers):
            return True
        current = current.__cause__
    return False


class ProductionFulfillmentStageRunner:
    """Reuse M3-M5 engines while enforcing the frozen snapshot chain."""

    def __init__(
        self,
        *,
        db_path: str | Path | None = None,
        catalog_loader: Callable[[], CatalogRepository] | None = None,
        amap_api_key: str | None = None,
    ) -> None:
        self.db_path = db_path
        self._catalog_loader = catalog_loader or (
            lambda: FileCatalogLoader(CATALOG_ROOT).load()
        )
        self._amap_api_key = amap_api_key

    def is_trigger_eligible(self, item: dict[str, Any]) -> bool:
        """Reject known non-ready routes; unavailable frozen versions become jobs that fail safely."""
        repository = self._catalog_loader()
        package = repository.get_package(item["package_id"])
        if package is None:
            return True
        manifest = package.manifest
        if (
            manifest.schema_version != item["schema_version"]
            or manifest.content_version != item["content_version"]
        ):
            return True
        route = CatalogProductService(repository).get_route(
            item["package_id"], item["route_id"]
        )
        return bool(route and route["availability"] == "ready")

    def _catalog(self, job: ProductFulfillmentJob) -> CatalogRepository:
        repository = self._catalog_loader()
        package = repository.get_package(job.package_id)
        if package is None or not package.manifest.enabled:
            raise FulfillmentStageError(
                "CATALOG_SNAPSHOT_UNAVAILABLE",
                "旅程使用的内容版本当前不可用。",
            )
        manifest = package.manifest
        if (
            manifest.schema_version != job.schema_version
            or manifest.content_version != job.content_version
        ):
            raise FulfillmentStageError(
                "CATALOG_SNAPSHOT_UNAVAILABLE",
                "旅程使用的内容版本当前不可用。",
            )
        route = repository.get_route(job.route_id)
        route_view = CatalogProductService(repository).get_route(
            job.package_id, job.route_id
        )
        if route is None or route_view is None or route_view["availability"] != "ready":
            raise FulfillmentStageError(
                "ROUTE_NOT_PRODUCTION_READY", "主题线路尚未满足正式生成条件。"
            )
        return repository

    def _run_inputs(self, job: ProductFulfillmentJob) -> tuple[dict, dict]:
        with get_conn(self.db_path) as conn:
            run = conn.execute(
                "SELECT * FROM runs WHERE id=? AND user_id=?", (job.run_id, job.owner_id)
            ).fetchone()
            itinerary = conn.execute(
                "SELECT plan_json,user_id FROM itineraries WHERE id=?",
                (job.itinerary_id,),
            ).fetchone()
        if (
            run is None
            or itinerary is None
            or itinerary["user_id"] != job.owner_id
            or run["status"] != "succeeded"
            or run["result_itinerary_id"] != job.itinerary_id
        ):
            raise FulfillmentStageError(
                "RUN_ITINERARY_MISMATCH", "正式行程与生成任务不匹配。"
            )
        try:
            return json.loads(run["request_snapshot_json"]), json.loads(
                itinerary["plan_json"]
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise FulfillmentStageError(
                "RUN_SNAPSHOT_CORRUPTED", "正式行程快照无法读取。"
            ) from exc

    @staticmethod
    def _version(job: ProductFulfillmentJob) -> CatalogVersionSnapshot:
        return CatalogVersionSnapshot(
            package_id=job.package_id,
            schema_version=job.schema_version,
            content_version=job.content_version,
        )

    @staticmethod
    def _unique(items: tuple[Any, ...], label: str) -> Any:
        if len(items) != 1:
            raise FulfillmentStageError(
                f"{label.upper()}_RESOLUTION_FAILED",
                f"线路未能唯一解析到可用的{label}配置。",
            )
        return items[0]

    def _story_blueprint(self, repository, job):
        return self._unique(
            tuple(
                item
                for item in repository.list_stories(job.route_id)
                if item.enabled
                and item.verification_status is StoryVerificationStatus.VERIFIED
            ),
            "story",
        )

    def _experience_blueprint(self, repository, job, story_id):
        return self._unique(
            tuple(
                item
                for item in repository.list_experiences(
                    route_id=job.route_id, story_id=story_id
                )
                if item.enabled
                and item.verification_status
                is ExperienceVerificationStatus.VERIFIED
            ),
            "experience",
        )

    async def story(self, job: ProductFulfillmentJob) -> FulfillmentStageResult:
        repository = self._catalog(job)
        blueprint = self._story_blueprint(repository, job)
        snapshots = StoryPackageSnapshotRepository(self.db_path)
        try:
            existing = snapshots.load_for_run(
                job.run_id,
                job.itinerary_id,
                blueprint.story_id,
                expected_catalog_version=self._version(job),
            )
        except StorySnapshotError as exc:
            if not _is_missing_snapshot(exc):
                raise FulfillmentStageError(
                    "SNAPSHOT_CHAIN_MISMATCH", "故事快照身份校验失败。"
                ) from exc
        else:
            return FulfillmentStageResult(
                status=FulfillmentStageStatus.SUCCEEDED,
                snapshot=FulfillmentSnapshotRef(
                    package_id=existing.package.package_id,
                    snapshot_hash=existing.snapshot_hash,
                ),
            )
        request_snapshot, itinerary = self._run_inputs(job)

        def generate_and_persist():
            generated = StoryGenerationService(repository).generate(
                StoryGenerationRequest(story_id=blueprint.story_id)
            )
            package = StoryItineraryBinder(repository).bind(
                generated,
                StoryBindingRequest(
                    itinerary_id=job.itinerary_id,
                    run_id=job.run_id,
                    route_id=job.route_id,
                    itinerary=itinerary,
                    weather=tuple(request_snapshot.get("weather_forecast") or ()),
                    user_profile={},
                ),
            )
            return snapshots.save(package)

        saved = await asyncio.to_thread(generate_and_persist)
        return FulfillmentStageResult(
            status=FulfillmentStageStatus.SUCCEEDED,
            snapshot=FulfillmentSnapshotRef(
                package_id=saved.package.package_id,
                snapshot_hash=saved.snapshot_hash,
            ),
        )

    async def experience(self, job: ProductFulfillmentJob) -> FulfillmentStageResult:
        repository = self._catalog(job)
        story_blueprint = self._story_blueprint(repository, job)
        try:
            story = StoryPackageSnapshotRepository(self.db_path).load_for_run(
                job.run_id,
                job.itinerary_id,
                story_blueprint.story_id,
                expected_catalog_version=self._version(job),
            )
        except StorySnapshotError as exc:
            raise FulfillmentStageError(
                "SNAPSHOT_CHAIN_MISMATCH", "故事快照链与任务记录不一致。"
            ) from exc
        if (
            story.package.package_id != job.story_package_id
            or story.snapshot_hash != job.story_snapshot_hash
        ):
            raise FulfillmentStageError(
                "SNAPSHOT_CHAIN_MISMATCH", "故事快照链与任务记录不一致。"
            )
        blueprint = self._experience_blueprint(
            repository, job, story.package.story_id
        )
        snapshots = ExperiencePackageSnapshotRepository(self.db_path)
        try:
            existing = snapshots.load_for_run(
                job.run_id,
                job.itinerary_id,
                story.package.package_id,
                expected_catalog_version=self._version(job),
            )
        except ExperienceSnapshotError as exc:
            if not _is_missing_snapshot(exc):
                raise FulfillmentStageError(
                    "SNAPSHOT_CHAIN_MISMATCH", "互动快照身份校验失败。"
                ) from exc
        else:
            if existing.package.experience_id != blueprint.experience_id:
                raise FulfillmentStageError(
                    "SNAPSHOT_CHAIN_MISMATCH", "互动快照配置身份不一致。"
                )
            return FulfillmentStageResult(
                status=FulfillmentStageStatus.SUCCEEDED,
                snapshot=FulfillmentSnapshotRef(
                    package_id=existing.package.package_id,
                    snapshot_hash=existing.snapshot_hash,
                ),
            )
        request_snapshot, itinerary = self._run_inputs(job)

        def generate_and_persist():
            draft = ExperienceGenerationService(repository, story.package).generate(
                ExperienceGenerationRequest(experience_id=blueprint.experience_id)
            )
            package = ExperienceItineraryBinder(repository).bind(
                draft,
                story.package,
                ExperienceBindingRequest(
                    itinerary_id=job.itinerary_id,
                    run_id=job.run_id,
                    route_id=job.route_id,
                    itinerary=itinerary,
                    weather=tuple(request_snapshot.get("weather_forecast") or ()),
                ),
            )
            return snapshots.save(package)

        saved = await asyncio.to_thread(generate_and_persist)
        return FulfillmentStageResult(
            status=FulfillmentStageStatus.SUCCEEDED,
            snapshot=FulfillmentSnapshotRef(
                package_id=saved.package.package_id,
                snapshot_hash=saved.snapshot_hash,
            ),
        )

    async def resources(self, job: ProductFulfillmentJob) -> FulfillmentStageResult:
        repository = self._catalog(job)
        route_view = CatalogProductService(repository).get_route(
            job.package_id, job.route_id
        )
        if not route_view or not route_view["capabilities"].get("resources_available"):
            return FulfillmentStageResult(
                status=FulfillmentStageStatus.NOT_APPLICABLE
            )
        story_blueprint = self._story_blueprint(repository, job)
        try:
            story = StoryPackageSnapshotRepository(self.db_path).load_for_run(
                job.run_id,
                job.itinerary_id,
                story_blueprint.story_id,
                expected_catalog_version=self._version(job),
            )
            experience = ExperiencePackageSnapshotRepository(self.db_path).load_for_run(
                job.run_id,
                job.itinerary_id,
                story.package.package_id,
                expected_catalog_version=self._version(job),
            )
        except (StorySnapshotError, ExperienceSnapshotError) as exc:
            raise FulfillmentStageError(
                "SNAPSHOT_CHAIN_MISMATCH", "附近资源的上游快照链不一致。"
            ) from exc
        if (
            story.package.package_id != job.story_package_id
            or story.snapshot_hash != job.story_snapshot_hash
            or experience.package.package_id != job.experience_package_id
            or experience.snapshot_hash != job.experience_snapshot_hash
        ):
            raise FulfillmentStageError(
                "SNAPSHOT_CHAIN_MISMATCH", "附近资源的上游快照链不一致。"
            )
        snapshots = LocalResourcePackageSnapshotRepository(self.db_path)
        try:
            existing = snapshots.load_for_run(job.run_id, job.itinerary_id)
        except LocalResourceSnapshotError as exc:
            if not _is_missing_snapshot(exc):
                raise FulfillmentStageError(
                    "SNAPSHOT_CHAIN_MISMATCH", "附近资源快照身份校验失败。"
                ) from exc
        else:
            package = existing.package
            if (
                package.story_snapshot_hash != story.snapshot_hash
                or package.experience_snapshot_hash != experience.snapshot_hash
                or package.package_id != job.package_id
                or package.schema_version != job.schema_version
                or package.content_version != job.content_version
            ):
                raise FulfillmentStageError(
                    "SNAPSHOT_CHAIN_MISMATCH", "附近资源快照链与任务记录不一致。"
                )
            return FulfillmentStageResult(
                status=FulfillmentStageStatus.SUCCEEDED,
                snapshot=FulfillmentSnapshotRef(
                    package_id=package.resource_package_id,
                    snapshot_hash=existing.snapshot_hash,
                ),
            )

        request_snapshot, itinerary = self._run_inputs(job)
        key = self._amap_api_key or os.getenv("AMAP_API_KEY", "").strip()
        if not key:
            raise FulfillmentStageError(
                "RESOURCE_PROVIDER_UNAVAILABLE",
                "附近资源服务暂时无法连接。",
            )
        provider = AmapRuntimeResourceProvider(key)
        discovery = ResourceDiscoveryService(provider)
        runtime_candidates = []
        seen_locations: set[tuple[float, float]] = set()
        for day in itinerary.get("days", []):
            day_number = int(day.get("day") or 0)
            for index, item in enumerate(day.get("timeline", [])):
                location = item.get("location")
                if not isinstance(location, dict):
                    continue
                try:
                    point = {
                        "lng": float(location["lng"]),
                        "lat": float(location["lat"]),
                    }
                except (KeyError, TypeError, ValueError):
                    continue
                identity = (point["lng"], point["lat"])
                if identity in seen_locations:
                    continue
                seen_locations.add(identity)
                runtime_candidates.extend(
                    await discovery.discover_restaurants(
                        point,
                        radius_m=5000,
                        limit=20,
                        related_stop_id=itinerary_stop_id(day_number, index),
                    )
                )
        candidates = [
            recommendation_candidate_from_runtime(item)
            for item in runtime_candidates
        ]
        now = datetime.now(timezone.utc)
        route = repository.get_route(job.route_id)
        for anchor_id in route.anchor_ids:
            for resource in repository.list_resources(anchor_id=anchor_id):
                candidate = recommendation_candidate_from_catalog(
                    resource,
                    repository,
                    as_of=now,
                    freshness_max_age=timedelta(days=30),
                )
                if candidate is not None:
                    candidates.append(candidate)
        unique_candidates = tuple(
            {
                (item.provider, item.external_poi_id): item for item in candidates
            }.values()
        )
        matrix = TravelTimeMatrix(
            {PoiProvider.AMAP: AmapTravelTimeProvider(key)}
        )
        budget = {
            "经济实用": BudgetPreference.ECONOMY,
            "均衡舒适": BudgetPreference.BALANCED,
            "品质优先": BudgetPreference.PREMIUM,
        }.get(str(request_snapshot.get("trip_budget") or ""), BudgetPreference.UNSPECIFIED)
        result = await LocalResourceRecommendationEngine(matrix).recommend(
            LocalResourceRecommendationRequest(
                run_id=job.run_id,
                itinerary_id=job.itinerary_id,
                story_package_id=story.package.package_id,
                experience_package_id=experience.package.package_id,
                resource_types=(LocalResourceType.RESTAURANT,),
                user_preferences=tuple(
                    filter(
                        None,
                        (str(request_snapshot.get("food_preference") or "").strip(),),
                    )
                ),
                budget_preference=budget,
            ),
            itinerary=itinerary,
            candidates=unique_candidates,
            story_package=story.package,
            experience_package=experience.package,
        )
        package = build_local_resource_package(
            catalog_version=self._version(job),
            run_id=job.run_id,
            itinerary_id=job.itinerary_id,
            story_package_id=story.package.package_id,
            story_snapshot_hash=story.snapshot_hash,
            experience_package_id=experience.package.package_id,
            experience_snapshot_hash=experience.snapshot_hash,
            resources=unique_candidates,
            result=result,
        )
        saved = snapshots.save(package)
        return FulfillmentStageResult(
            status=FulfillmentStageStatus.SUCCEEDED,
            snapshot=FulfillmentSnapshotRef(
                package_id=saved.package.resource_package_id,
                snapshot_hash=saved.snapshot_hash,
            ),
        )


class ProductFulfillmentOrchestrator:
    def __init__(
        self,
        repository: ProductFulfillmentRepository,
        runner: FulfillmentStageRunner,
    ) -> None:
        self.repository = repository
        self.runner = runner

    async def execute(self, job_id: str) -> ProductFulfillmentJob:
        for stage in FulfillmentStage:
            job = self.repository.get_internal(job_id)
            if job.stage_status(stage) is not FulfillmentStageStatus.PENDING:
                if job.stage_status(stage) in {
                    FulfillmentStageStatus.FAILED,
                    FulfillmentStageStatus.BLOCKED,
                }:
                    return job
                continue
            if not self.repository.claim_stage(job_id, stage):
                return self.repository.get_internal(job_id)
            try:
                result = await self._run_stage(stage, self.repository.get_internal(job_id))
            except Exception as exc:  # noqa: BLE001
                error = exc if isinstance(exc, FulfillmentStageError) else FulfillmentStageError(
                    f"{stage.value.upper()}_GENERATION_FAILED",
                    {
                        FulfillmentStage.STORY: "故事生成未完成。",
                        FulfillmentStage.EXPERIENCE: "互动生成未完成。",
                        FulfillmentStage.RESOURCES: "附近资源暂时无法核验。",
                    }[stage],
                    retryable=_is_transient(exc),
                )
                return self.repository.fail_stage(
                    job_id,
                    stage,
                    error_class=type(exc).__name__,
                    error_code=error.code,
                    error_message=error.public_message,
                )
            self.repository.complete_stage(job_id, stage, result.status, result.snapshot)
        return self.repository.get_internal(job_id)

    async def _run_stage(
        self, stage: FulfillmentStage, job: ProductFulfillmentJob
    ) -> FulfillmentStageResult:
        operation = getattr(self.runner, stage.value)
        try:
            return await operation(job)
        except Exception as exc:  # noqa: BLE001
            retryable = (
                exc.retryable if isinstance(exc, FulfillmentStageError) else _is_transient(exc)
            )
            if not retryable:
                raise
            return await operation(job)


class ProductFulfillmentExecutor:
    """Single-node background executor with durable DB reconciliation."""

    def __init__(
        self,
        repository: ProductFulfillmentRepository,
        orchestrator: ProductFulfillmentOrchestrator,
        *,
        poll_interval: float = 0.5,
        execution_limit: int = 1,
        shutdown_grace_period: float = 1.0,
    ) -> None:
        self.repository = repository
        self.orchestrator = orchestrator
        self.poll_interval = max(0.05, poll_interval)
        self.shutdown_grace_period = max(0.0, shutdown_grace_period)
        self._capacity = asyncio.Semaphore(max(1, execution_limit))
        self._loop_task: asyncio.Task | None = None
        self._tasks: dict[str, asyncio.Task] = {}
        self._wake = asyncio.Event()
        self._stopping = False
        self._activation_time: str | None = None

    async def start(self) -> None:
        if self._loop_task and not self._loop_task.done():
            return
        self._stopping = False
        self._activation_time = datetime.now(timezone.utc).isoformat()
        await asyncio.to_thread(self.repository.reset_running_for_startup)
        self._loop_task = asyncio.create_task(
            self._loop(), name="product-fulfillment-executor"
        )
        self.notify()

    async def stop(self) -> None:
        self._stopping = True
        self.notify()
        if self._loop_task is not None:
            await self._loop_task
            self._loop_task = None
        tasks = tuple(self._tasks.values())
        if tasks:
            _, pending = await asyncio.wait(
                tasks, timeout=self.shutdown_grace_period
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

    def notify(self) -> None:
        self._wake.set()

    async def retry(self, owner_id: str, run_id: str) -> ProductFulfillmentJob:
        job = await asyncio.to_thread(
            self.repository.retry_failed, owner_id, run_id
        )
        self.notify()
        return job

    async def reconcile_once(self) -> tuple[str, ...]:
        eligible = await asyncio.to_thread(
            self.repository.discover_eligible_runs,
            created_after=self._activation_time,
        )
        for item in eligible:
            trigger_check = getattr(self.orchestrator.runner, "is_trigger_eligible", None)
            if trigger_check is not None and not await asyncio.to_thread(
                trigger_check, item
            ):
                continue
            await asyncio.to_thread(self.repository.create, **item)
        jobs = await asyncio.to_thread(self.repository.list_recoverable)
        scheduled = []
        for job in jobs:
            existing = self._tasks.get(job.job_id)
            if existing is not None and not existing.done():
                continue
            task = asyncio.create_task(
                self._execute_bounded(job.job_id),
                name=f"fulfillment:{job.job_id}",
            )
            self._tasks[job.job_id] = task
            task.add_done_callback(
                lambda _task, identity=job.job_id: self._tasks.pop(identity, None)
            )
            scheduled.append(job.job_id)
        return tuple(scheduled)

    async def _execute_bounded(self, job_id: str) -> ProductFulfillmentJob:
        async with self._capacity:
            return await self.orchestrator.execute(job_id)

    async def _loop(self) -> None:
        while not self._stopping:
            await self.reconcile_once()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self.poll_interval)
            except TimeoutError:
                pass
            self._wake.clear()


def build_product_fulfillment_executor(
    *, db_path: str | Path | None = None
) -> ProductFulfillmentExecutor:
    repository = ProductFulfillmentRepository(db_path)
    runner = ProductionFulfillmentStageRunner(db_path=db_path)
    orchestrator = ProductFulfillmentOrchestrator(repository, runner)
    return ProductFulfillmentExecutor(repository, orchestrator)
