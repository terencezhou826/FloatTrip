# Project Log

## 2026-08-22 12:43:06 +08:00 - M2B Evidence-Aware Knowledge Retrieval

- Files modified:
  - Added `app/catalog/retrieval.py` with frozen `KnowledgeQuery`,
    `KnowledgeHit`, Evidence/Source snapshots, `KnowledgeContext`, and a
    package-scoped `KnowledgeRetriever`.
  - Exported the retrieval contracts from `app/catalog/__init__.py`.
  - Added `tests/catalog/test_knowledge_retrieval.py` and
    `docs/knowledge/RETRIEVAL.md`.
  - Updated only the canonical tracking documents under `docs/development/`.
- Architecture and safety:
  - Production eligibility runs before ranking and reuses the Repository gate;
    package-local verified `supports` Evidence and verified Sources are also
    required.
  - Structured Region/Theme/Anchor/Claim-type filters combine with deterministic
    Unicode normalization, Chinese character bigrams/trigrams, generic query
    expansions, causal markers, and ordered subsequence matching.
  - Hits retain complete promotion qualifiers, all verified Evidence relations,
    deduplicated Source snapshots, stable IDs, scores, and match reasons.
  - Authority contributes only a small Source-relationship tie-break and is not
    interpreted as truth probability.
- Commands and results:
  - Retriever tests: 25 passed.
  - Catalog tests: 101 passed.
  - Catalog + M1A-M1E focused regression: 203 passed, 5 existing warnings.
  - `python -m compileall -q app`: passed.
  - Complete Python regression: 281 passed, 18 subtests passed, 5 existing
    warnings.
  - Frontend Node tests: 26 passed.
  - Standalone A-F local Catalog demo: all queries completed; production-
    ineligible leakage was 0. The Yandi-residence query returned only weak
    eligible context and `insufficient_direct_match`.
- Current risks:
  - V1 ranking is intentionally lexical and uses a small generic Chinese query
    vocabulary; it is deterministic but not a semantic-search replacement.
  - `include_disputed=true` is explicitly review-oriented and produces a
    warning; default production retrieval excludes disputed Claims.
  - Existing FastAPI lifespan/JWT warnings remain unrelated. Runtime
    concurrency `KNOWN_FLAKY` did not reproduce and Runtime was not modified.
- Next recommended action: review and checkpoint M2B. Do not connect
  `KnowledgeContext` to Planning or LLM generation until M2C is explicitly
  scoped.

## 2026-08-22 12:22:28 +08:00 - M2A Final Audit

- Files modified in this phase:
  - Clarified `docs/knowledge/KNOWLEDGE_MODEL.md`: `primary` describes the
    Source-to-Claim relationship, a modern digital transcription is not an
    ancient physical manuscript, verified official narrative is not historical
    truth, and Retrieval/Generation must preserve qualification.
  - Updated the canonical tracking files under `docs/development/`.
  - No Source, Claim, Evidence, Catalog data, or business code was changed.
- Audit results:
  - Rechecked all 3 public Source URLs and all 13 excerpt/locator pairs; every
    page returned HTTP 200 and every excerpt remained locatable.
  - All 13 Claim scopes, types, Evidence relations, and promotion policies were
    retained. The 12 verified Claims remain production eligible; the Yandi
    residence Claim remains `review_required` + `internal_only`.
  - Verified Claim evidence coverage remains 12/12 (100%); status counts remain
    12 verified, 1 review-required, 0 draft/rejected/disputed.
- Commands and results:
  - Knowledge tests: 31 passed.
  - Catalog + M1A-M1E focused regression: 178 passed, 5 existing warnings.
  - `python -m compileall -q app`: passed.
  - Complete Python regression: 256 passed, 18 subtests passed, 5 existing
    warnings.
  - Frontend Node tests: 26 passed.
  - `git diff --check`: run after documentation updates.
- Current risks:
  - Public Source URLs are not archived and need a future preservation policy.
  - `changzhi.claim.fajiushan-yandi-residence` lacks independent historical
    support and must remain outside production retrieval.
  - Existing FastAPI lifespan/JWT warnings remain unrelated. Runtime
    concurrency `KNOWN_FLAKY` did not reproduce and Runtime was not modified.
- Next recommended action: create an M2A Git checkpoint after approval. Enter
  M2B only under a separate explicit instruction.

## 2026-08-22 11:53:09 +08:00 - M2A Evidence-Grounded Cultural Knowledge Foundation

- Files modified:
  - Extended `app/catalog/models.py`, `loader.py`, `repository.py`, `validation.py`, and Catalog exports with provider-neutral Source, Claim, Evidence, authority, verification, promotion, coverage, and production-eligibility semantics.
  - Added `content/catalog/packages/shanxi/changzhi/knowledge/{sources,claims,evidence}.json` and bumped package content version to `0.2.0`.
  - Added `tests/catalog/test_knowledge.py`, updated current-Catalog version expectations, and added `docs/knowledge/KNOWLEDGE_MODEL.md`.
- Source verification:
  - Directly checked Chinese Text Project `《山海经·北山经》` node `n83673`, a 长子县人民政府/县文旅局 page, and a 长治市地方志研究室 page.
  - Added 3 Sources, 13 Claims, and 13 Evidence records. Twelve Claims are `verified`, one historical assertion is `review_required` + `internal_only`, and none are `disputed`.
  - Verified Claim evidence coverage is `1.0`; 12 Claims satisfy the conservative production-eligibility rule.
- Commands and results:
  - `python -m pytest -q tests/catalog/test_knowledge.py --basetemp .pytest_tmp_m2a_final_knowledge`: 31 passed.
  - Catalog + M1A-M1E focused regression: 164 passed.
  - `python -m compileall -q app`: passed.
  - `python -m pytest -q --basetemp .pytest_tmp_m2a_final_full`: 256 passed, 18 subtests passed, 5 existing warnings.
  - `node --test tests/chat-state.test.js tests/navigation-state.test.js`: 26 passed.
  - Scope, regional-hardcoding, secret, whitespace, and Git diff audits passed; no Planning, Runtime, API behavior, frontend, or mobile code was modified.
- Problems and risks:
  - The default pytest temp root is inaccessible on this Windows account; repository-local `--basetemp` works. No dependency or business-code change was needed.
  - Public source URLs are traceable but not archived locally; link preservation/versioning remains future content-operations work.
  - `changzhi.claim.fajiushan-yandi-residence` remains intentionally `review_required`; it must not enter production retrieval without stronger historical evidence.
  - `KNOWN_FLAKY`: `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` remains tracked and did not reproduce. Runtime was not modified.
- Next recommended action: conduct a human content review, create the M2A Git checkpoint after approval, then scope M2B retrieval against `is_claim_production_eligible()` without weakening evidence or promotion-policy gates.

## 2026-08-21 19:08:50 +08:00 - M0 Baseline

