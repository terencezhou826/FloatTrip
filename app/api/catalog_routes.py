"""Public read-only product endpoints backed by the validated Catalog."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.catalog.loader import FileCatalogLoader
from app.product.catalog import CatalogProductService


router = APIRouter(prefix="/api/catalog", tags=["catalog-product"])
_CATALOG_ROOT = Path(__file__).resolve().parents[2] / "content" / "catalog"


def _service() -> CatalogProductService:
    return CatalogProductService(FileCatalogLoader(_CATALOG_ROOT).load())


@router.get("/product-collections")
def list_product_collections(region_id: str | None = Query(default=None)):
    return {"collections": _service().list_collections(region_id=region_id)}


@router.get("/packages/{package_id}/routes/{route_id}")
def get_product_route(package_id: str, route_id: str):
    route = _service().get_route(package_id, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="主题线路不存在或尚未启用")
    return route


@router.get("/routes/{route_id}")
def find_product_route(route_id: str):
    route = _service().find_route(route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="主题线路不存在或尚未启用")
    return route
