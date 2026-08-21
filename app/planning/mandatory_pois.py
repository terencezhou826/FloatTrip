"""Resolve and enforce verified mandatory POI identities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ConfigDict

from app.catalog.models import PoiProvider, StableId
from app.catalog.repository import CatalogRepository
from app.planning.catalog_context import CatalogContext
from app.providers.poi_identity import ExactPoiProvider, ExternalPoiRecord


class MandatoryPoiResolutionError(RuntimeError):
    pass


class MandatoryConstraintUnsatisfied(RuntimeError):
    pass


class ResolvedMandatoryPoi(ExternalPoiRecord):
    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_id: StableId
    curated_anchor_id: StableId
    is_mandatory: bool = True


class MandatoryPoiResolver:
    def __init__(
        self,
        repository: CatalogRepository,
        providers: Mapping[PoiProvider, ExactPoiProvider],
    ) -> None:
        self._repository = repository
        self._providers = providers

    async def resolve(
        self, context: CatalogContext | None
    ) -> tuple[ResolvedMandatoryPoi, ...]:
        if context is None or not context.mandatory_anchor_ids:
            return ()

        package = self._repository.get_package(context.package_id)
        if package is None or not package.manifest.enabled:
            raise MandatoryPoiResolutionError(
                f"catalog package {context.package_id} is unavailable"
            )
        manifest = package.manifest
        if (
            manifest.schema_version != context.schema_version
            or manifest.content_version != context.content_version
        ):
            raise MandatoryPoiResolutionError(
                "catalog snapshot version is no longer available"
            )
        if self._repository.get_route(context.route_id) is None:
            raise MandatoryPoiResolutionError(
                f"catalog route {context.route_id} is unavailable"
            )

        resolved: list[ResolvedMandatoryPoi] = []
        for anchor_id in context.mandatory_anchor_ids:
            if anchor_id not in context.anchor_ids:
                raise MandatoryPoiResolutionError(
                    f"mandatory anchor {anchor_id} is outside the selected route"
                )
            if self._repository.get_anchor(anchor_id) is None:
                raise MandatoryPoiResolutionError(
                    f"mandatory anchor {anchor_id} is unavailable"
                )
            bindings = self._repository.list_verified_bindings_for_anchor(anchor_id)
            if not bindings:
                raise MandatoryPoiResolutionError(
                    f"mandatory anchor {anchor_id} has no verified binding"
                )
            if len(bindings) > 1:
                raise MandatoryPoiResolutionError(
                    f"mandatory anchor {anchor_id} has multiple verified bindings"
                )

            binding = bindings[0]
            provider = self._providers.get(binding.provider)
            if provider is None:
                raise MandatoryPoiResolutionError(
                    f"unsupported provider: {binding.provider.value}"
                )
            try:
                record = await provider.get_poi(binding.external_poi_id)
            except Exception as exc:
                raise MandatoryPoiResolutionError(
                    f"provider lookup failed for binding {binding.binding_id}: {exc}"
                ) from exc
            if (
                record.provider is not binding.provider
                or record.external_poi_id != binding.external_poi_id
            ):
                raise MandatoryPoiResolutionError(
                    f"provider identity mismatch for binding {binding.binding_id}"
                )
            resolved.append(
                ResolvedMandatoryPoi(
                    **record.model_dump(),
                    binding_id=binding.binding_id,
                    curated_anchor_id=anchor_id,
                )
            )
        return tuple(resolved)


def _as_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    return dict(item)


def _identity(item: Mapping[str, Any]) -> tuple[str, str] | None:
    provider = item.get("provider")
    external_poi_id = item.get("external_poi_id")
    if hasattr(provider, "value"):
        provider = provider.value
    if not provider or not external_poi_id:
        return None
    return str(provider), str(external_poi_id)


def merge_poi_candidates(
    ordinary: Sequence[dict[str, Any]], mandatory: Sequence[Any]
) -> list[dict[str, Any]]:
    if not mandatory:
        return list(ordinary)

    merged = [dict(item) for item in ordinary]
    positions = {
        identity: index
        for index, item in enumerate(merged)
        if (identity := _identity(item)) is not None
    }
    for item in mandatory:
        mandatory_item = _as_dict(item)
        identity = _identity(mandatory_item)
        if identity is not None and identity in positions:
            index = positions[identity]
            preserved = {
                key: value
                for key, value in merged[index].items()
                if value is not None
            }
            merged[index] = {**preserved, **mandatory_item}
            for key, value in preserved.items():
                if merged[index].get(key) is None:
                    merged[index][key] = value
            continue
        if identity is not None:
            positions[identity] = len(merged)
        merged.append(mandatory_item)
    return merged


def missing_mandatory_pois(
    route: Sequence[Mapping[str, Any]], mandatory: Sequence[Any]
) -> list[dict[str, Any]]:
    selected = {
        identity
        for day in route
        for spot in day.get("spots", [])
        if (identity := _identity(spot)) is not None
    }
    return [
        item
        for raw in mandatory
        if (item := _as_dict(raw)) and _identity(item) not in selected
    ]


def mandatory_constraint_block(mandatory: Sequence[Any]) -> str:
    if not mandatory:
        return ""
    lines = []
    for raw in mandatory:
        item = _as_dict(raw)
        lines.append(
            f"- {item['name']} | provider={item['provider']} | "
            f"external_poi_id={item['external_poi_id']} | "
            f"curated_anchor_id={item['curated_anchor_id']}"
        )
    return (
        "\n\n【策展线路 mandatory POI 硬约束】\n"
        "以下地点必须在最终路线中至少安排一次，且输出时必须原样保留其 "
        "provider、external_poi_id、curated_anchor_id 和 is_mandatory 身份字段；"
        "不得删除或用同名地点替代：\n" + "\n".join(lines)
    )