- Files modified: project tracking files and root `AGENTS.md` created after baseline.
- Commands run: Git status, complete and dependency-excluded Python tests, and frontend Node tests.
- Results: frontend 26 passed; dependency-excluded Python baseline 57 passed, 1 failed, 26 errors, 18 subtests passed; complete collection had 2 errors.
- Risks: declared `langgraph-checkpoint-sqlite` was absent locally; Runtime concurrency behavior was non-deterministic.
- Next action: implement the isolated M0 Catalog without connecting it to existing application flows.

## 2026-08-21 19:16:38 +08:00 - M0 Complete

- Files modified: added `app/catalog/`, `content/catalog/`, `tests/catalog/`, and project continuity files.
- Commands run: focused Catalog tests, `python -m compileall -q app/catalog`, executable Python regression tests, frontend Node tests, and scope/hardcoding/Git audits.
- Results: Catalog 17 passed; executable Python regression 75 passed, 26 dependency errors, 18 subtests passed; frontend 26 passed.
- Risks: local checkpoint dependency remained missing; Runtime concurrency test remained flaky.
- Next action: restore the declared local dependency and define M1 separately.

## 2026-08-21 19:28:24 +08:00 - M0.5 Catalog Foundation

- Files modified:
  - Updated `app/catalog/models.py`, `app/catalog/repository.py`, `app/catalog/validation.py`, and `app/catalog/__init__.py`.
  - Updated Shanxi Region registry and the four Changzhi route records under `content/catalog/`.
  - Expanded `tests/catalog/test_catalog_loader.py`.
  - Moved long-term tracking files to `docs/development/` and removed temporary Codex planning files.
- Commands run:
  - `python -m pip install "langgraph-checkpoint-sqlite>=3.0"`
  - Checkpoint import/version verification.
  - `python -m pytest -q tests/catalog --basetemp <system-temp>`
  - `python -m compileall -q app/catalog`
  - `python -m pytest -q --basetemp <system-temp>`
  - `node --test tests/chat-state.test.js tests/navigation-state.test.js`
  - Git whitespace, status, dependency-diff, prohibited-module, and regional-hardcoding audits.
- Results:
  - Initial Catalog run: 26 passed, 1 test assertion failed because it expected a loader-specific Pydantic field-path prefix; the assertion was narrowed to the stable field name without changing business code.
  - Catalog: 27 passed.
  - Compileall: passed.
  - Complete Python: 116 passed, 18 subtests passed, 5 warnings.
  - Frontend: 26 passed.
  - Scope and whitespace audits: passed; no prohibited application modules or dependency declarations changed.
- Environment conclusion: case A. `requirements.txt` already declares `langgraph-checkpoint-sqlite>=3.0`; only the active local Python environment was repaired, with no dependency-file change.
- Current problems and risks:
  - `KNOWN_FLAKY`: `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` failed once in the restored baseline and passed in the final run. Runtime was not modified.
  - All M0/M0.5 files remain untracked until explicitly staged or committed.
- Next recommended action: review and approve M0.5 before defining M1. Do not start M1 implicitly.

## 2026-08-21 20:01:43 +08:00 - M1A Catalog Context Integration

- Files modified:
  - Added `app/planning/catalog_context.py` with immutable `CatalogContext`, generic resolver, and request snapshot freezing helper.
  - Updated Catalog Repository/Loader to retain package-scoped lookup, including disabled package metadata for resolver validation.
  - Added optional `catalog_context` to `TravelPlanState`.
  - Updated Runtime and legacy revision/checkpoint copy points without changing graph nodes, prompts, POI, review, time check, meals, scoring, finalize output, or SSE semantics.
  - Added `tests/test_catalog_context.py` and focused Runtime API coverage.
- Commands run:
  - Focused pre-change and iterative M1A pytest runs.
  - `python -m pytest -q tests/catalog --basetemp <system-temp>`
  - `python -m pytest -q tests/test_catalog_context.py --basetemp <system-temp>`
  - `python -m compileall -q app`
  - `python -m pytest -q --basetemp <system-temp>`
  - `node --test tests/chat-state.test.js tests/navigation-state.test.js`
  - Git whitespace, scope, hardcoding, public-schema, and prohibited-module audits.
- Results:
  - Catalog: 27 passed.
  - M1A dedicated tests: 11 passed; explicit Run API selection/retry/revision tests: 3 passed.
  - Compileall: passed.
  - Complete Python: 130 passed, 18 subtests passed, 5 existing warnings.
  - Frontend: 26 passed.
  - Runtime concurrency known flaky did not reproduce in final runs.
- Errors resolved:
  - Initial expected TDD collection failure before the context module existed.
  - Replaced unsupported `pytest.mark.asyncio` with standard-library `asyncio.run()`; no dependency change.
- Current problems and risks:
  - `KNOWN_FLAKY`: `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` remains tracked from M0/M0.5 despite passing here.
  - M1A carries mandatory anchor IDs but deliberately does not alter candidate POIs or planner behavior.
- Next recommended action: review and checkpoint M1A, then define M1B explicitly before implementing mandatory-anchor planning behavior.

## 2026-08-21 20:17:22 +08:00 - M1B-1 Anchor External POI Binding Foundation

- Files modified:
  - Added provider-neutral Binding enums/model and package collection support in `app/catalog/`.
  - Added generic Anchor/Region candidate discovery in `app/catalog/discovery.py`.
  - Added an Amap discovery adapter in `app/providers/amap/discovery.py`, reusing the existing POI search implementation.
  - Added an empty `content/catalog/packages/shanxi/changzhi/poi_bindings.json`; no candidate or verified identity was persisted.
  - Added Binding and Discovery coverage in `tests/catalog/test_poi_bindings.py` and `tests/test_poi_discovery.py`.
- Commands run:
  - Focused pre-change and iterative M1B-1 pytest runs.
  - `python -m pytest -q --basetemp <workspace-temp> tests/catalog tests/test_catalog_context.py tests/test_runtime_api.py tests/test_poi_discovery.py`
  - `python -m compileall -q app`
  - `python -m pytest -q --basetemp <workspace-temp>`
  - Isolated Runtime concurrency retry.
  - `node --test tests/chat-state.test.js tests/navigation-state.test.js`
  - Amap configuration, scope, hardcoding, whitespace, and Git audits.
  - Removed task-scoped pytest temporary directories after resolving their exact workspace paths.
- Results:
  - M1B-1 focused: 15 passed.
  - Catalog: 38 passed.
  - M1A and Runtime API: 25 passed, 5 existing warnings.
  - Catalog + M1A + M1B-1 focused regression: 67 passed, 5 existing warnings.
  - Compileall: passed.
  - Complete Python: 144 passed, 1 known Runtime concurrency failure, 18 subtests passed, 5 existing warnings.
  - Complete Python excluding only that known flaky: 144 passed, 1 deselected, 18 subtests passed, 5 existing warnings.
  - Frontend: 26 passed.
