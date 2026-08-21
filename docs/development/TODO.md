# TODO

Updated: 2026-08-21 19:28:24 +08:00

- [x] Implement the isolated M0 Catalog models, repository, loader, validation, content, and tests.
- [x] Add the controlled `RegionType` enum and optional `admin_code`.
- [x] Replace route `region_id` with `primary_region_id` and non-empty `coverage_region_ids`.
- [x] Validate route and Anchor coverage through the generic Region parent tree.
- [x] Restore the already-declared checkpoint dependency in the local environment.
- [x] Run Catalog, compileall, complete Python, and frontend tests.
- [x] Consolidate long-term project tracking under `docs/development/`.

Deferred until explicitly approved:

- [ ] Define and approve M1 scope.
- [ ] Investigate the Runtime concurrency `KNOWN_FLAKY` in a separate task.
- [ ] Connect Catalog to Planning, API, Runtime, database, Web, Mobile, RAG, Story, or Video only in an explicitly authorized later phase.
