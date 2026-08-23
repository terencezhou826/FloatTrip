from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest

from app.core.database import configure_database, get_conn, get_db_path, init_db
from app.product.fulfillment import (
    FulfillmentStageError,
    ProductFulfillmentExecutor,
    ProductFulfillmentOrchestrator,
    ProductionFulfillmentStageRunner,
)
from app.product.catalog import CatalogProductService
from app.product.fulfillment_models import (
    FulfillmentSnapshotRef,
    FulfillmentStage,
    FulfillmentStageResult,
    FulfillmentStageStatus,
    ProductFulfillmentStatus,
)
from app.product.fulfillment_repository import (
    FulfillmentJobNotFound,
    FulfillmentTransitionError,
    ProductFulfillmentRepository,
)
from app.story import StoryGenerationService, StoryPackageSnapshotRepository
from tests.test_story_binding import _bind as bind_story


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc).isoformat()
ROUTES = (
    "changzhi.route.jingwei-fajiushan",
    "changzhi.route.nuwa-tiantaishan",
    "changzhi.route.shennong-laodingshan",
    "changzhi.route.houyi-laoyeshan",
)


@pytest.fixture()
def fulfillment_db(tmp_path):
    original = get_db_path()
    path = tmp_path / "fulfillment.db"
    configure_database(path)
    init_db()
    try:
        yield path
    finally:
        configure_database(original)


def _formal_run(
    run_id: str,
    itinerary_id: str,
    *,
    route_id: str | None,
    owner_id: str = "owner",
    finished_at: str = NOW,
) -> None:
    context = (
        {
            "package_id": "shanxi.changzhi",
            "schema_version": "1.0",
            "content_version": "0.6.0",
            "route_id": route_id,
        }
        if route_id
        else None
    )
    request = {"catalog_context": context} if context else {}
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(id,username,password_hash,created_at) VALUES(?,?,?,?)",
            (owner_id, owner_id, "unused", NOW),
        )
        conn.execute(
            """INSERT INTO itineraries(
               id,user_id,query,destination,plan_json,created_at)
               VALUES(?,?,?,'长治市','{}',?)""",
            (itinerary_id, owner_id, "trip", NOW),
        )
        conn.execute(
            """INSERT INTO runs(
               id,user_id,kind,status,concurrency_key,request_snapshot_json,
               result_itinerary_id,created_at,queued_at,started_at,finished_at,updated_at)
               VALUES(?,?,'travel_plan','succeeded',?,?,?, ?,?,?,?,?)""",
            (
                run_id,
                owner_id,
                run_id,
                json.dumps(request),
                itinerary_id,
                NOW,
                NOW,
                NOW,
                finished_at,
                NOW,
            ),
        )