- Discovery result:
  - `.env.local` and `AMAP_API_KEY` are absent, so no real Amap request was made and no candidate was fabricated or persisted.
- Current problems and risks:
  - The default Windows pytest temp root returned `WinError 5`; all tests using `tmp_path` were run with task-scoped workspace `--basetemp` directories instead. No business code was changed for this environment issue.
  - `KNOWN_FLAKY`: `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` observed peak concurrency 1 instead of 2 in the full run and isolated retry. Runtime was not modified.
  - No external POI identity is currently eligible for runtime use because the formal Binding collection is empty.
- Next recommended action: content operations should configure Amap and review real candidates before any explicit `verified` Binding is authored. M1B-2 must remain separate and must fail or require review when a mandatory Anchor has no verified Binding.

## 2026-08-21 20:39:00 +08:00 - M1B-1.5 POI Binding Verification Provenance

- Files modified:
  - Extended `ExternalPoiBinding` in `app/catalog/models.py` with provider-neutral `verification_method`, `verified_at`, and `verification_note` fields.
  - Exported the controlled `PoiVerificationMethod` enum from `app/catalog/__init__.py`.
  - Expanded `tests/catalog/test_poi_bindings.py` with candidate, verified, rejected, invalid enum, and JSON Loader/Repository round-trip cases.
  - Updated the long-term files under `docs/development/`.
- Commands run:
  - Failing-first and focused Binding provenance pytest runs.
  - `python -m pytest -q --basetemp <workspace-temp> tests/catalog`
  - `python -m pytest -q --basetemp <workspace-temp> tests/test_catalog_context.py tests/test_runtime_api.py`
  - `python -m pytest -q --basetemp <workspace-temp> tests/catalog/test_poi_bindings.py tests/test_poi_discovery.py`
  - Two complete Python regression runs and one run excluding only the documented Runtime concurrency flaky.
  - `node --test tests/chat-state.test.js tests/navigation-state.test.js`
  - Empty-content, prohibited-field, Planning/Runtime/Chat scope, whitespace, and Git audits.
- Results:
  - Catalog: 45 passed.
  - M1A and Runtime API: 25 passed, 5 existing warnings.
  - M1B-1: 22 passed.
  - Complete Python passed once before the final enum assertion was added; the final 152-test rerun produced 151 passed and the known Runtime concurrency failure. Excluding only that flaky produced 151 passed, 1 deselected, and 18 subtests passed.
  - Frontend: 26 passed.
- Validation contract:
  - Candidate Bindings may omit all verification provenance.
  - Rejected Bindings may retain method and note.
  - Verified Bindings require a controlled verification method and an ISO 8601 datetime; note remains optional.
- Current problems and risks:
  - `KNOWN_FLAKY`: `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` passed one complete run and failed the next with peak concurrency 1. Runtime was not modified.
  - Formal `poi_bindings.json` remains empty, and no real POI verification was performed.
- Next recommended action: checkpoint the accepted M1B-1/M1B-1.5 work after review, then configure Amap and perform human candidate verification before defining M1B-2 enforcement.

## 2026-08-21 22:35:25 +08:00 - M1B-2 Verified Mandatory Anchor Enforcement

- Files modified:
  - Added `app/providers/poi_identity.py`, `app/providers/amap/identity.py`, and Amap Place Detail v3 exact-ID lookup support.
  - Added `app/planning/mandatory_pois.py` with the Provider-neutral resolver, identity merge, constraint formatting, and deterministic validator.
  - Extended Planning schemas, nodes, prompts, graphs, checkpoints, and Finalize identity projection without changing public API or SSE event semantics.
  - Added the single approved verified Fajiushan Binding to the Changzhi package; no other Anchor Binding was added.
  - Added `tests/test_mandatory_pois.py` and `tests/test_mandatory_planning.py`; updated superseded M1A/Catalog assertions.
- Commands run:
  - Failing-first and focused Catalog/M1A/M1B pytest runs using repository-local `--basetemp` directories.
  - `python -m compileall -q app`
  - Two complete `python -m pytest -q` regression runs.
  - `node --test tests/chat-state.test.js tests/navigation-state.test.js`
  - Real read-only Amap exact-ID smoke lookup for `B0FFF49AFB` after `load_local_env()`.
  - Git whitespace, scope, hardcoding, status, and diff audits.
- Results:
  - Catalog/M1A/M1B focused regression: 91 passed.
  - M1B-2 resolver/planning focused coverage: 31 passed within the focused suites.
  - Compileall: passed.
  - Complete Python: 183 passed, 18 subtests passed, 5 existing warnings.
  - Frontend: 26 passed.
  - Real Amap Place Detail v3 lookup returned the same ID `B0FFF49AFB`, name `发鸠山景区`, district `长子县`, address `326省道附近`, and the verified coordinates.
- Runtime behavior:
  - Mandatory Anchors resolve only through one verified Binding and exact Provider ID; candidate/rejected/missing/ambiguous/unsupported/mismatched identities fail explicitly.
  - Mandatory POIs merge after ordinary search/rating filtering and deduplicate only by `provider + external_poi_id`.
  - Every Planner output, including Time Check corrections and revision paths, passes an internal deterministic identity check before continuing.
  - Internal nodes emit no new public progress events; Finalize never inserts missing POIs.
- Current problems and risks:
  - `KNOWN_FLAKY`: `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` remains tracked but did not reproduce in either final full run. Runtime concurrency was not modified.
  - A saved Catalog snapshot whose package version is no longer present fails mandatory resolution explicitly; multi-version historical Catalog storage remains out of scope.
  - Existing FastAPI lifespan deprecation and local `JWT_SECRET` warnings remain unrelated.
- Next recommended action: review and checkpoint M1B-2. M1C may be specified separately after acceptance; do not start it implicitly.

## 2026-08-21 23:34:30 +08:00 - M1C OpenAI-Compatible Provider Foundation (Real E2E Blocked)

- Files modified:
  - Added `app/llm/openai_compatible.py` with generic ChatOpenAI construction and strict Pydantic function calling.
  - Extended `app/llm/factory.py` with the `openai_compatible` provider while preserving existing DeepSeek and Doubao dispatch.
  - Added empty OpenAI-compatible settings and comments to `.env.example`.
  - Added Provider unit coverage in `tests/test_openai_compatible_llm.py`.
  - Updated the long-term files under `docs/development/`.
- Local environment repair:
  - `requirements.txt` already declared `langchain-openai`; only the active local environment was missing it.
  - Installed `langchain-openai 1.6.0`. The initial resolver chose `openai 3.3.1`, which conflicted with installed `litellm<3`, so the local SDK was corrected to `openai 2.54.0`; `pip check` passes.
  - No dependency declaration file was changed.
