"""Bounded, provider-neutral meal candidate coverage policy."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal


class MealCoverageStatus(StrEnum):
    COVERED = "COVERED"
    FALLBACK_EXPANDED = "FALLBACK_EXPANDED"
    UNCOVERED = "UNCOVERED"


@dataclass(frozen=True)
class MealSearchLevel:
    level: int
    radius_m: int


@dataclass(frozen=True)
class MealSearchAnchor:
    name: str
    location: dict[str, float]
    role: Literal["primary", "secondary"] = "primary"


@dataclass(frozen=True)
class MealCoverageResult:
    status: MealCoverageStatus
    candidates: tuple[dict[str, Any], ...]
    attempts: tuple[dict[str, Any], ...]
    max_search_radius_m: int


DEFAULT_MEAL_SEARCH_LEVELS = (
    MealSearchLevel(level=0, radius_m=1000),
    MealSearchLevel(level=1, radius_m=3000),
    MealSearchLevel(level=2, radius_m=5000),
)

MealCandidateSearch = Callable[
    [dict[str, float], int], Awaitable[list[dict[str, Any]]]
]


def _identified_candidates(
    candidates: Sequence[dict[str, Any]],
    *,
    level: MealSearchLevel,
    anchor: MealSearchAnchor,
) -> tuple[dict[str, Any], ...]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for candidate in candidates:
        provider = str(candidate.get("provider") or "").strip()
        external_poi_id = str(candidate.get("external_poi_id") or "").strip()
        if not provider or not external_poi_id:
            continue
        identity = (provider, external_poi_id)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(
            {
                **candidate,
                "provider": provider,
                "external_poi_id": external_poi_id,
                "search_level": level.level,
                "search_radius_m": level.radius_m,
                "search_anchor_role": anchor.role,
                "search_anchor_name": anchor.name,
            }
        )
    return tuple(result)


async def discover_meal_coverage(
    anchors: Sequence[MealSearchAnchor],
    search: MealCandidateSearch,
    *,
    levels: Sequence[MealSearchLevel] = DEFAULT_MEAL_SEARCH_LEVELS,
) -> MealCoverageResult:
    """Search progressively, stopping at the first identified candidate set."""
    if not levels:
        raise ValueError("meal search levels must not be empty")
    max_radius = max(level.radius_m for level in levels)
    attempts: list[dict[str, Any]] = []

    for level in levels:
        for anchor in anchors:
            raw_candidates = await search(anchor.location, level.radius_m)
            candidates = _identified_candidates(
                raw_candidates,
                level=level,
                anchor=anchor,
            )
            attempts.append(
                {
                    "search_level": level.level,
                    "search_radius_m": level.radius_m,
                    "search_anchor_role": anchor.role,
                    "search_anchor_name": anchor.name,
                    "candidate_count": len(candidates),
                }
            )
            if candidates:
                status = (
                    MealCoverageStatus.COVERED
                    if level.level == 0 and anchor.role == "primary"
                    else MealCoverageStatus.FALLBACK_EXPANDED
                )
                return MealCoverageResult(
                    status=status,
                    candidates=candidates,
                    attempts=tuple(attempts),
                    max_search_radius_m=max_radius,
                )

    return MealCoverageResult(
        status=MealCoverageStatus.UNCOVERED,
        candidates=(),
        attempts=tuple(attempts),
        max_search_radius_m=max_radius,
    )
