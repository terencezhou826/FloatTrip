from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.catalog.loader import FileCatalogLoader
from app.catalog.repository import InMemoryCatalogRepository
from app.core.database import get_conn, init_db
from app.core.memory import load_itinerary, save_itinerary
from app.planning.catalog_context import (
    CatalogContextResolutionError,
    CatalogContextResolver,
)
from app.planning.runtime_worker import (
    PlanningFinalizer,
    revision_snapshot_to_state,
    snapshot_to_state,
)
from app.planning.schemas import TravelPlanState


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = PROJECT_ROOT / "content" / "catalog"
PACKAGE_ID = "shanxi.changzhi"
ROUTE_ID = "changzhi.route.jingwei-fajiushan"


@pytest.fixture(scope="module")
def catalog():
    return FileCatalogLoader(CATALOG_ROOT).load()


@pytest.fixture(scope="module")
def resolver(catalog):
    return CatalogContextResolver(catalog)


@pytest.fixture(scope="module")
def jingwei_context(resolver):
    return resolver.resolve(PACKAGE_ID, ROUTE_ID)


def test_jingwei_route_resolves_complete_versioned_context(jingwei_context):
    assert jingwei_context.model_dump(mode="json") == {
        "package_id": PACKAGE_ID,
        "schema_version": "1.0",
        "content_version": "0.3.0",
        "region_id": "cn.shanxi.changzhi",
        "theme_id": "changzhi.jingwei",
        "route_id": ROUTE_ID,
        "theme_name": "精卫填海",
        "route_name": "精卫填海·发鸠山探秘",
        "primary_region_id": "cn.shanxi.changzhi.changzi",
        "coverage_region_ids": ["cn.shanxi.changzhi.changzi"],
        "anchor_ids": ["changzhi.anchor.fajiushan"],
        "mandatory_anchor_ids": ["changzhi.anchor.fajiushan"],
    }


def test_missing_route_is_rejected(resolver):
    with pytest.raises(CatalogContextResolutionError, match="route .* not found"):
        resolver.resolve(PACKAGE_ID, "missing.route")


def test_disabled_package_is_rejected(catalog):
    package = catalog.get_package(PACKAGE_ID)
    disabled = package.model_copy(
        update={"manifest": package.manifest.model_copy(update={"enabled": False})}
    )
    repository = InMemoryCatalogRepository(
        regions=catalog.list_regions(),
        themes=(),
        routes=(),
        anchors=(),
        manifests=(),
        packages=(disabled,),
    )

    with pytest.raises(CatalogContextResolutionError, match="package .* is disabled"):
        CatalogContextResolver(repository).resolve(PACKAGE_ID, ROUTE_ID)


def test_dangling_theme_reference_is_rejected(catalog):
    package = catalog.get_package(PACKAGE_ID)
    route = package.routes[0].model_copy(update={"theme_id": "missing.theme"})
    broken_package = package.model_copy(update={"routes": [route, *package.routes[1:]]})
    repository = InMemoryCatalogRepository(
        regions=catalog.list_regions(),
        themes=package.themes,
        routes=broken_package.routes,
        anchors=package.anchors,
        manifests=(package.manifest,),
        packages=(broken_package,),
    )

    with pytest.raises(CatalogContextResolutionError, match="theme .* not found"):
        CatalogContextResolver(repository).resolve(PACKAGE_ID, ROUTE_ID)


def test_context_serializes_through_travel_plan_state(jingwei_context):
    state = TravelPlanState(query="长治两日游", catalog_context=jingwei_context)

    restored = TravelPlanState.model_validate_json(state.model_dump_json())

    assert restored.catalog_context == jingwei_context
    assert restored.model_dump(mode="json")["catalog_context"]["content_version"] == "0.3.0"


def test_ordinary_state_remains_context_free_and_unchanged():
    state = snapshot_to_state({"query": "南京两日游", "max_per_day": 3})

    assert state.catalog_context is None
    assert state.query == "南京两日游"
    assert state.max_per_day == 3