- Commands run:
  - Failing-first and passing Provider pytest runs.
  - Existing LLM/mandatory focused tests.
  - Catalog, M1A, M1B, and M1C focused regression.
  - `python -m compileall -q app`.
  - Complete `python -m pytest -q` regression.
  - `node --test tests/chat-state.test.js tests/navigation-state.test.js`.
  - `.env.local` presence-only audit through `load_local_env()`; no secret values were printed.
  - Provider-brand, regional-branch, whitespace, and Git audits.
- Results:
  - Provider red baseline: 6 failed, 2 passed; final Provider suite: 8 passed.
  - Existing LLM/mandatory focused: 20 passed.
  - Catalog + M1A + M1B + M1C focused: 99 passed.
  - Compileall: passed.
  - Complete Python: 191 passed, 18 subtests passed, 5 existing warnings.
  - Frontend: 26 passed.
- Real smoke/E2E result:
  - `AMAP_API_KEY` is present, but `LLM_PROVIDER`, `OPENAI_COMPATIBLE_API_KEY`, `OPENAI_COMPATIBLE_BASE_URL`, and `OPENAI_COMPATIBLE_MODEL` are absent from `.env.local`.
  - The first failed layer is LLM Provider configuration. Per M1C rules, no real Chat request, structured-output smoke, exact Amap prerequisite chain, or formal Runtime/API Planning Run was attempted.
  - No fallback to legacy `DEEPSEEK_API_KEY`, fake data, plain-text parsing, or direct Planner invocation was used.
- Current problems and risks:
  - M1C's real Jingwei end-to-end acceptance target remains incomplete until the generic Provider variables are configured and both LLM smokes pass.
  - `KNOWN_FLAKY`: `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` remains tracked but did not reproduce in this complete run. Runtime was not modified.
  - Existing FastAPI lifespan deprecation and local `JWT_SECRET` warnings remain unrelated.
- Next recommended action: configure the four generic LLM variables in the ignored `.env.local`, rerun Chat and structured-output smokes, then execute the Jingwei Run through `POST /api/runs`. Do not enter M2 before that real M1C verification succeeds.

## 2026-08-22 00:04:28 +08:00 - M1C Real Jingwei Runtime/API E2E Completion

- Real environment gates:
  - Loaded ignored `.env.local` through `load_local_env()`; all five required settings were present without printing keys.
  - Provider `openai_compatible`, endpoint host `127.0.0.1`, model `gpt-5.6-sol`.
  - Real factory Chat returned `OK`.
  - Real strict function calling returned a typed `SmokeSchema(ok=True, message="OK")`; no text fallback occurred.
- Catalog/Amap/weather prerequisites:
  - Catalog validation passed for schema `1.0`, content `0.1.0`, package `shanxi.changzhi`, route `changzhi.route.jingwei-fajiushan`.
  - Mandatory Anchor `changzhi.anchor.fajiushan` resolved through the unique verified Binding `amap / B0FFF49AFB`.
  - Live Amap Place Detail v3 returned `B0FFF49AFB / 发鸠山景区`, district `长子县`, coordinates `112.640827,36.146452`.
  - Live weather selected the nearest future date `2026-08-22`: daytime light rain, night clear, 29/19 C.
- Formal Runtime/API result:
  - Created Run `c380a146-1be1-4cdc-8f72-a4cf10ad46a4` through `POST /api/runs`; it succeeded and persisted itinerary `77de3ade-b773-477b-9112-c69bccc629e2`.
  - Public pipeline completed intent, query rewrite, attraction search, Planner, Reviewer, Time Check, meal search/recommendation, Spot Tips, and Finalize with no retry.
  - Candidate pool contained 26 normal Amap candidates plus one verified mandatory candidate.
  - Final attractions were mandatory `发鸠山景区 / B0FFF49AFB` and dynamic `翠云山法兴寺景区 / B016300KB2`; both trace to the real candidate pool.
  - Mandatory machine validation passed with the exact Provider ID, curated Anchor ID, and `is_mandatory=true`; no missing mandatory identity remained.
  - Run CatalogContext exactly matched the saved checkpoint snapshot.
  - Reviewer passed on round 1 with score 91 and a rain-safety advisory. Time Check passed round 1 with no reported opening-time violations. Spot Tips covered both attractions.
  - Meal search found no lunch candidate within the existing search boundary around Fajiushan, so the plan explicitly records no lunch restaurant; dinner is the real Amap candidate `老地方风味饭店`.
- Automated regression:
  - First focused run exposed three missing-config tests reloading the now-populated real `.env.local`; test isolation was corrected without production changes.
  - Catalog + M1A + M1B + M1C focused: 99 passed.
  - Complete Python: 191 passed, 18 subtests passed, 5 existing warnings.
  - Compileall: passed. Frontend: 26 passed.
- Files modified in this completion phase:
  - Test-only isolation adjustment in `tests/test_openai_compatible_llm.py`.
  - Long-term tracking files under `docs/development/`.
  - No Provider, Planning, Runtime, API, Catalog, frontend, or mobile production code was changed after the successful real call.
- Current problems and risks:
  - Lunch is unresolved for this result; the current 1 km restaurant search around Fajiushan returned no candidates. The pipeline handled this honestly but the itinerary lacks a concrete midday meal.
  - Exact 800 RMB total cost is not verifiable because attraction and transport price data are incomplete.
  - Time Check verifies reported opening-time compatibility through the existing LLM stage; travel-time feasibility is not a deterministic hard validator.
  - Local Redis was unavailable and cache disabled itself; provider calls continued normally.
  - Existing FastAPI lifespan and missing `JWT_SECRET` warnings remain. The known Runtime concurrency flaky did not reproduce.
- Next recommended action: review and checkpoint M1C. Before M2, explicitly accept the lunch-search limitation or define a separate generic meal-coverage improvement; do not hide it as a successful lunch recommendation.

## 2026-08-22 08:08:11 +08:00 - M1D Generic Meal Coverage Fallback

- Files modified:
  - Added `app/planning/meal_coverage.py` with a Provider-neutral bounded coverage policy.
  - Extended `app/planning/helpers.py` to retain Amap POI identity and reported distance for restaurant candidates.
  - Extended `app/planning/nodes.py` with staged meal discovery, route-aware lunch fallback, coverage metadata, identity-based duplicate handling, and honest uncovered output.
  - Added `tests/test_meal_coverage.py` for policy, node integration, provenance, ordinary non-Catalog behavior, Provider failures, and Finalize output.
  - Updated the three long-term documents under `docs/development/`.
- Policy:
  - Search levels are 1000 m, 3000 m, and 5000 m; 5000 m is the hard maximum.
  - Each level searches the primary meal anchor and then an optional secondary route anchor, stopping on the first identified non-empty candidate set.
  - Candidate identity is `provider + external_poi_id`; same identity is deduplicated while same-name/different-ID candidates remain distinct.
  - Status is `COVERED` only for the primary anchor at level 0, `FALLBACK_EXPANDED` for a secondary anchor or later radius, and `UNCOVERED` after every bounded attempt is empty.
  - Provider errors propagate and are never converted into empty results. No Planner, mandatory POI, Catalog, Runtime/SSE, frontend, or mobile behavior was changed.
