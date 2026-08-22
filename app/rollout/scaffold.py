"""Generate empty, fact-free route content workspaces."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.evaluation.models import EvaluationModel
from app.rollout.models import RouteRolloutStatus


_STABLE_ID = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")


class RouteScaffoldManifest(EvaluationModel):
    scaffold_schema_version: str
    route_id: str
    rollout_status: RouteRolloutStatus
    generated_content: bool = False


class RouteContentScaffold:
    EMPTY_FILES = (
        "poi_bindings.json",
        "knowledge/sources.json",
        "knowledge/claims.json",
        "knowledge/evidence.json",
        "stories/blueprints.json",
        "stories/chapters.json",
        "experiences/blueprints.json",
        "experiences/activities.json",
        "benchmarks/cases.json",
    )

    def create(self, output_root: str | Path, route_id: str) -> Path:
        if not _STABLE_ID.fullmatch(route_id):
            raise ValueError("route_id must be a stable ID")
        root = Path(output_root).resolve()
        target = (root / route_id).resolve()
        if root not in target.parents:
            raise ValueError("scaffold target escapes output root")
        if target.exists():
            raise FileExistsError(f"route scaffold already exists: {target}")
        target.mkdir(parents=True)
        manifest = RouteScaffoldManifest(
            scaffold_schema_version="1.0",
            route_id=route_id,
            rollout_status=RouteRolloutStatus.CATALOG_ONLY,
        )
        self._write(target / "manifest.json", manifest.model_dump(mode="json"))
        for relative in self.EMPTY_FILES:
            self._write(target / relative, [])
        self._write(
            target / "benchmarks" / "golden.json",
            {
                "route_id": route_id,
                "mandatory_anchor_identity": {},
                "expected_chapter_ids": [],
                "expected_activity_ids": [],
                "approved_claim_ids": [],
                "forbidden_claim_ids": [],
                "capability_expectation": {},
            },
        )
        return target

    @staticmethod
    def _write(path: Path, value) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
