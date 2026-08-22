"""Deterministic road-time feasibility for selected itinerary legs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.catalog.models import PoiProvider, SpatialIdentityType
from app.providers.travel_time import (
    TransportMode,
    TravelLeg,
    TravelPoint,
    TravelRoutingError,
    TravelTimeProvider,
)


class RouteFeasibilityStatus(StrEnum):
    FEASIBLE = "FEASIBLE"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    UNRESOLVED = "UNRESOLVED"


class RouteFeasibilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class RouteFeasibilityPolicy:
    transition_buffer_s: int = 10 * 60
    soft_large_leg_distance_m: int = 50_000
    hard_max_leg_distance_m: int = 150_000
    soft_max_daily_driving_s: int = 2 * 60 * 60


@dataclass(frozen=True)
class MealDetourPolicy:
    max_extra_duration_s: int = 20 * 60
    max_total_duration_s: int = 90 * 60
    max_single_leg_duration_s: int = 60 * 60
    meal_duration_s: int = 45 * 60
    schedule_buffer_s: int = 10 * 60


class RouteLegAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    day: int
    from_poi: TravelPoint
    to_poi: TravelPoint
    distance_m: int = Field(ge=0)
    duration_s: int = Field(ge=0)
    provider: PoiProvider
    transport_mode: TransportMode
    source: str
    scheduled_gap_s: int
    required_gap_s: int
    feasibility: Literal["PASS", "FAIL"]


class RouteViolation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    day: int
    from_poi: str | None = None
    to_poi: str | None = None
    detail: str


class RouteFeasibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: RouteFeasibilityStatus
    legs: tuple[RouteLegAssessment, ...] = ()
    violations: tuple[RouteViolation, ...] = ()
    warnings: tuple[str, ...] = ()
    total_distance_m: int = 0
    total_duration_s: int = 0


class MealDetourAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    route_feasible: bool
    travel_legs: tuple[TravelLeg, ...]
    direct_leg: TravelLeg | None = None
    total_distance_m: int = 0
    total_duration_s: int = 0
    extra_duration_s: int = 0
    available_gap_s: int | None = None
    rejection_reasons: tuple[str, ...] = ()


def _point_cache_token(point: TravelPoint) -> str:
    return (
        f"{':'.join(str(part) for part in point.identity)}:"
        f"{point.longitude:.6f},{point.latitude:.6f}"
    )


def travel_leg_cache_key(
    origin: TravelPoint,
    destination: TravelPoint,
    transport_mode: TransportMode = TransportMode.DRIVING,
) -> str:
    return (
        f"{transport_mode.value}|{_point_cache_token(origin)}"
        f"->{_point_cache_token(destination)}"
    )


class TravelTimeMatrix:
    """Lazy selected-leg matrix with a serializable per-Run cache."""

    def __init__(
        self,
        providers: Mapping[PoiProvider, TravelTimeProvider],
        *,
        cache: Mapping[str, dict[str, Any]] | None = None,
    ) -> None:
        self._providers = dict(providers)
        self._cache = {key: dict(value) for key, value in (cache or {}).items()}

    async def get_leg(
        self,
        origin: TravelPoint,
        destination: TravelPoint,
        transport_mode: TransportMode = TransportMode.DRIVING,
    ) -> TravelLeg:
        origin_provider = origin.effective_routing_provider
        destination_provider = destination.effective_routing_provider
        if (
            origin_provider is not None
            and destination_provider is not None
            and origin_provider is not destination_provider
        ):
            raise TravelRoutingError(
                "cross-provider route coordinates are not supported"
            )
        routing_provider = origin_provider or destination_provider
        if routing_provider is None:
            if len(self._providers) != 1:
                raise TravelRoutingError(
                    "routing provider is ambiguous for coordinate-only points"
                )
            routing_provider = next(iter(self._providers))
        if origin.identity == destination.identity:
            return TravelLeg(
                from_poi=origin,
                to_poi=destination,
                distance_m=0,
                duration_s=0,
                provider=routing_provider,
                transport_mode=transport_mode,
                source="same_poi_identity",
            )
        key = travel_leg_cache_key(origin, destination, transport_mode)
        cached = self._cache.get(key)
        if cached is not None:
            leg = TravelLeg.model_validate(cached)
            return leg.model_copy(update={"from_poi": origin, "to_poi": destination})
        provider = self._providers.get(routing_provider)
        if provider is None:
            raise TravelRoutingError(
                f"no travel-time provider for {routing_provider.value}"
            )
        leg = await provider.get_travel_time(origin, destination, transport_mode)
        if (
            leg.from_poi.identity != origin.identity
            or leg.to_poi.identity != destination.identity
        ):
            raise TravelRoutingError("travel-time provider returned mismatched identity")
        self._cache[key] = leg.model_dump(mode="json")
        return leg

    def export_cache(self) -> dict[str, dict[str, Any]]:
        return {key: dict(value) for key, value in self._cache.items()}


def travel_point_from_item(item: Mapping[str, Any]) -> TravelPoint | None:
    provider_raw = item.get("provider")
    external_poi_id = str(item.get("external_poi_id") or "").strip()
    name = str(item.get("name") or "").strip()
    location = item.get("location")
    identity_type_raw = item.get("spatial_identity_type")
    spatial_identity_id = str(item.get("spatial_identity_id") or "").strip()
    curated_anchor_id = str(item.get("curated_anchor_id") or "").strip()
    if not name or not isinstance(location, Mapping):
        return None
    try:
        identity_type = (
            SpatialIdentityType(
                str(getattr(identity_type_raw, "value", identity_type_raw))
            )
            if identity_type_raw
            else SpatialIdentityType.PROVIDER_POI
        )
        provider = (
            PoiProvider(str(getattr(provider_raw, "value", provider_raw)))
            if provider_raw
            else None
        )
        longitude = float(location["lng"])
        latitude = float(location["lat"])
    except (KeyError, TypeError, ValueError):
        return None
    if identity_type is SpatialIdentityType.PROVIDER_POI:
        if provider is None or not external_poi_id:
            return None
    elif not spatial_identity_id or not curated_anchor_id:
        return None
    return TravelPoint(
        provider=provider,
        external_poi_id=external_poi_id or None,
        spatial_identity_type=identity_type,
        spatial_identity_id=spatial_identity_id or None,
        curated_anchor_id=curated_anchor_id or None,
        name=name,
        longitude=longitude,
        latitude=latitude,
    )


def _poi_points(
    pois: Sequence[Mapping[str, Any]],
) -> dict[tuple[object, str], TravelPoint]:
    result: dict[tuple[object, str], TravelPoint] = {}
    for poi in pois:
        point = travel_point_from_item(poi)
        if point is not None:
            result[point.identity] = point
    return result


def resolve_route_point(
    spot: Mapping[str, Any],
    poi_points: Mapping[tuple[object, str], TravelPoint],
) -> TravelPoint | None:
    provider_raw = spot.get("provider")
    external_poi_id = str(spot.get("external_poi_id") or "").strip()
    identity_type_raw = spot.get("spatial_identity_type")
    spatial_identity_id = str(spot.get("spatial_identity_id") or "").strip()
    try:
        identity_type = (
            SpatialIdentityType(
                str(getattr(identity_type_raw, "value", identity_type_raw))
            )
            if identity_type_raw
            else SpatialIdentityType.PROVIDER_POI
        )
        if identity_type is SpatialIdentityType.PROVIDER_POI:
            if not provider_raw or not external_poi_id:
                return None
            provider = PoiProvider(str(getattr(provider_raw, "value", provider_raw)))
            identity = provider, external_poi_id
        else:
            if not spatial_identity_id:
                return None
            identity = identity_type, spatial_identity_id
    except ValueError:
        return None
    point = poi_points.get(identity)
    if point is None:
        return None
    name = str(spot.get("name") or point.name).strip()
    return point.model_copy(update={"name": name})


def _clock_seconds(value: Any) -> int | None:
    text = str(value or "")
    parts = text.split(":")
    if len(parts) != 2:
        return None
    try:
        hour, minute = (int(part) for part in parts)
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 3600 + minute * 60


def scheduled_gap_seconds(
    previous: Mapping[str, Any],
    following: Mapping[str, Any],
) -> int | None:
    previous_end = _clock_seconds(previous.get("end_time"))
    following_start = _clock_seconds(following.get("start_time"))
    if previous_end is None or following_start is None:
        return None
    return following_start - previous_end


async def evaluate_route_feasibility(
    route: Sequence[Mapping[str, Any]],
    pois: Sequence[Mapping[str, Any]],
    matrix: TravelTimeMatrix,
    *,
    policy: RouteFeasibilityPolicy = RouteFeasibilityPolicy(),
) -> RouteFeasibilityResult:
    points = _poi_points(pois)
    legs: list[RouteLegAssessment] = []
    violations: list[RouteViolation] = []
    warnings: list[str] = []
    total_distance_m = 0
    total_duration_s = 0

    for day in route:
        day_number = int(day.get("day") or 0)
        day_duration_s = 0
        spots = list(day.get("spots") or [])
        for previous, following in zip(spots, spots[1:]):
            origin = resolve_route_point(previous, points)
            destination = resolve_route_point(following, points)
            if origin is None or destination is None:
                violations.append(RouteViolation(
                    kind="missing_routing_identity",
                    day=day_number,
                    from_poi=str(previous.get("name") or "") or None,
                    to_poi=str(following.get("name") or "") or None,
                    detail=(
                        "selected adjacent places require stable spatial identity and coordinates"
                    ),
                ))
                continue
            scheduled_gap_s = scheduled_gap_seconds(previous, following)
            if scheduled_gap_s is None:
                violations.append(RouteViolation(
                    kind="invalid_schedule_time",
                    day=day_number,
                    from_poi=origin.name,
                    to_poi=destination.name,
                    detail="selected adjacent POIs require valid HH:MM times",
                ))
                continue
            leg = await matrix.get_leg(origin, destination)
            required_gap_s = leg.duration_s + policy.transition_buffer_s
            passed = (
                scheduled_gap_s >= required_gap_s
                and leg.distance_m <= policy.hard_max_leg_distance_m
            )
            assessment = RouteLegAssessment(
                day=day_number,
                **leg.model_dump(),
                scheduled_gap_s=scheduled_gap_s,
                required_gap_s=required_gap_s,
                feasibility="PASS" if passed else "FAIL",
            )
            legs.append(assessment)
            day_duration_s += leg.duration_s
            total_distance_m += leg.distance_m
            total_duration_s += leg.duration_s
            if scheduled_gap_s < required_gap_s:
                violations.append(RouteViolation(
                    kind="insufficient_travel_gap",
                    day=day_number,
                    from_poi=origin.name,
                    to_poi=destination.name,
                    detail=(
                        f"driving requires {leg.duration_s // 60} minutes plus "
                        f"{policy.transition_buffer_s // 60} minutes buffer, but "
                        f"the schedule leaves {max(0, scheduled_gap_s) // 60} minutes"
                    ),
                ))
            if leg.distance_m > policy.hard_max_leg_distance_m:
                violations.append(RouteViolation(
                    kind="excessive_leg_distance",
                    day=day_number,
                    from_poi=origin.name,
                    to_poi=destination.name,
                    detail=(
                        f"road distance {leg.distance_m / 1000:.1f} km exceeds "
                        f"the configured {policy.hard_max_leg_distance_m / 1000:.1f} km limit"
                    ),
                ))
            elif leg.distance_m >= policy.soft_large_leg_distance_m:
                warnings.append(
                    f"Day {day_number} {origin.name} -> {destination.name}: "
                    f"large road leg {leg.distance_m / 1000:.1f} km"
                )
        if day_duration_s >= policy.soft_max_daily_driving_s:
            warnings.append(
                f"Day {day_number}: daily driving {day_duration_s / 3600:.1f} hours"
            )

    unresolved = any(
        item.kind in {"missing_routing_identity", "invalid_schedule_time"}
        for item in violations
    )
    status = (
        RouteFeasibilityStatus.UNRESOLVED
        if unresolved
        else RouteFeasibilityStatus.REPLAN_REQUIRED
        if violations
        else RouteFeasibilityStatus.FEASIBLE
    )
    return RouteFeasibilityResult(
        status=status,
        legs=tuple(legs),
        violations=tuple(violations),
        warnings=tuple(dict.fromkeys(warnings)),
        total_distance_m=total_distance_m,
        total_duration_s=total_duration_s,
    )


async def assess_meal_detour(
    previous: TravelPoint,
    meal: TravelPoint,
    following: TravelPoint | None,
    matrix: TravelTimeMatrix,
    *,
    available_gap_s: int | None = None,
    policy: MealDetourPolicy = MealDetourPolicy(),
) -> MealDetourAssessment:
    first = await matrix.get_leg(previous, meal)
    travel_legs = [first]
    direct_leg = None
    if following is not None:
        second = await matrix.get_leg(meal, following)
        direct_leg = await matrix.get_leg(previous, following)
        travel_legs.append(second)

    total_distance_m = sum(item.distance_m for item in travel_legs)
    total_duration_s = sum(item.duration_s for item in travel_legs)
    extra_duration_s = max(
        0,
        total_duration_s - (direct_leg.duration_s if direct_leg is not None else 0),
    )
    rejection_reasons: list[str] = []
    if any(
        item.duration_s > policy.max_single_leg_duration_s
        for item in travel_legs
    ):
        rejection_reasons.append("single_leg_duration")
    if total_duration_s > policy.max_total_duration_s:
        rejection_reasons.append("total_travel_duration")
    if extra_duration_s > policy.max_extra_duration_s:
        rejection_reasons.append("extra_travel_duration")
    if (
        following is not None
        and available_gap_s is not None
        and total_duration_s + policy.meal_duration_s + policy.schedule_buffer_s
        > available_gap_s
    ):
        rejection_reasons.append("insufficient_meal_window")
    return MealDetourAssessment(
        route_feasible=not rejection_reasons,
        travel_legs=tuple(travel_legs),
        direct_leg=direct_leg,
        total_distance_m=total_distance_m,
        total_duration_s=total_duration_s,
        extra_duration_s=extra_duration_s,
        available_gap_s=available_gap_s,
        rejection_reasons=tuple(rejection_reasons),
    )
