"""Deterministic Planner candidate references and backend hydration."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from app.planning.schemas import (
    DayRoute,
    PlannerTravelRoute,
    SpotPlan,
    TravelRoute,
)


logger = logging.getLogger(__name__)

_PROVIDER_POI = "provider_poi"
_CLUSTER_LABELS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮"


class PlannerCandidateReferenceError(ValueError):
    """Planner output cannot be resolved to exactly one candidate."""


def _value(value: Any) -> str:
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw).strip()


def _legacy_payload(candidate: Mapping[str, Any]) -> dict[str, Any]:
    location = candidate.get("location")
    if hasattr(location, "model_dump"):
        location = location.model_dump(mode="json")
    region = (
        candidate.get("region")
        or candidate.get("region_name")
        or candidate.get("adname")
    )
    return {
        "name": candidate.get("name") or "",
        "location": location,
        "address": candidate.get("address") or "",
        "region": region or "",
    }


def planner_candidate_ref(candidate: Mapping[str, Any]) -> str:
    """Return a deterministic identity reference without name-only matching."""
    identity_type = _value(candidate.get("spatial_identity_type"))
    identity_id = _value(candidate.get("spatial_identity_id"))
    provider = _value(candidate.get("provider"))
    external_poi_id = _value(candidate.get("external_poi_id"))

    if identity_type and identity_id and identity_type != _PROVIDER_POI:
        return f"spatial:{identity_type.casefold()}:{identity_id}"
    if provider and external_poi_id:
        return f"poi:{provider.casefold()}:{external_poi_id}"
    if identity_type and identity_id:
        return f"spatial:{identity_type.casefold()}:{identity_id}"

    payload = _legacy_payload(candidate)
    if not payload["name"]:
        raise PlannerCandidateReferenceError("Planner candidate is missing name")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"legacy:{digest}"


def build_planner_candidate_index(
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index candidates by stable ref and reject ambiguous identity collisions."""
    index: dict[str, dict[str, Any]] = {}
    for raw in candidates:
        candidate = deepcopy(dict(raw))
        candidate_ref = planner_candidate_ref(candidate)
        if candidate_ref in index:
            raise PlannerCandidateReferenceError(
                f"Duplicate Planner candidate_ref: {candidate_ref}"
            )
        index[candidate_ref] = candidate
    return index


def _candidate_line(candidate_ref: str, candidate: Mapping[str, Any]) -> str:
    location = candidate.get("location") or {}
    coordinates = "未知"
    if isinstance(location, Mapping):
        lng = location.get("lng", location.get("longitude"))
        lat = location.get("lat", location.get("latitude"))
        if isinstance(lng, (int, float)) and isinstance(lat, (int, float)):
            coordinates = f"{lng:.6f},{lat:.6f}"
    region = (
        candidate.get("adname")
        or candidate.get("region_name")
        or candidate.get("region")
        or "未知"
    )
    fields = [
        f"ref={candidate_ref}",
        f"name={candidate.get('name') or ''}",
        f"区域={region}",
        f"评分={candidate.get('rating') if candidate.get('rating') is not None else '无'}",
        f"开放={candidate.get('open_time') or '未知'}",
        f"坐标={coordinates}",
        f"mandatory={str(bool(candidate.get('is_mandatory'))).lower()}",
    ]
    if candidate.get("degraded"):
        fields.extend(
            [
                f"resolution={_value(candidate.get('resolution_level')) or '未知'}",
                f"placement={_value(candidate.get('placement_status')) or '未知'}",
                f"navigation={candidate.get('navigation_name') or '未知'}",
                f"disclosure={candidate.get('disclosure_text') or '必须说明精确位置不可用'}",
            ]
        )
    return "- " + " | ".join(fields)