def _insert_complete_snapshot_chain(run_id: str, itinerary_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO story_package_snapshots VALUES(
               ?,?,?,?,'1.0','shanxi.changzhi','1.0','0.6.0','{}',?,?)""",
            (f"story-{run_id}", run_id, itinerary_id, "story", "a" * 64, NOW),
        )
        conn.execute(
            """INSERT INTO experience_package_snapshots VALUES(
               ?,?,?,?,'1.0',?,?,'shanxi.changzhi','1.0','0.6.0','{}',?,?)""",
            (
                f"experience-{run_id}", run_id, itinerary_id, "experience",
                f"story-{run_id}", "a" * 64, "b" * 64, NOW,
            ),
        )
        conn.execute(
            """INSERT INTO local_resource_package_snapshots VALUES(
               ?,?,?,?,?,?,?,'shanxi.changzhi','1.0','0.6.0','{}',?,?)""",
            (
                f"resources-{run_id}", run_id, itinerary_id, f"story-{run_id}",
                "a" * 64, f"experience-{run_id}", "b" * 64, "c" * 64, NOW,
            ),
        )


def _create_job(repository, run_id="run-1", itinerary_id="itinerary-1", route_id=ROUTES[0]):
    return repository.create(
        owner_id="owner",
        run_id=run_id,
        itinerary_id=itinerary_id,
        route_id=route_id,
        package_id="shanxi.changzhi",
        schema_version="1.0",
        content_version="0.6.0",
    )


def _ref(prefix: str) -> FulfillmentSnapshotRef:
    hash_char = {"story": "a", "experience": "b", "resources": "c"}[prefix]
    return FulfillmentSnapshotRef(
        package_id=f"{prefix}.package", snapshot_hash=(hash_char * 64)
    )


class FakeRunner:
    def __init__(
        self,
        *,
        fail: str | None = None,
        transient: str | None = None,
        resources_status: FulfillmentStageStatus = FulfillmentStageStatus.SUCCEEDED,
    ):
        self.fail = fail
        self.transient = transient
        self.resources_status = resources_status
        self.calls: list[tuple[str, str]] = []

    async def _stage(self, stage, job):
        self.calls.append((stage, job.route_id))
        if self.transient == stage:
            self.transient = None
            raise FulfillmentStageError("TRANSIENT", "temporary", retryable=True)
        if self.fail == stage:
            raise FulfillmentStageError(f"{stage.upper()}_FAILED", f"{stage} failed")
        return FulfillmentStageResult(
            status=FulfillmentStageStatus.SUCCEEDED,
            snapshot=_ref(stage),
        )

    async def story(self, job):
        return await self._stage("story", job)

    async def experience(self, job):
        return await self._stage("experience", job)

    async def resources(self, job):
        if self.resources_status is not FulfillmentStageStatus.SUCCEEDED:
            self.calls.append(("resources", job.route_id))
            return FulfillmentStageResult(status=self.resources_status)
        return await self._stage("resources", job)


def test_repository_create_is_idempotent_and_owner_isolated(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    first = _create_job(repository)
    second = _create_job(repository)

    assert first.job_id == second.job_id
    with get_conn(fulfillment_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM product_fulfillment_jobs").fetchone()[0] == 1
    with pytest.raises(FulfillmentJobNotFound):
        repository.get("other-owner", "run-1")


def test_repository_stage_transitions_and_snapshot_identity(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = _create_job(repository)

    assert repository.claim_stage(job.job_id, FulfillmentStage.STORY)
    assert not repository.claim_stage(job.job_id, FulfillmentStage.STORY)
    updated = repository.complete_stage(
        job.job_id,
        FulfillmentStage.STORY,
        FulfillmentStageStatus.SUCCEEDED,
        _ref("story"),
    )

    assert updated.story_status is FulfillmentStageStatus.SUCCEEDED
    assert updated.story_package_id == "story.package"
    assert updated.story_snapshot_hash == "a" * 64
    assert updated.status is ProductFulfillmentStatus.PENDING


def test_repository_failure_is_safe_and_retry_preserves_successful_upstream(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = _create_job(repository)
    repository.claim_stage(job.job_id, FulfillmentStage.STORY)
    repository.complete_stage(
        job.job_id, FulfillmentStage.STORY,
        FulfillmentStageStatus.SUCCEEDED, _ref("story"),
    )
    repository.claim_stage(job.job_id, FulfillmentStage.EXPERIENCE)
    failed = repository.fail_stage(
        job.job_id,
        FulfillmentStage.EXPERIENCE,
        error_class="ProviderError",
        error_code="EXPERIENCE_FAILED",
        error_message="safe public text Authorization: Bearer secret-token",
    )

    assert failed.status is ProductFulfillmentStatus.PARTIAL
    assert failed.story_status is FulfillmentStageStatus.SUCCEEDED
    assert failed.experience_status is FulfillmentStageStatus.FAILED
    assert failed.resources_status is FulfillmentStageStatus.BLOCKED
    assert "secret-token" not in (failed.last_error_message or "")
    assert "<redacted>" in (failed.last_error_message or "")

    retried = repository.retry_failed("owner", "run-1")
    assert retried.story_status is FulfillmentStageStatus.SUCCEEDED
    assert retried.experience_status is FulfillmentStageStatus.PENDING
    assert retried.resources_status is FulfillmentStageStatus.PENDING


def test_startup_recovery_resets_running_stage_only(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = _create_job(repository)
    repository.claim_stage(job.job_id, FulfillmentStage.STORY)

    assert repository.reset_running_for_startup() == 1
    recovered = repository.get_internal(job.job_id)
    assert recovered.status is ProductFulfillmentStatus.PENDING
    assert recovered.story_status is FulfillmentStageStatus.PENDING


def test_orchestrator_orders_stages_and_finishes(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = _create_job(repository)
    runner = FakeRunner()

    result = asyncio.run(
        ProductFulfillmentOrchestrator(repository, runner).execute(job.job_id)
    )

    assert [item[0] for item in runner.calls] == ["story", "experience", "resources"]
    assert result.status is ProductFulfillmentStatus.SUCCEEDED
    assert result.resource_snapshot_hash == "c" * 64


def test_story_failure_blocks_downstream_without_touching_run(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = _create_job(repository)
    runner = FakeRunner(fail="story")

    result = asyncio.run(
        ProductFulfillmentOrchestrator(repository, runner).execute(job.job_id)
    )

    assert runner.calls == [("story", ROUTES[0])]
    assert result.status is ProductFulfillmentStatus.FAILED
    assert result.experience_status is FulfillmentStageStatus.BLOCKED
    assert result.resources_status is FulfillmentStageStatus.BLOCKED
    with get_conn(fulfillment_db) as conn:
        assert conn.execute("SELECT status FROM runs WHERE id='run-1'").fetchone()[0] == "succeeded"


def test_optional_resources_not_applicable_is_successful_terminal(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = _create_job(repository)
    runner = FakeRunner(resources_status=FulfillmentStageStatus.NOT_APPLICABLE)

    result = asyncio.run(
        ProductFulfillmentOrchestrator(repository, runner).execute(job.job_id)
    )

    assert result.status is ProductFulfillmentStatus.SUCCEEDED
    assert result.resources_status is FulfillmentStageStatus.NOT_APPLICABLE


def test_transient_stage_gets_one_bounded_retry(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = _create_job(repository)
    runner = FakeRunner(transient="story")

    result = asyncio.run(
        ProductFulfillmentOrchestrator(repository, runner).execute(job.job_id)
    )

    assert [item[0] for item in runner.calls].count("story") == 2
    assert result.status is ProductFulfillmentStatus.SUCCEEDED


def test_existing_succeeded_stages_are_never_called_again(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = _create_job(repository)
    for stage in FulfillmentStage:
        repository.claim_stage(job.job_id, stage)
        repository.complete_stage(
            job.job_id, stage, FulfillmentStageStatus.SUCCEEDED, _ref(stage.value)
        )
    runner = FakeRunner()

    result = asyncio.run(
        ProductFulfillmentOrchestrator(repository, runner).execute(job.job_id)
    )

    assert result.status is ProductFulfillmentStatus.SUCCEEDED
    assert runner.calls == []


def test_executor_duplicate_reconcile_creates_one_job_and_chain(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    runner = FakeRunner()
    executor = ProductFulfillmentExecutor(
        repository,
        ProductFulfillmentOrchestrator(repository, runner),
        poll_interval=10,
    )

    async def exercise():
        for _ in range(10):
            await executor.reconcile_once()
        await asyncio.gather(*tuple(executor._tasks.values()))

    asyncio.run(exercise())

    assert len(repository.discover_eligible_runs()) == 0
    with get_conn(fulfillment_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM product_fulfillment_jobs").fetchone()[0] == 1
    assert [item[0] for item in runner.calls] == ["story", "experience", "resources"]


def test_started_executor_ignores_historical_incomplete_run(fulfillment_db):
    _formal_run("run-old", "itinerary-old", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    runner = FakeRunner()
    executor = ProductFulfillmentExecutor(
        repository, ProductFulfillmentOrchestrator(repository, runner)
    )
    executor._activation_time = "2026-08-23T13:00:00+00:00"

    assert asyncio.run(executor.reconcile_once()) == ()
    assert runner.calls == []
    assert repository.get_for_run("run-old", "itinerary-old") is None


def test_started_executor_backfills_historical_complete_chain(fulfillment_db):
    _formal_run("run-old", "itinerary-old", route_id=ROUTES[0])
    _insert_complete_snapshot_chain("run-old", "itinerary-old")
    repository = ProductFulfillmentRepository(fulfillment_db)
    runner = FakeRunner()
    executor = ProductFulfillmentExecutor(
        repository, ProductFulfillmentOrchestrator(repository, runner)
    )
    executor._activation_time = "2026-08-23T13:00:00+00:00"

    async def exercise():
        await executor.reconcile_once()
        await asyncio.gather(*tuple(executor._tasks.values()))

    asyncio.run(exercise())

    assert repository.get("owner", "run-old").status is ProductFulfillmentStatus.SUCCEEDED


def test_started_executor_enqueues_newly_completed_run(fulfillment_db):
    _formal_run(
        "run-new",
        "itinerary-new",
        route_id=ROUTES[0],
        finished_at="2026-08-23T13:00:01+00:00",
    )
    repository = ProductFulfillmentRepository(fulfillment_db)
    runner = FakeRunner()
    executor = ProductFulfillmentExecutor(
        repository, ProductFulfillmentOrchestrator(repository, runner)
    )
    executor._activation_time = "2026-08-23T13:00:00+00:00"

    async def exercise():
        await executor.reconcile_once()
        await asyncio.gather(*tuple(executor._tasks.values()))

    asyncio.run(exercise())

    assert repository.get("owner", "run-new").status is ProductFulfillmentStatus.SUCCEEDED


def test_executor_stop_cancels_owned_stage_and_startup_reset_recovers(
    fulfillment_db,
):
    class BlockingRunner(FakeRunner):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.cancelled = asyncio.Event()

        async def story(self, job):
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled.set()
                raise

    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    _create_job(repository)
    runner = BlockingRunner()
    executor = ProductFulfillmentExecutor(
        repository,
        ProductFulfillmentOrchestrator(repository, runner),
        poll_interval=10,
        shutdown_grace_period=0.01,
    )

    async def exercise():
        await executor.start()
        await asyncio.wait_for(runner.started.wait(), timeout=1)
        await executor.stop()
        assert runner.cancelled.is_set()

    asyncio.run(exercise())

    interrupted = repository.get("owner", "run-1")
    assert interrupted.story_status is FulfillmentStageStatus.RUNNING
    assert repository.reset_running_for_startup() == 1
    recovered = repository.get("owner", "run-1")
    assert recovered.story_status is FulfillmentStageStatus.PENDING


def test_non_catalog_run_does_not_trigger(fulfillment_db):
    _formal_run("run-plain", "itinerary-plain", route_id=None)
    repository = ProductFulfillmentRepository(fulfillment_db)
    runner = FakeRunner()
    executor = ProductFulfillmentExecutor(
        repository, ProductFulfillmentOrchestrator(repository, runner)
    )

    assert asyncio.run(executor.reconcile_once()) == ()
    assert runner.calls == []


@pytest.mark.parametrize("route_id", ROUTES)
def test_four_routes_use_the_same_orchestration_path(fulfillment_db, route_id):
    suffix = route_id.rsplit(".", 1)[-1]
    run_id = f"run-{suffix}"
    itinerary_id = f"itinerary-{suffix}"
    _formal_run(run_id, itinerary_id, route_id=route_id)
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = _create_job(repository, run_id, itinerary_id, route_id)
    runner = FakeRunner()

    result = asyncio.run(
        ProductFulfillmentOrchestrator(repository, runner).execute(job.job_id)
    )

    assert result.status is ProductFulfillmentStatus.SUCCEEDED
    assert {seen_route for _, seen_route in runner.calls} == {route_id}


def test_retry_rejects_successful_job(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    _create_job(repository)
    with pytest.raises(FulfillmentTransitionError):
        repository.retry_failed("owner", "run-1")


@pytest.mark.parametrize("route_id", ROUTES)
def test_production_resolution_uses_catalog_relationships(route_id, fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=route_id)
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = _create_job(repository, route_id=route_id)
    runner = ProductionFulfillmentStageRunner(db_path=fulfillment_db)

    catalog = runner._catalog(job)
    story = runner._story_blueprint(catalog, job)
    experience = runner._experience_blueprint(catalog, job, story.story_id)

    assert story.route_id == route_id
    assert experience.route_id == route_id
    assert experience.story_id == story.story_id
    if route_id == "changzhi.route.nuwa-tiantaishan":
        view = runner._catalog(job)
        route_view = CatalogProductService(view).get_route(job.package_id, route_id)
        assert route_view["capabilities"]["spatial_resolution"] == "verified_locality"
        assert route_view["capabilities"]["spatial_degraded"] is True
        assert route_view["capabilities"]["exact_anchor_location_available"] is False


def test_frozen_catalog_version_never_falls_back_to_latest(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = repository.create(
        owner_id="owner",
        run_id="run-1",
        itinerary_id="itinerary-1",
        route_id=ROUTES[0],
        package_id="shanxi.changzhi",
        schema_version="1.0",
        content_version="0.5.0",
    )

    with pytest.raises(FulfillmentStageError) as caught:
        ProductionFulfillmentStageRunner(db_path=fulfillment_db)._catalog(job)
    assert caught.value.code == "CATALOG_SNAPSHOT_UNAVAILABLE"


def test_existing_story_snapshot_reconciles_without_generation(
    fulfillment_db, monkeypatch
):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = _create_job(repository)
    runner = ProductionFulfillmentStageRunner(db_path=fulfillment_db)
    catalog = runner._catalog(job)
    existing = StoryPackageSnapshotRepository(fulfillment_db).save(bind_story(catalog))

    monkeypatch.setattr(
        StoryGenerationService,
        "generate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("existing snapshot must not call Story LLM")
        ),
    )
    result = asyncio.run(runner.story(job))

    assert result.snapshot.package_id == existing.package.package_id
    assert result.snapshot.snapshot_hash == existing.snapshot_hash


def test_missing_declared_upstream_snapshot_is_hard_chain_failure(fulfillment_db):
    _formal_run("run-1", "itinerary-1", route_id=ROUTES[0])
    repository = ProductFulfillmentRepository(fulfillment_db)
    job = _create_job(repository)
    repository.claim_stage(job.job_id, FulfillmentStage.STORY)
    repository.complete_stage(
        job.job_id,
        FulfillmentStage.STORY,
        FulfillmentStageStatus.SUCCEEDED,
        _ref("story"),
    )
    runner = ProductionFulfillmentStageRunner(db_path=fulfillment_db)

    result = asyncio.run(
        ProductFulfillmentOrchestrator(repository, runner).execute(job.job_id)
    )

    assert result.experience_status is FulfillmentStageStatus.FAILED
    assert result.last_error_code == "SNAPSHOT_CHAIN_MISMATCH"
