# TODO

Updated: 2026-08-22 08:08:11 +08:00

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
- [x] Create the accepted M1C Git checkpoint (`08687a1`).
- [x] Add Provider-neutral staged meal coverage at 1 km, 3 km, and 5 km with a bounded maximum.
- [x] Add route-aware lunch fallback from the morning primary anchor to the afternoon secondary anchor.
- [x] Preserve meal Provider identity, distance, search level, radius, anchor role, and anchor name provenance.
- [x] Distinguish `COVERED`, `FALLBACK_EXPANDED`, and `UNCOVERED` without allowing LLM-created restaurants.
- [x] Verify real Fajiushan meal discovery and rerun the formal Jingwei Runtime/API E2E.
- [x] Preserve mandatory Anchor enforcement, Reviewer, Time Check, Spot Tips, and Finalize behavior through M1D.

Deferred until explicitly approved:

- [ ] Review and create a Git checkpoint for M1D only after explicit approval; do not commit automatically.
- [ ] Decide whether the observed 39.82 km Fajiushan-to-lunch detour requires a separately scoped corridor-aware feasibility policy before M2.
- [ ] Investigate the Runtime concurrency `KNOWN_FLAKY` in a separate task.
- [ ] Keep RAG, Story, Experience, Commerce, Video, frontend, and mobile integration deferred until explicitly authorized.