- Commands run:
  - Focused Meal/mandatory tests and Catalog/M1A/M1B/M1C/M1D regression with repository-local `--basetemp` directories.
  - `python -m compileall -q app`.
  - Complete `python -m pytest -q --basetemp .pytest_tmp_m1d_full` regression.
  - `node --test tests/chat-state.test.js tests/navigation-state.test.js`.
  - Live Amap meal discovery for the approved Fajiushan and Cuiyunshan Faxingsi POIs.
  - Formal Jingwei Runtime/API E2E, plus hardcoding, secret, whitespace, and Git audits.
- Results:
  - Meal/mandatory focused: 44 passed.
  - Final post-cleanup Meal verification: 13 passed.
  - Catalog + M1A + M1B + M1C + M1D focused: 112 passed.
  - Compileall: passed.
  - Complete Python: 204 passed, 18 subtests passed, 5 existing warnings.
  - Frontend: 26 passed.
  - The known Runtime concurrency flaky did not reproduce; Runtime was not modified.
- Live discovery:
  - Fajiushan primary anchor at level 0/1000 m returned 0 identified candidates.
  - Cuiyunshan Faxingsi secondary anchor at level 0/1000 m returned 9 identified real Amap candidates, so levels 1 and 2 were not attempted and status was `FALLBACK_EXPANDED`.
  - A representative candidate was `老地方风味饭店 / amap / B0FFFZ7ZGA`, address `丹慈路与平安街交叉口西南80米`, coordinates `112.92015,35.982461`, rating 4.3, reported cost 30, and Provider distance 690 m from the secondary anchor.
- Formal Runtime/API E2E:
  - Run `40f2defd-070e-41df-9a93-34d7212886b3` succeeded and persisted itinerary `7b266426-8271-4299-bb67-05431241cf74` without retry.
  - Frozen CatalogContext, exact mandatory Fajiushan identity, attraction and meal provenance, Reviewer, Time Check, Spot Tips, and Finalize all passed.
  - Lunch was the real Amap candidate `桂花蒸饺馆 / B0G2SSJUAM`, found at level 1/3000 m around the afternoon secondary anchor `漳泽湖国家城市湿地公园`; status was `FALLBACK_EXPANDED`.
  - The final-route straight-line distance from Fajiushan to lunch was 39.82 km. M1D improves truthful candidate coverage but does not implement corridor or route optimization, so this result must not be represented as distance-optimal.
  - Dinner was `申一刀厨师班 / B0JUJAJKUD`, 126 m from Shangdang Gate at level 0/1000 m with status `COVERED`.
- Current problems and risks:
  - The 39.82 km lunch detour remains a route-feasibility limitation for a future explicitly scoped corridor-aware policy.
  - Exact 800 RMB total remains unverifiable because reliable attraction and transport pricing is incomplete.
  - Existing FastAPI lifespan deprecation and local `JWT_SECRET` warnings remain unrelated.
  - `KNOWN_FLAKY`: `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` remains tracked but did not reproduce.
- Next recommended action: review M1D and create a Git checkpoint only after explicit approval. Decide separately whether the residual lunch detour blocks M2; do not enter M2 implicitly.

## 2026-08-22 08:57:19 +08:00 - M1E Deterministic Route Feasibility and Travel-Time Matrix

- Files modified:
  - Added `app/providers/travel_time.py` and `app/providers/amap/travel_time.py` for Provider-neutral driving contracts and the Amap Driving v3 adapter.
  - Added `app/planning/route_feasibility.py` for lazy per-Run OD caching, selected-adjacent-leg validation, route policy, and meal-detour policy.
  - Extended Planning state, graph, nodes, prompts, and revision checkpoint projection with deterministic route feasibility and road-leg provenance.
  - Extended Meal Search to validate previous -> meal -> next road corridors before retaining candidates.
  - Added `tests/test_route_feasibility.py` and expanded `tests/test_meal_coverage.py`.
- Commands run:
  - Focused M1E/Meal/Mandatory and Catalog/M1A-M1E pytest suites.
  - `python -m compileall -q app`.
  - Complete `python -m pytest -q --basetemp .pytest_tmp_m1e_full`.
  - `node --test tests/chat-state.test.js tests/navigation-state.test.js`.
  - Live Amap Driving v3 smoke for Fajiushan, the M1D lunch, and Zhangze Lake.
  - Formal Jingwei execution through `POST /api/runs`, plus scope, hardcoding, secret, whitespace, and Git audits.
- Results:
  - M1E/Meal/Mandatory focused: 46 passed.
  - Catalog + M1A-M1E focused: 133 passed.
  - Complete Python: 225 passed, 18 subtests passed, 5 existing warnings.
  - Compileall: passed. Frontend: 26 passed.
  - The Runtime concurrency `KNOWN_FLAKY` did not reproduce; Runtime concurrency was not modified.
- Architecture and policy:
  - Planning depends on `TravelTimeProvider`, `TravelPoint`, and `TravelLeg`, not Amap response fields. Current mode is driving.
  - `TravelTimeMatrix` queries only selected adjacent OD pairs, persists a serializable per-Run cache, and reuses unchanged legs after Planner correction.
  - Hard route checks require actual duration plus a 10-minute buffer to fit the scheduled gap and cap a leg at 150 km. A 50 km leg and two hours of daily driving are soft warnings.
  - Meal policy caps extra detour at 20 minutes, total meal travel at 90 minutes, and any meal leg at 60 minutes; candidates are identified only by `provider + external_poi_id`.
  - Provider errors and missing identities remain explicit failures. Haversine remains only as a legacy display field and never impersonates a road result.
- Live routing evidence:
  - Fajiushan -> Zhangze Lake: 50.126 km / 66.9 min by road, versus the prior 39.82 km straight-line display value.
  - Fajiushan -> Guihua Steamed Dumpling Restaurant: 51.484 km / 64.0 min.
  - Restaurant -> Zhangze Lake: 3.136 km / 4.5 min.
  - Via-meal total: 54.620 km / 68.5 min; detour over direct: 4.494 km / 1.6 min.
  - The M1D meal is rejected because its first leg exceeds the generic 60-minute meal-leg limit, despite its small detour.
