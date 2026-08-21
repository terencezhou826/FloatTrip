"""Amap adapter for operator-facing Anchor POI candidate discovery."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.catalog.discovery import (
    ExternalPoiCandidate,
    PoiDiscoveryQuery,
)
from app.catalog.models import PoiProvider, RegionType
from app.providers.amap.poi import (
    ATTRACTION_TYPE,
    normalize_address,
    parse_location,
    search_city_pois,
)


SearchFunction = Callable[..., list[dict[str, Any]]]


class AmapPoiDiscoveryProvider:
    provider = PoiProvider.AMAP

    def __init__(
        self,
        api_key: str,
        *,
        search: SearchFunction = search_city_pois,
    ) -> None:
        if not api_key:
            raise ValueError("Amap API key is required")
        self._api_key = api_key
        self._search = search

    def search_candidates(
        self, query: PoiDiscoveryQuery
    ) -> tuple[ExternalPoiCandidate, ...]:
        scope = next(
            (
                region
                for region in reversed(query.region_path)
                if region.region_type is RegionType.PREFECTURE_CITY
            ),
            query.region_path[-1],
        )
        raw_candidates = self._search(
            scope.admin_code or scope.name,
            self._api_key,
            keywords=query.anchor_name,
            types=ATTRACTION_TYPE,
            offset=10,
        )
        candidates: list[ExternalPoiCandidate] = []
        for raw in raw_candidates:
            external_poi_id = str(raw.get("id") or "").strip()
            name = str(raw.get("name") or "").strip()
            if not external_poi_id or not name:
                continue

            address = normalize_address(raw.get("address")).strip() or None
            region_code = normalize_address(raw.get("adcode")).strip() or None
            raw_fields = {
                field: raw[field]
                for field in (
                    "type",
                    "typecode",
                    "pname",
                    "cityname",
                    "adname",
                    "tel",
                )
                if field in raw and raw[field] not in (None, "", [])
            }
            candidates.append(
                ExternalPoiCandidate(
                    provider=self.provider,
                    external_poi_id=external_poi_id,
                    name=name,
                    address=address,
                    provider_region_code=region_code,
                    location=parse_location(raw.get("location")),
                    raw_fields=raw_fields,
                )
            )
        return tuple(candidates)