def format_planner_candidates(
    candidates: Sequence[Mapping[str, Any]],
    candidate_index: Mapping[str, Mapping[str, Any]],
    cluster_map: Mapping[str, int] | None = None,
) -> str:
    """Render compact Planner input without authoritative nested metadata."""
    entries = [
        (planner_candidate_ref(candidate), candidate)
        for candidate in candidates
    ]
    for candidate_ref, _candidate in entries:
        if candidate_ref not in candidate_index:
            raise PlannerCandidateReferenceError(
                f"Planner candidate_ref is absent from index: {candidate_ref}"
            )
    if not cluster_map:
        return "\n".join(_candidate_line(ref, item) for ref, item in entries)

    groups: dict[int, list[tuple[str, Mapping[str, Any]]]] = {}
    for candidate_ref, candidate in entries:
        cluster_id = cluster_map.get(str(candidate.get("name") or ""), -1)
        groups.setdefault(cluster_id, []).append((candidate_ref, candidate))
    blocks: list[str] = []
    for cluster_id in sorted(groups, key=lambda value: (value == -1, value)):
        if cluster_id == -1:
            heading = "📍其他（无坐标，地理分区未知）"
        else:
            label = (
                _CLUSTER_LABELS[cluster_id]
                if cluster_id < len(_CLUSTER_LABELS)
                else f"#{cluster_id + 1}"
            )
            heading = f"📍地理分区{label}"
        lines = "\n".join(
            _candidate_line(candidate_ref, candidate)
            for candidate_ref, candidate in groups[cluster_id]
        )
        blocks.append(f"{heading}\n{lines}")
    return "\n\n".join(blocks)


def planner_mandatory_constraint_block(
    mandatory: Sequence[Mapping[str, Any]],
    candidate_index: Mapping[str, Mapping[str, Any]],
) -> str:
    """Require mandatory refs while leaving all identity metadata to hydration."""
    if not mandatory:
        return ""
    lines: list[str] = []
    for candidate in mandatory:
        candidate_ref = planner_candidate_ref(candidate)
        if candidate_ref not in candidate_index:
            raise PlannerCandidateReferenceError(
                f"Mandatory candidate_ref is absent from candidate pool: {candidate_ref}"
            )
        lines.append(
            f"- candidate_ref={candidate_ref} | name={candidate.get('name') or ''} | "
            f"curated_anchor_id={candidate.get('curated_anchor_id') or ''}"
        )
    return (
        "\n\n【策展线路 mandatory spatial Anchor 硬约束】\n"
        "最终 Planner selection 必须至少包含一次以下 candidate_ref。"
        "身份 metadata 由后端恢复；不要生成或复制 Provider/spatial metadata：\n"
        + "\n".join(lines)
    )


def compact_hydrated_route(route: Sequence[Mapping[str, Any]]) -> str:
    """Project a prior hydrated route back to the Planner-only representation."""
    days: list[dict[str, Any]] = []
    for day in route:
        spots: list[dict[str, Any]] = []
        for spot in day.get("spots", []):
            candidate_ref = spot.get("candidate_ref")
            if not candidate_ref and (
                (spot.get("provider") and spot.get("external_poi_id"))
                or (
                    spot.get("spatial_identity_type")
                    and spot.get("spatial_identity_id")
                )
            ):
                try:
                    candidate_ref = planner_candidate_ref(spot)
                except PlannerCandidateReferenceError:
                    candidate_ref = None
            spots.append(
                {
                    "candidate_ref": candidate_ref,
                    "name": spot.get("name") or "",
                    "period": spot.get("period") or "",
                    "start_time": spot.get("start_time") or "",
                    "end_time": spot.get("end_time") or "",
                }
            )
        days.append(
            {
                "day": day.get("day"),
                "theme": day.get("theme") or "",
                "spots": spots,
            }
        )
    return json.dumps(days, ensure_ascii=False, separators=(",", ":"))


def hydrate_planner_route(
    route: PlannerTravelRoute,
    candidate_index: Mapping[str, Mapping[str, Any]],
) -> TravelRoute:
    """Restore authoritative candidate metadata selected by exact candidate_ref."""
    days: list[DayRoute] = []
    for day in route.days:
        spots: list[SpotPlan] = []
        for selection in day.spots:
            candidate = candidate_index.get(selection.candidate_ref)
            if candidate is None:
                raise PlannerCandidateReferenceError(
                    f"Unknown Planner candidate_ref: {selection.candidate_ref}"
                )
            canonical_name = str(candidate.get("name") or "")
            if selection.name != canonical_name:
                logger.warning(
                    "Planner candidate name mismatch for ref=%s; using canonical name=%s",
                    selection.candidate_ref,
                    canonical_name,
                )
            payload = {
                field: deepcopy(candidate[field])
                for field in SpotPlan.model_fields
                if field in candidate
            }
            payload.update(
                {
                    "candidate_ref": selection.candidate_ref,
                    "name": canonical_name,
                    "period": selection.period,
                    "start_time": selection.start_time,
                    "end_time": selection.end_time,
                }
            )
            spots.append(SpotPlan.model_validate(payload))
        days.append(DayRoute(day=day.day, spots=spots, theme=day.theme))
    return TravelRoute(
        reasoning=route.reasoning,
        days=days,
        notes=route.notes,
        modification_concern=route.modification_concern,
    )