- Formal Runtime/API E2E:
  - Run `ded3572b-f5d7-4479-bb16-6923565d59ee` succeeded and persisted itinerary `bc1d4f8b-cecc-4e74-86ba-8fc629a4bcd0`.
  - Catalog snapshot remained package `shanxi.changzhi`, schema `1.0`, content `0.1.0`, route `changzhi.route.jingwei-fajiushan`.
  - The relaxed final route selected mandatory Fajiushan (`B0FFF49AFB`) from 09:30 to 15:30 and no dynamic attraction. Mandatory, Reviewer, Time Check, route feasibility, Spot Tips, and Finalize passed.
  - Lunch and dinner used the same real fallback candidate Nongxiangju (`B0L309LL0Z`). Fajiushan -> restaurant was 5.526 km / 6.6 min; same restaurant identity -> itself was 0 km / 0 min.
  - Final driving total was 5.526 km / 6.6 min with complete Provider road data and `meal_route_feasible=true`.
- Current problems and risks:
  - Because only one attraction was selected, the E2E had no inter-attraction leg; route feasibility is valid for the selected route but does not demonstrate a corrected multi-attraction Run.
  - Meal entries have no explicit start/end clock times. Their road legs are verified, but scheduled meal gaps remain `ROAD_VERIFIED`, not hard schedule `PASS`.
  - The one available fallback restaurant was selected for both lunch and dinner and had a 3.2 Provider rating; the result warns about the duplicate and sparse local coverage.
  - Exact 800 RMB total remains unverifiable because reliable attraction and transport pricing is incomplete.
  - A no-date E2E entered `waiting_user`; existing startup reconciliation marks orphaned waiting Runs failed after process restart. This Runtime behavior was observed but not changed.
  - Existing FastAPI lifespan, missing local `JWT_SECRET`, and unavailable Redis warnings remain unrelated.
- Next recommended action: review and checkpoint M1E only after explicit approval. Do not enter M2 implicitly.

## 2026-08-22 13:18:50 +08:00 - M2C Evidence-Grounded Cultural Answering

- Files modified:
  - Added `app/knowledge/models.py`, `prompts.py`, `service.py`, and package exports for the standalone answer layer.
  - Added `tests/test_knowledge_answering.py` and `docs/knowledge/ANSWERING.md`.
  - Updated the three canonical project documents under `docs/development/`.
- Architecture:
  - The service executes `KnowledgeAnswerRequest -> M2B KnowledgeRetriever -> KnowledgeContext -> deterministic Answerability Gate -> strict structured LLM -> deterministic validation`.
  - Insufficient evidence bypasses the LLM. Successful answers freeze Catalog package/schema/content versions and validate Claim, Evidence, Source, locator, quote, policy, qualifier, and production eligibility against the original Context.
  - Claim-type checks reject unnegated historical promotion, including promotion after contrast markers. Location guidance preserves relative-location Evidence without inferring a target's administrative location or coordinates.
- Commands run:
  - Focused M2C, M2B retrieval, Knowledge, Catalog, and M1A-M1E pytest suites.
  - `python -m compileall -q app`.
  - Complete `python -m pytest -q --basetemp .pytest_tmp_m2c_full_final`.
  - `node --test tests/chat-state.test.js tests/navigation-state.test.js`.
  - Real OpenAI-compatible structured-output runs for A-F and deterministic no-LLM runs for three hallucination-injection questions.
- Results:
  - M2C: 25 passed. M2B retrieval + Knowledge: 56 passed. Catalog: 101 passed.
  - M1A-M1E/M2 focused: 214 passed. Compileall passed.
  - Complete Python: 306 passed, 18 subtests passed, 5 existing warnings. Frontend: 26 passed.
  - Real A-F all met the quality gate. F returned `insufficient_evidence` without an LLM call or internal Claim leakage. The year, coordinate, and archaeology injection questions also bypassed the LLM.
  - Production-ineligible leakage: 0. Citation hallucination: 0. Required qualifier violations: 0. Context-external cultural facts: 0.
- Current problems and risks:
  - Deterministic validation verifies identity, provenance, policy, qualifiers, numbers, and known claim-type promotion phrases; unrestricted semantic entailment remains outside this non-RAG first version.
  - Public Source URL archival/versioning remains undefined.
  - Existing FastAPI lifespan and local `JWT_SECRET` warnings remain unrelated.
  - `KNOWN_FLAKY`: `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` did not reproduce; Runtime was not modified.
- Next recommended action: review M2C and create a Git checkpoint only after explicit approval. Do not connect Knowledge answering to Planning or Chat without a separately scoped milestone.

## 2026-08-22 13:41:44 +08:00 - M3 stopped at M3A Catalog regression gate

- Files modified before the gate:
  - Extended Catalog models, Loader, Repository, validation, and exports with Story Blueprint/Chapter collections.
  - Added one Jingwei Blueprint and five Chapter records under `content/catalog/packages/shanxi/changzhi/stories/`.
  - Added `tests/catalog/test_stories.py` with 34 Story domain and validation cases.
- Commands run:
  - Starting M2C/M2B/Knowledge/Catalog gate: 126 passed.
  - Package/route/verified Fajiushan binding integrity check: passed.
  - Story tests: 34 passed.
  - Complete Catalog tests: 5 failed, 130 passed.
  - `git diff --check`: no whitespace errors; only existing LF-to-CRLF notices.
- First failed gate:
  - `M3A Catalog regression`.
  - Existing compatibility fixtures remove the copied package's Knowledge directory or POI Binding file while leaving the newly added Story collections intact. The Story Validator then correctly rejects dangling Claim or POI Binding references.
  - Failures: two Knowledge compatibility tests and three POI Binding compatibility/query tests.
- Safety status:
  - Story-specific tests passed; one Blueprint and five Chapters load normally.
  - Required Claim eligibility passed, non-production leakage was 0, and the internal Yandi Claim reference count was 0.
  - M3B, M3C, and M3D were not started. No Planning, Runtime, Chat, frontend, mobile, Knowledge data, or M2C code was changed for M3.
- Safe next action: update the unrelated compatibility test fixtures so an emulated legacy package also omits `stories/`, or otherwise supplies a self-consistent Story dependency set. Do not weaken Story dangling-reference validation. Then rerun M3A from its Story and Catalog gates.

## 2026-08-22 14:14:56 +08:00 - M3 Evidence-Grounded Story Engine Complete

- Compatibility repair:
  - Confirmed all five M3A Catalog failures came from test fixtures that removed Knowledge or POI Binding collections while retaining newer Stories that referenced them.
  - Updated only the affected test fixtures to remove `stories/` from those historical snapshots. Production Story validation was not weakened.
- Architecture and files:
  - Added generic Story Blueprint/Chapter Catalog models, recursive loading, Repository access, cross-collection validation, one Jingwei Blueprint, and five curated Chapters.
  - Added standalone `app/story/` generation and binding services with strict structured output, M2C-derived deterministic grounding checks, exact Provider POI identity placement, immutable version snapshots, and reserved media/experience slots.
  - Added Story domain, generation, and binding tests plus `docs/story/STORY_MODEL.md`, `STORY_GENERATION.md`, and `STORY_BINDING.md`.
