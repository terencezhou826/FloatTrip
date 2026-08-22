"""Amap Web Service driving-time adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
import urllib.parse

from app.catalog.models import PoiProvider
from app.core.http import http_get_json_async
from app.providers.amap.client import (
    AMAP_DRIVING_URL,
    AMAP_RATE_LIMIT_INFOS,
    int_or_none,
)
from app.providers.travel_time import (
    TransportMode,
    TravelLeg,
    TravelPoint,
    TravelRoutingError,
)


DrivingRouteLookup = Callable[
    [TravelPoint, TravelPoint, str], Awaitable[dict[str, Any]]
]


async def get_driving_route_async(
    origin: TravelPoint,
    destination: TravelPoint,
    api_key: str,
) -> dict[str, Any]:
    params = {
        "key": api_key,
        "origin": f"{origin.longitude},{origin.latitude}",
        "destination": f"{destination.longitude},{destination.latitude}",
        "strategy": "0",
        "extensions": "base",
        "output": "json",
    }
    url = f"{AMAP_DRIVING_URL}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        data = await http_get_json_async(url)
        if data.get("status") == "1":
            return data
        info = str(data.get("info") or "UNKNOWN_ERROR")
        if info not in AMAP_RATE_LIMIT_INFOS or attempt >= 3:
            return data
        await asyncio.sleep(1.2 * (attempt + 1))
    raise AssertionError("unreachable")


class AmapTravelTimeProvider:
    provider = PoiProvider.AMAP

    def __init__(
        self,
        api_key: str,
        *,
        lookup: DrivingRouteLookup = get_driving_route_async,
    ) -> None:
        if not api_key:
            raise ValueError("Amap API key is required")
        self._api_key = api_key
        self._lookup = lookup

    async def get_travel_time(
        self,
        origin: TravelPoint,
        destination: TravelPoint,
        transport_mode: TransportMode,
    ) -> TravelLeg:
        if transport_mode is not TransportMode.DRIVING:
            raise TravelRoutingError(
                f"Amap adapter does not support transport mode {transport_mode}"
            )
        try:
            data = await self._lookup(origin, destination, self._api_key)
        except TravelRoutingError:
            raise
        except Exception as exc:
            raise TravelRoutingError(f"Amap driving request failed: {exc}") from exc

        if data.get("status") != "1":
            info = str(data.get("info") or "UNKNOWN_ERROR")
            raise TravelRoutingError(f"Amap driving route failed: {info}")
        paths = (data.get("route") or {}).get("paths") or []
        if not isinstance(paths, list) or not paths or not isinstance(paths[0], dict):
            raise TravelRoutingError("Amap driving route returned no path")
        distance_m = int_or_none(paths[0].get("distance"))
        duration_s = int_or_none(paths[0].get("duration"))
        if distance_m is None or duration_s is None:
            raise TravelRoutingError(
                "Amap driving route returned incomplete distance or duration"
            )
        return TravelLeg(
            from_poi=origin,
            to_poi=destination,
            distance_m=distance_m,
            duration_s=duration_s,
            provider=self.provider,
            transport_mode=transport_mode,
            source="amap.direction.driving.v3",
        )
