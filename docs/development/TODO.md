# TODO

Updated: 2026-08-22 00:04:28 +08:00

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
- [x] Create an independent Git checkpoint for M1A (`900c49e`).
- [x] Add provider-neutral Anchor-to-External-POI Binding models and enums.
- [x] Add optional package-level Binding storage, validation, and Repository queries.
- [x] Add Anchor/Region-driven POI candidate discovery and an Amap adapter.
- [x] Verify M1B-1 does not modify Planning, Runtime, frontend, mobile, or candidate pools.
- [x] Add provider-neutral POI Binding verification provenance and controlled methods.
- [x] Require method and timestamp only for verified Bindings.
- [x] Verify provenance JSON Loader/Repository round-trip and empty-content compatibility.
- [x] Perform real Fajiushan Amap Discovery and human verification outside runtime enforcement.
- [x] Persist the single approved Fajiushan verified Binding with audit provenance.
- [x] Add Provider-neutral exact POI identity lookup and mandatory resolution.
- [x] Merge mandatory POIs by Provider identity without name-based deduplication.
- [x] Preserve mandatory identity through Planner output, checkpoints, retries, revisions, and Finalize projection.
- [x] Enforce mandatory presence after every Planner output with deterministic failure semantics.
- [x] Verify Amap exact-ID lookup with a real read-only smoke test.
- [x] Add a generic OpenAI-compatible ChatOpenAI adapter and factory dispatch.
- [x] Keep the configured endpoint/model authoritative and strict structured output explicit.
- [x] Add Provider tests without real service calls or deployment-specific core code.
- [x] Restore the already-declared `langchain-openai` dependency in the active local environment without changing dependency files.
- [x] Configure and validate the real generic OpenAI-compatible environment without exposing credentials.
- [x] Pass real factory Chat and strict Pydantic function-calling smoke tests.
- [x] Pass real Catalog, verified Binding, exact Amap identity, and weather prerequisites.
- [x] Run Jingwei through the formal Runtime/API path and verify frozen CatalogContext, mandatory identity, checkpoint retention, and candidate provenance.
- [x] Complete the real Planner, Reviewer, Time Check, meal, Spot Tips, and Finalize pipeline without retry.

Deferred until explicitly approved:

- [ ] Review and create a Git checkpoint for M1C only after real E2E acceptance; do not commit automatically.
- [ ] Decide whether the Fajiushan lunch-search gap must be addressed before M2 in a separately scoped generic meal-coverage task.
- [ ] Investigate the Runtime concurrency `KNOWN_FLAKY` in a separate task.
- [ ] Keep RAG, Story, Experience, Commerce, Video, frontend, and mobile integration deferred until explicitly authorized.
