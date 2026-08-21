# TODO

Updated: 2026-08-21 20:01:43 +08:00

- [x] Implement the isolated M0 Catalog models, repository, loader, validation, content, and tests.
- [x] Add the controlled `RegionType` enum and optional `admin_code`.
- [x] Replace route `region_id` with `primary_region_id` and non-empty `coverage_region_ids`.
- [x] Validate route and Anchor coverage through the generic Region parent tree.
- [x] Restore the already-declared checkpoint dependency in the local environment.
- [x] Run Catalog, compileall, complete Python, and frontend tests.
- [x] Consolidate long-term project tracking under `docs/development/`.
- [x] Add immutable, versioned CatalogContext and a generic package-scoped resolver.
- [x] Freeze explicit Catalog selection into Run and itinerary snapshots.
- [x] Preserve CatalogContext through checkpoint, retry, revision, and legacy modification flows.
- [x] Verify M1A remains behavior-neutral for ordinary planning.

Deferred until explicitly approved:

- [ ] Review and create an independent Git checkpoint for M1A.
- [ ] Define and approve M1B scope before applying mandatory anchors to planning.
- [ ] Investigate the Runtime concurrency `KNOWN_FLAKY` in a separate task.
- [ ] Keep RAG, Story, Experience, Commerce, Video, frontend, and mobile integration deferred until explicitly authorized.