- Real M3D Runtime/API E2E:
  - Used isolated local Runtime databases, real Amap, and the configured OpenAI-compatible/Sub2API provider. Run `1054358a-11ef-40da-9bfc-ef57c09c6161` succeeded and persisted itinerary `c0b75c5c-721b-424b-9786-7f9c715ff594`.
  - The one-day family itinerary retained mandatory `amap / B0FFF49AFB`, added two dynamic attractions, selected real lunch and dinner candidates, and completed Planner, Reviewer, Time Check, route feasibility (`FEASIBLE`), meal, Spot Tips, and Finalize.
  - Real Story generation produced all five Chapters and package `story-package.7a0534bac6da449adb209953`; the first four Chapters matched the mandatory stop by exact Provider identity and the final reflection Chapter remained context-only.
- Safety results:
  - Production-ineligible leakage, internal-only leakage, Citation hallucination, qualifier violation, Context fact violation, forbidden Claim references, name-only binding, dynamic POI forcing, itinerary mutation, and Knowledge mutation: all 0.
  - All Chapter grounding coverage values were 1.0. StoryPackage validation passed with no unplaced Chapters. Unsupported Yandi residence, birth-year, historical-dating, archaeology, unsupported coordinate, heritage-grade, and scenic-history content was absent.
- Commands and regression results:
  - Story/Knowledge/Catalog focused: 197 passed.
  - M1A-M1E focused: 102 passed, 5 existing warnings.
  - Complete Python: 377 passed, 18 subtests passed, 5 existing warnings.
  - Frontend Node tests: 26 passed. `compileall` and `git diff --check`: passed.
  - Removed all repository-local `.pytest_tmp_m3*` artifacts after verification; final hardcoding scan, `git diff --stat`, and `git status --short` were read-only.
- Current problems and risks:
  - The first E2E driver closed while the Run was waiting for date input, so startup reconciliation correctly marked it `server_restarted`; the formal `/retry` and `/resume` flow then completed successfully in one application lifecycle.
  - Local Redis remained unavailable and cache disabled itself without blocking Provider calls. Existing FastAPI lifespan and local `JWT_SECRET` warnings remain unrelated.
  - Story prose is intentionally concise because factual text is restricted to approved Claim wording. No Story UI, GPS trigger, Video, Experience, Commerce, or additional route content was implemented.
  - `KNOWN_FLAKY`: Runtime concurrency did not reproduce; Runtime behavior was not modified.
- Next recommended action: review and create an M3 Git checkpoint only after explicit approval. Do not enter M4 implicitly.

## 2026-08-22 15:24:44 +08:00 - M4 stopped at M4D real Runtime gate

- Files modified before the gate:
  - Added generic Experience Catalog models, loading, Repository queries, validation, one Jingwei family Blueprint, and five Activities.
  - Added standalone `app/experience/` evidence-safe generation, deterministic safety validation, exact-identity itinerary binding, weather adaptation, and focused tests.
  - Updated Changzhi Catalog content version to `0.3.0` and compatibility fixtures to omit later `experiences/` data from historical snapshots.
- Commands and results:
  - M4 starting Story/Knowledge/Catalog gate: 197 passed.
  - M4A Experience Catalog: 60 passed; full Catalog: 195 passed; `compileall` and `git diff --check` passed.
  - M4B generation: 37 passed; relevant Experience/Story/Knowledge gate: 159 passed; real OpenAI-compatible generation produced five validated Activities with grounding coverage 1.0 and all fact/safety counters zero.
  - M4C binding: 16 passed; combined generation/Story/Experience binding gate: 67 passed; exact identity, weather adaptation, and mutation counters passed.
  - M4D formal Runtime/API Run `9f2911fd-8564-4b4f-a85d-0fafcc49837e` froze Catalog Context `0.3.0` but did not reach a terminal state within the 1200-second driver deadline.
- Stop reason and risk:
  - First failed gate: M4D real itinerary completion. No itinerary was available, so real StoryPackage and final ExperiencePackage generation/binding were not executed.
  - Full Python/frontend regressions, final hardcoding audit, M4 documentation, and Git final audit were not executed after the HARD FAIL.
  - Runtime concurrency remains `KNOWN_FLAKY`, but this timeout was a separate real Provider/Runtime non-termination and was not classified as that known flaky test.
- Safe next action: diagnose the timed-out Run with per-node Runtime events and bounded Provider timings, then rerun M4D from the formal Runtime/API gate. Do not weaken Experience, identity, evidence, or safety validation, and do not enter M5.

## 2026-08-22 16:09:20 +08:00 - M4D-0 diagnosed; M4D stopped at Experience generation

- Read-only timeout diagnosis:
  - The failed Run `9f2911fd-8564-4b4f-a85d-0fafcc49837e` used an auto-cleaned isolated database, so no record, event, or checkpoint remained in project databases.
  - The E2E harness polled for the nonexistent `waiting_input` status while the formal Runtime protocol uses `waiting_user`; this classified the prior timeout as `A. WAITING_USER SEMANTICS`.
  - Existing Runtime/API and checkpoint resume tests passed (`15 passed`), and Mandatory/Route Feasibility tests passed (`32 passed`). No production Runtime, Planning, SSE, or Provider code was changed.
- Real rerun:
  - Formal Run `87e1e50d-e4fa-4817-8e8d-563859f46480` entered `waiting_user` after Intent, resumed through `POST /api/runs/{id}/resume`, and succeeded in 174.4 seconds.
  - Persisted itinerary: `84f32a03-2323-468f-b7ca-81459719cf1e`; 18 durable events and 16 LangGraph checkpoints were retained in an isolated diagnostic directory.
  - Real Story generation completed successfully.
- First new HARD FAIL:
  - Real Experience generation failed after its single permitted repair attempt with `validation_failed: observation_target_unstructured`.
  - Experience binding, final safety/fact/mutation audits, full regression, M4 documentation, and final Git audit were not executed.
- Safe next action: inspect the generated Activity failure using a bounded, non-production diagnostic that records only the Activity ID and validator issue, then determine whether the prompt/schema contract has a generic fix. Do not weaken observable-reality validation or retry the full M4D chain until justified.

## 2026-08-22 16:50:39 +08:00 - M4D-1 generic repair passed tests; real five-Activity gate stopped

- Diagnosis and files modified:
  - Reproduced `observation_target_unstructured` on the family-question Activity when a negated safety clause contained `不分头寻找线索`; the initial output failed and the permitted repair passed.
  - Replaced the optional generic/Claim-grounded target list with a required, Catalog-owned four-mode ObservationTarget contract shared by curated and generated Activities.
  - Updated `app/catalog/models.py`, `app/catalog/validation.py`, `app/catalog/__init__.py`, `app/experience/models.py`, `app/experience/prompts.py`, `app/experience/safety.py`, `app/experience/__init__.py`, the five Jingwei Experience Activity records, `tests/test_experience_generation.py`, and added `tests/test_observable_reality_contract.py`.
