"""Amap adapter for runtime local-resource candidates."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from typing import Any

from app.catalog.models import (
    CurrencyCode,
    LocalResourceType,
    PoiProvider,
    PriceStatus,
    ResourceCoordinates,
)
from app.providers.amap.poi import (
    normalize_address,
    parse_location,
    search_around_pois_async,
)
from app.resources.models import (
    FreshnessStatus,
    ProviderBusinessHours,
    ProviderPriceInfo,
    RuntimeResourceCandidate,
)


AroundSearch = Callable[..., Awaitable[list[dict[str, Any]]]]
Clock = Callable[[], datetime]


def _runtime_resource_id(provider: PoiProvider, external_poi_id: str) -> str:
    digest = hashlib.sha256(
        f"{provider.value}:{external_poi_id}".encode("utf-8")
    ).hexdigest()[:24]
    return f"runtime-resource.{provider.value}.{digest}"


def _number(value: Any) -> float | None:
    try:
        return float(str(value).strip()) if str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    try:
        return int(str(value).strip()) if str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _provider_price(
    biz_ext: dict[str, Any], retrieved_at: datetime
) -> ProviderPriceInfo:
    raw_cost = str(biz_ext.get("cost") or "").strip()
    if not raw_cost:
        return ProviderPriceInfo()
    try:
        amount = Decimal(raw_cost)
    except InvalidOperation:
        return ProviderPriceInfo()
    if amount < 0:
        return ProviderPriceInfo()
    return ProviderPriceInfo(
        price_status=PriceStatus.PER_PERSON,
        currency=CurrencyCode.CNY,
        amount=amount,
        unit="person",
        provider=PoiProvider.AMAP,
        source_field="amap.biz_ext.cost",
        retrieved_at=retrieved_at,
        freshness_status=FreshnessStatus.FRESH,
    )


def normalize_amap_restaurants(
    raw_candidates: list[dict[str, Any]],
    *,
    retrieved_at: datetime,
) -> tuple[RuntimeResourceCandidate, ...]:
    candidates: list[RuntimeResourceCandidate] = []
    for raw in raw_candidates:
        external_poi_id = str(raw.get("id") or "").strip()
        name = str(raw.get("name") or "").strip()
        location = parse_location(raw.get("location"))
        if not external_poi_id or not name or location is None:
            continue
        biz_ext = raw.get("biz_ext")
        if not isinstance(biz_ext, dict):
            biz_ext = {}
        open_time = (
            str(biz_ext.get("opentime2") or "").strip()
            or str(biz_ext.get("opentime") or "").strip()
            or None
        )
        business_hours = (
            ProviderBusinessHours(
                display_text=open_time,
                provider=PoiProvider.AMAP,
                source_field="amap.biz_ext.opentime",
                retrieved_at=retrieved_at,
                freshness_status=FreshnessStatus.FRESH,
            )
            if open_time
            else None
        )
        address = normalize_address(raw.get("address")).strip() or None
        provider_raw_fields = {
            field: raw[field]
            for field in ("typecode", "pcode", "citycode")
            if raw.get(field) not in (None, "", [])
        }
        candidates.append(
            RuntimeResourceCandidate(
                runtime_resource_id=_runtime_resource_id(
                    PoiProvider.AMAP, external_poi_id
                ),
                resource_type=LocalResourceType.RESTAURANT,
                name=name,
                provider=PoiProvider.AMAP,
                external_poi_id=external_poi_id,
                coordinates=ResourceCoordinates(
                    longitude=location["lng"], latitude=location["lat"]
                ),
                address=address,
                province=str(raw.get("pname") or "").strip() or None,
                city=str(raw.get("cityname") or "").strip() or None,
                district=str(raw.get("adname") or "").strip() or None,
                provider_region_code=str(raw.get("adcode") or "").strip() or None,
                poi_type=str(raw.get("type") or "").strip() or None,
                provider_distance_m=_integer(raw.get("distance")),
                rating=_number(biz_ext.get("rating")),
                review_count=_integer(
                    biz_ext.get("review_count") or biz_ext.get("comment_num")
                ),
                price_info=_provider_price(biz_ext, retrieved_at),
                business_hours=business_hours,
                provider_source="amap.place.around.v3",
                retrieved_at=retrieved_at,
                freshness_status=FreshnessStatus.FRESH,
                provider_raw_fields=provider_raw_fields,
            )
        )
    return tuple(candidates)


class AmapRuntimeResourceProvider:
    provider = PoiProvider.AMAP

    def __init__(
        self,
        api_key: str,
        *,
        search: AroundSearch = search_around_pois_async,
        clock: Clock = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not api_key:
            raise ValueError("Amap API key is required")
        self._api_key = api_key
        self._search = search
        self._clock = clock

    async def discover_restaurants(
        self,
        location: dict[str, float],
        *,
        radius_m: int,
        limit: int,
    ) -> tuple[RuntimeResourceCandidate, ...]:
        raw = await self._search(
            location,
            self._api_key,
            types="餐饮服务",
            radius=radius_m,
            offset=min(limit, 25),
        )
        return normalize_amap_restaurants(raw, retrieved_at=self._clock())
