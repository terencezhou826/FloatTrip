"""Canonical hashing for immutable generated package snapshots."""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel


def canonical_package_json(package: BaseModel) -> str:
    return json.dumps(
        package.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def package_snapshot_hash(package: BaseModel) -> str:
    return hashlib.sha256(canonical_package_json(package).encode("utf-8")).hexdigest()
