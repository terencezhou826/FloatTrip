"""Local resource discovery, recommendation, and package contracts."""

from app.resources.discovery import ResourceDiscoveryService, RuntimeResourceProvider
from app.resources.models import (
    FreshnessStatus,
    ProviderBusinessHours,
    ProviderPriceInfo,
    ResourceProvenanceType,
    RuntimeResourceCandidate,
    classify_freshness,
)
from app.resources.recommendation import (
    BudgetPreference,
    ContextualRelation,
    LocalResourceRecommendationEngine,
    LocalResourceRecommendationRequest,
    MatchReason,
    RecommendationCandidate,
    RecommendationMetrics,
    RecommendationPriceSnapshot,
    RecommendationResult,
    RecommendationStatus,
    ResourceRecommendation,
    itinerary_stop_id,
    recommendation_candidate_from_catalog,
    recommendation_candidate_from_runtime,
)
from app.resources.package import (
    LocalResourcePackage,
    ResourceContextBinding,
    ResourceDisclosure,
    build_local_resource_package,
    local_resource_package_hash,
)
from app.resources.persistence import (
    LocalResourcePackageSnapshot,
    LocalResourcePackageSnapshotRepository,
    LocalResourceSnapshotError,
)

__all__ = [
    "FreshnessStatus",
    "BudgetPreference",
    "ContextualRelation",
    "LocalResourceRecommendationEngine",
    "LocalResourceRecommendationRequest",
    "LocalResourcePackage",
    "LocalResourcePackageSnapshot",
    "LocalResourcePackageSnapshotRepository",
    "LocalResourceSnapshotError",
    "MatchReason",
    "ProviderBusinessHours",
    "ProviderPriceInfo",
    "ResourceDiscoveryService",
    "ResourceProvenanceType",
    "ResourceContextBinding",
    "ResourceDisclosure",
    "RecommendationCandidate",
    "RecommendationMetrics",
    "RecommendationPriceSnapshot",
    "RecommendationResult",
    "RecommendationStatus",
    "ResourceRecommendation",
    "RuntimeResourceCandidate",
    "RuntimeResourceProvider",
    "classify_freshness",
    "build_local_resource_package",
    "itinerary_stop_id",
    "local_resource_package_hash",
    "recommendation_candidate_from_catalog",
    "recommendation_candidate_from_runtime",
]
