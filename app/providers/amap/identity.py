"""Amap exact POI identity adapter."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.catalog.models import PoiProvider
from app.providers.amap.poi import (
    get_poi_by_id_async,
    normalize_address,
    parse_location,
)
from app.providers.poi_identity import ExternalPoiRecord


ExactLookup = Callable[[str, str], Awaitable[list[dict[str, Any]]]]


class AmapExactPoiProvider:
    provider = PoiProvider.AMAP

    def __init__(
        self,
        api_key: str,
        *,
        lookup: ExactLookup = get_poi_by_id_async,
    ) -> None:
        if not api_key:
            raise ValueError("Amap API key is required")
        self._api_key = api_key
        self._lookup = lookup

    async def get_poi(self, external_poi_id: str) -> ExternalPoiRecord:
        raw_results = await self._lookup(external_poi_id, self._api_key)
        if len(raw_results) != 1:
            raise RuntimeError(
                "Amap exact POI lookup must return exactly one result"
            )
        raw = raw_results[0]
        returned_id = str(raw.get("id") or "").strip()
        if returned_id != external_poi_id:
            raise RuntimeError("Amap exact POI lookup returned a different identity")
        location = parse_location(raw.get("location"))
        if location is None:
            raise RuntimeError("Amap exact POI lookup returned no usable location")

        biz_ext = raw.get("biz_ext") or {}
        rating_raw = biz_ext.get("rating") if isinstance(biz_ext, dict) else None
        try:
            rating = float(rating_raw) if rating_raw not in (None, "") else None
        except (TypeError, ValueError):
            rating = None
        open_time = None
        if isinstance(biz_ext, dict):
            open_time = str(
                biz_ext.get("opentime2") or biz_ext.get("opentime") or ""
            ).strip() or None
        photos = raw.get("photos") or []
        photo = None
        if isinstance(photos, list) and photos and isinstance(photos[0], dict):
            photo = str(photos[0].get("url") or "").strip() or None

        return ExternalPoiRecord(
            provider=self.provider,
            external_poi_id=returned_id,
            name=str(raw.get("name") or "").strip(),
            location=location,
            rating=rating,
            open_time=open_time,
            photo=photo,
            region_name=str(raw.get("adname") or "").strip() or None,
            address=normalize_address(raw.get("address")).strip() or None,
            tel=str(raw.get("tel") or "").strip() or None,
            cost=(
                str(biz_ext.get("cost") or "").strip() or None
                if isinstance(biz_ext, dict)
                else None
            ),
        )
