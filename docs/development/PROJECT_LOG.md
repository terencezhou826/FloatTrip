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
