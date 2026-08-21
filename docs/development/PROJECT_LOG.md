# Project Log

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
