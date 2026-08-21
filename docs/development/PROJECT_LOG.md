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