- Commands and results:
  - Read-only recovery confirmed successful Runtime Run `87e1e50d-e4fa-4817-8e8d-563859f46480`, itinerary `84f32a03-2323-468f-b7ca-81459719cf1e`, and frozen Catalog `0.3.0`; no Planning rerun occurred.
  - `python -m compileall -q app tests`: passed; Catalog load smoke: five Activities.
  - Observable Reality plus Experience generation: 56 passed.
  - Experience Domain/Generation/Observable/Safety/Binding with repository-local basetemp: 132 passed.
  - Bounded real family-question retest: passed with `target_mode=none` and all grounding/safety counters zero.
- First new HARD FAIL:
  - Real five-Activity generation stopped on the first Activity, arrival-observation, after the single permitted repair with `validation_failed: observation_target_not_visible`.
  - No ExperiencePackage was produced; final regressions, hardcoding audit, M4 completion docs, checkpoint, and M5 were not executed.
- Current risk and safe next action:
  - The complete structured target contract is now present, but the Provider did not keep the curated target text visible after one repair. Do not weaken the Validator or retry the full five-Activity flow.
  - Next perform one bounded, non-sensitive capture of arrival-observation initial/repair structured fields to determine whether the remaining mismatch is Prompt wording or Provider adherence.

## 2026-08-22 17:07:40 +08:00 - M4D-2 renderer gates passed; stopped before real retest

- Diagnosis and files modified:
  - Confirmed the arrival-observation initial and repair outputs retained the structured `visitor_selected_visible_object` target but did not reproduce the exact curated `target_text`; this is display integrity, not fact safety.
  - Added `RenderedExperienceActivity` and a generic deterministic renderer that combines the trusted ObservationTarget and hard safety constraints with validated LLM facilitation prose. Raw generation remains embedded for audit.
  - Kept `observation_target_not_visible` on rendered output. Raw output still passes the existing fact, Citation, qualifier, text-safety, identity, and current-presence Evidence validators.
  - Updated `app/experience/{models,rendering,service,safety,prompts,__init__}.py` and focused Experience tests. No Catalog content, Knowledge, Story, Planning, Runtime, Web, or Mobile logic was changed in M4D-2.
- Commands and results:
  - `python -m pytest tests/test_observable_reality_contract.py tests/test_experience_generation.py tests/test_experience_binding.py tests/catalog/test_experiences.py -q --basetemp=.pytest_tmp_m4d2_contract`: 145 passed.
  - `python -m pytest tests/catalog tests/test_knowledge_answering.py tests/test_story_generation.py tests/test_story_binding.py tests/test_observable_reality_contract.py tests/test_experience_generation.py tests/test_experience_binding.py -q --basetemp=.pytest_tmp_m4d2_m4abc`: 342 passed.
  - `python -m compileall -q app tests`: passed.
  - Read-only preserved-database audit found one itinerary, 18 Runtime events, 16 LangGraph checkpoints, and no persisted GeneratedStory or StoryPackage table/file.
- First failed gate:
  - The required formal Story input/snapshot for the bounded real arrival Activity is no longer reusable. Only the real itinerary and Planning checkpoints persist; replacing the missing Story with a test fixture or regenerating it would violate the explicit M4D-2 gate.
  - No real Activity Provider call, five-Activity generation, binding, final regression, M4 completion documentation, commit, or push was performed.
- Safe next action: obtain or explicitly authorize reconstruction of the exact same-version formal GeneratedStory/StoryPackage snapshot, then resume at the single arrival-observation real gate. Do not rerun Planning and do not substitute test fixture content for a real Story snapshot.

## 2026-08-22 18:05:52 +08:00 - M4 Evidence-Safe Experience Engine Complete

- Formal recovery and persistence:
  - Final read-only search confirmed the earlier formal Story snapshot was not persisted. User authorized exactly one same-version regeneration; that one call succeeded and was not repeated.
  - Formal Run `87e1e50d-e4fa-4817-8e8d-563859f46480`, itinerary `84f32a03-2323-468f-b7ca-81459719cf1e`, and frozen Catalog `shanxi.changzhi / 1.0 / 0.3.0` matched.
  - Added generic immutable SQLite StoryPackage and ExperiencePackage snapshot repositories, canonical SHA-256 hashes, Run/itinerary/Catalog association checks, corruption detection, and no-LLM recovery.
  - Persisted StoryPackage `story-package.0d7a0337095e6a1e32ccdda8` with hash `214abccd53bd1b285c33cd2918166b2da38672040e4c0056752065ac170e754b`.
  - Persisted ExperiencePackage `experience-package.abbc847bc8ab2e51de0e0733` with hash `209fe0b54622eaacb493a74fd54de25cbabbe39c199e75d718047b2861014456`.
- Real generation and binding:
  - Regenerated five Story Chapters from production-eligible Knowledge, bound four spatial Chapters through exact `amap / B0FFF49AFB`, and retained one context-only Chapter.
  - The bounded arrival-observation real gate passed: trusted `周围的一般环境` was rendered exactly, while the LLM retained natural facilitation wording. Guardian, no-touch, no-move, and environmental-safety visibility passed.
  - Generated five real Experience Activities from the same persisted Story hash, placed four by exact Provider identity, retained one context-only reflection, and persisted the final package.
  - Production/internal-only leakage, Citation hallucination, qualifier violation, Context fact violation, mythology promotion, all safety/hazard counters, name-only identity, dynamic POI forcing, and Knowledge/Story/itinerary/Planning mutation were all 0.
- Files modified:
  - Added `app/core/package_snapshots.py`, Story/Experience persistence modules and exports, Runtime SQLite snapshot tables, Experience Story snapshot identity fields, persistence tests, and five M4 documentation files.
  - Completed the deterministic Experience renderer, rendered model, validator responsibility split, prompts, and related tests from M4D-2.
- Commands and results:
  - Persistence/Binder: 45 passed. Persistence plus Runtime compatibility: 53 passed. M4 Domain gate: 357 passed. Persisted StoryPackage input gate: 52 passed.
  - Final focused regression: 479 passed, 5 existing warnings.
  - Complete Python: 537 passed, 18 subtests passed, 5 existing warnings.
  - Frontend Node: 26 passed. `python -m compileall -q app tests frontend mobile-app`: passed.
  - Runtime concurrency `KNOWN_FLAKY` did not reproduce. Existing FastAPI lifespan and local JWT warnings remain unrelated.
- Current risks:
  - Snapshot persistence currently has Repository/domain APIs but no frontend read surface; this is expected for M4.
  - Provider facilitation and deterministic safety wording may repeat slightly; this is a documented soft warning, not a safety failure.
  - Repository-local `.pytest_tmp_m4*` directories remain untracked test artifacts because this environment blocks their deletion. They must not be staged.
- Next recommended action: review the complete M4 diff and establish an explicit Git checkpoint. Enter M5 only after that checkpoint and a separately approved M5 scope.
