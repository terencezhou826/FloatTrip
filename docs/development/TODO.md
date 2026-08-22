# TODO

Updated: 2026-08-22 14:14:56 +08:00

M3 completed 2026-08-22 14:14:56 +08:00:

- [x] Repair five legacy Catalog fixtures by removing later `stories/` data from self-consistent historical snapshots; keep production Story validation unchanged.
- [x] Add generic StoryBlueprint and StoryChapter Catalog models, loading, Repository queries, and closed-reference validation.
- [x] Add one verified Jingwei Blueprint and five Chapters with production-eligible Claim and verified POI references.
- [x] Add standalone, evidence-grounded structured Story generation with deterministic Citation, qualifier, Claim-type, and Context-fact validation.
- [x] Add post-Planning Story binding based only on exact `provider + external_poi_id` identity.
- [x] Complete a real Runtime/API itinerary with Amap and OpenAI-compatible/Sub2API, then generate and bind all five Chapters.
- [x] Confirm production leakage, Citation hallucination, qualifier violation, Context fact violation, internal-only leakage, name-only binding, Knowledge mutation, and itinerary mutation are all zero.
- [x] Pass Story/Knowledge/Catalog (197), M1A-M1E focused (102), complete Python (377 plus 18 subtests), compileall, diff check, and frontend (26) regressions.
- [x] Document Story model, generation, binding, and reserved Video/Experience boundaries.

M2C completed 2026-08-22 13:18:50 +08:00:

- [x] Add standalone request, answer, Citation, Catalog-version, and Answerability schemas.
- [x] Gate all generation through production-safe M2B `KnowledgeContext` and deterministic answerability.
- [x] Bypass the LLM for unsupported premises, precision requests, and excluded production Claims.
- [x] Use strict `build_structured_llm()` output with one bounded repair attempt and no free-text fallback.
- [x] Validate Citation identities, Source/Evidence snapshots, production eligibility, qualifiers, Claim types, and grounded numbers.
- [x] Expose deterministic grounding counts and coverage.
- [x] Run real A-F answers with zero production leakage, Citation hallucination, qualifier violation, and Context-external cultural facts.
- [x] Reject year, coordinate, and archaeology hallucination injections before the LLM.
- [x] Keep Planning, Chat, Runtime, Story, Commerce, Video, frontend, mobile, Embedding, and vector databases unchanged.
- [x] Pass M2C, M2B, Knowledge, Catalog, focused, compileall, complete Python, and frontend regressions.

M2B completed 2026-08-22 12:43:06 +08:00:

- [x] Add frozen, serializable KnowledgeQuery, KnowledgeHit, and KnowledgeContext schemas.
- [x] Gate retrieval through package-scoped production eligibility before ranking.
- [x] Add deterministic Chinese lexical matching and explainable ranking without Embedding or LLM calls.
- [x] Preserve qualifiers, verified Evidence, Source provenance, locators, excerpts, and Catalog versions.
- [x] Support multiple Evidence records and Sources without treating contradicts as supports.
- [x] Run A-F standalone retrieval with zero production-ineligible leakage.
- [x] Document production filtering, ranking, hydration, disputed handling, network isolation, and the future Embedding boundary.
- [x] Pass Retriever, Catalog, focused, compileall, complete Python, and frontend regressions.

M2A Final Audit completed 2026-08-22 12:22:28 +08:00:

- [x] Recheck all 13 Claim/Evidence/Source chains against the three live public sources.
- [x] Confirm all Claim wording, types, promotion policies, qualifiers, and statuses remain within Evidence scope.
- [x] Keep the Yandi residence Claim `review_required` and `internal_only`.
- [x] Clarify digital-carrier, official-narrative, and qualification-preservation semantics in the Knowledge model documentation.
- [x] Confirm 12 production-eligible Claims and 100% verified-Claim Evidence coverage.
- [x] Pass Knowledge, focused, compileall, complete Python, and frontend regressions.

M2A completed 2026-08-22 11:53:09 +08:00:

- [x] Add provider-neutral KnowledgeSource, KnowledgeClaim, and KnowledgeEvidence models.
- [x] Add controlled claim type, source type, authority, verification, evidence relation, and promotion policy enums.
- [x] Load optional package `knowledge/**/*.json` recursively in deterministic order.
- [x] Validate global IDs, Catalog references, Evidence references, verified supporting Evidence, and 100% coverage.
- [x] Add Repository queries and conservative production-eligibility evaluation.
- [x] Add 3 checked Jingwei Sources, 13 Claims, and 13 Evidence records without LLM generation.
- [x] Document that verified mythology is not verified historical fact.
- [x] Pass Knowledge, Catalog, M1A-M1E, compileall, full Python, and frontend regressions.

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
- [x] Create the accepted M1D Git checkpoint (`3b4d716`).
- [x] Add Provider-neutral selected-leg travel-time contracts and an Amap Driving v3 adapter.
- [x] Cache actual OD legs per Run without building a candidate NxN matrix.
- [x] Add deterministic route status, hard schedule-gap validation, and separate soft driving warnings.
- [x] Feed route failures back to Planner without allowing mandatory POIs to be removed.
- [x] Validate meal candidates through previous -> meal -> next road legs and generic detour limits.
- [x] Preserve road-leg cache and provenance through checkpoints and revisions.
- [x] Verify the prior 39.82 km straight-line span as 50.126 km / 66.9 min by real road routing.
- [x] Rerun Jingwei through the formal Runtime/API path with mandatory, meal, and route feasibility gates.
- [x] Run focused, complete Python, compileall, and frontend regressions for M1E.

Deferred until explicitly approved:

- [ ] Review and create a Git checkpoint for M1E only after explicit approval; do not commit automatically.
- [ ] Decide whether meal entries require explicit clock times before claiming hard schedule verification for meal legs.
- [ ] Add a deterministic multi-attraction real E2E fixture or acceptance Run if stronger live route-gate evidence is required.
- [ ] Investigate the Runtime concurrency `KNOWN_FLAKY` in a separate task.
- [ ] Keep RAG, Story-to-Planning/Chat/UI integration, Experience, Commerce, Video, frontend, and mobile integration deferred until explicitly authorized.
- [x] Create the accepted M2B Git checkpoint (`b6c618f`).
- [ ] Keep `changzhi.claim.fajiushan-yandi-residence` as `review_required` and `internal_only` unless stronger historical evidence is supplied.
- [x] Scope and implement M2C without weakening production eligibility or qualifier preservation.
- [ ] Review and create an M2C Git checkpoint only after explicit approval; do not commit automatically.
- [ ] Define any Planning or Chat integration as a separate milestone that preserves the M2C Gate and validators.