def test_itinerary_checkpoint_freezes_context_and_omits_absent_context(
    tmp_path, jingwei_context
):
    db_path = tmp_path / "finalizer.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO users(id,username,password_hash,created_at) VALUES(?,?,?,?)",
            ("owner", "owner", "hash", "2026-01-01"),
        )
    final_plan = {
        "destination": "长治",
        "start_date": "2026-09-01",
        "end_date": "2026-09-02",
        "days": [],
    }
    core_get_conn = get_conn
    with patch(
        "app.planning.runtime_worker.get_conn",
        side_effect=lambda: core_get_conn(db_path),
    ):
        themed_id = PlanningFinalizer._persist(
            {"user_id": "owner"},
            TravelPlanState(
                query="长治两日游",
                catalog_context=jingwei_context,
                final_plan=final_plan,
            ),
        )
        ordinary_id = PlanningFinalizer._persist(
            {"user_id": "owner"},
            TravelPlanState(query="长治两日游", final_plan=final_plan),
        )

    with get_conn(db_path) as conn:
        themed = load_itinerary(themed_id, conn)
        ordinary = load_itinerary(ordinary_id, conn)
    assert themed["planner_state"]["catalog_context"]["content_version"] == "0.3.0"
    assert "catalog_context" not in ordinary["planner_state"]


def test_context_survives_sqlite_checkpoint_round_trip(tmp_path, jingwei_context):
    builder = StateGraph(TravelPlanState)
    builder.add_node("preserve", lambda _state: {})
    builder.add_edge(START, "preserve")
    builder.add_edge("preserve", END)
    config = {"configurable": {"thread_id": "catalog-context-round-trip"}}

    async def round_trip():
        async with AsyncSqliteSaver.from_conn_string(
            str(tmp_path / "checkpoints.db")
        ) as saver:
            graph = builder.compile(checkpointer=saver)
            await graph.ainvoke(
                TravelPlanState(query="长治两日游", catalog_context=jingwei_context),
                config,
            )
            return await graph.aget_state(config)

    snapshot = asyncio.run(round_trip())
    restored = TravelPlanState.model_validate(snapshot.values)
    assert restored.catalog_context == jingwei_context


def test_revision_restores_context_from_itinerary_checkpoint(
    tmp_path, jingwei_context
):
    db_path = tmp_path / "revision.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO users(id,username,password_hash,created_at) VALUES(?,?,?,?)",
            ("owner", "owner", "hash", "2026-01-01"),
        )
        itinerary_id = save_itinerary(
            "owner",
            {"destination": "长治", "days": []},
            "长治两日游",
            conn,
            planner_state=TravelPlanState(
                query="长治两日游", catalog_context=jingwei_context
            ).model_dump(mode="json"),
        )

    run = {
        "user_id": "owner",
        "request_snapshot": {
            "related_itinerary_id": itinerary_id,
            "modification_notes": "第二天轻松一些",
        },
    }
    core_get_conn = get_conn
    with patch(
        "app.planning.runtime_worker.get_conn",
        side_effect=lambda: core_get_conn(db_path),
    ):
        restored = asyncio.run(revision_snapshot_to_state(run))

    assert restored.catalog_context == jingwei_context


def test_mandatory_planning_integration_has_no_regional_special_cases():
    prohibited = {"changzhi", "jingwei", "fajiushan", "mythology"}
    found = set()
    for relative in (
        "app/planning/nodes.py",
        "app/planning/mandatory_pois.py",
        "app/planning/prompts.py",
    ):
        tree = ast.parse((PROJECT_ROOT / relative).read_text(encoding="utf-8"))
        found.update(
            token
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            for token in prohibited
            if token in node.value.casefold()
        )
    assert not found


def test_catalog_context_python_has_no_regional_special_cases():
    tree = ast.parse(
        (PROJECT_ROOT / "app" / "planning" / "catalog_context.py").read_text(
            encoding="utf-8"
        )
    )
    prohibited = {"changzhi", "jingwei", "mythology"}
    found = {
        token
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        for token in prohibited
        if token in node.value.casefold()
    }

    assert not found
