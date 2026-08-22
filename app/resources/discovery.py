"""Generic runtime local-resource discovery service."""

from __future__ import annotations

from typing import Protocol

from app.catalog.models import PoiProvider
from app.resources.models import RuntimeResourceCandidate


class RuntimeResourceProvider(Protocol):
    provider: PoiProvider

    async def discover_restaurants(
        self,
        location: dict[str, float],
        *,
        radius_m: int,
        limit: int,
    ) -> tuple[RuntimeResourceCandidate, ...]: ...


class ResourceDiscoveryService:
    def __init__(self, provider: RuntimeResourceProvider) -> None:
        self._provider = provider

    async def discover_restaurants(
        self,
        location: dict[str, float],
        *,
        radius_m: int = 5000,
        limit: int = 20,
        related_stop_id: str | None = None,
    ) -> tuple[RuntimeResourceCandidate, ...]:
        if radius_m < 1:
            raise ValueError("resource discovery radius must be positive")
        if limit < 1:
            raise ValueError("resource discovery limit must be positive")
        candidates = await self._provider.discover_restaurants(
            location,
            radius_m=radius_m,
            limit=limit,
        )
        seen: set[tuple[PoiProvider, str]] = set()
        unique: list[RuntimeResourceCandidate] = []
        for candidate in candidates:
            if candidate.identity in seen:
                continue
            seen.add(candidate.identity)
            unique.append(
                candidate.model_copy(update={"discovery_stop_id": related_stop_id})
                if related_stop_id is not None
                else candidate
            )
        return tuple(unique[:limit])
