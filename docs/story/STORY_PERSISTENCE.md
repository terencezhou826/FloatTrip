# StoryPackage Persistence

## Why Persistence Is Required

A generated Story is a versioned input to downstream Experience work. Keeping it only in process memory makes retries non-reproducible and can force another LLM call with different wording. Formal StoryPackage artifacts therefore persist before Experience generation starts.

## Storage

`StoryPackageSnapshotRepository` uses the existing Runtime SQLite database. `story_package_snapshots` records:

- StoryPackage ID, Story ID and version.
- Run and itinerary IDs.
- package, schema, and content versions.
- complete serialized StoryPackage, including Chapters, Claim IDs, Citations, qualifiers, bindings, and metrics.
- a canonical SHA-256 snapshot hash and creation time.

No Redis, external database, or route-specific file is required.

## Immutability And Recovery

The package ID is immutable. Saving different content under an existing ID fails. Loading validates the canonical hash, serialized Pydantic contract, metadata columns, expected Run, itinerary, and Catalog version. Corrupt or mismatched records fail explicitly.

Experience generation accepts the loaded StoryPackage directly. A retry loads the same hash and does not call the Story LLM. The final ExperiencePackage stores both the StoryPackage ID and Story snapshot hash, and its own snapshot cannot be saved unless that exact Story record exists with matching Run, itinerary, and Catalog version.
