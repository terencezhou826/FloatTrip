# Project Log

## Current status - M8.2 COMPLETE

- Reconciled at 2026-08-23 13:32:09 +08:00. Starting HEAD was `e3e606e`; required M8 `33772f4`, M8.1 `5bc60bb`, and PORT `e3e606e` checkpoints were present.
- A durable, independent post-Planning fulfillment pipeline now creates Story, Experience, and optional Local Resource snapshots after an eligible theme Travel Run has succeeded and its itinerary has been persisted. Planning success remains independent from downstream product-layer failures.
- Formal Jingwei E2E Run `03b8e2a9-908d-4f24-a606-824ab8a4be88` produced itinerary `eb414a29-04a9-408e-849f-59f3d56305f4` and fulfillment job `d3c210eb-1377-5456-b29b-05dfe3274fe3`. All three stages succeeded with one immutable snapshot each; repeated API reads and browser refreshes preserved IDs and hashes without regeneration.
- The executor freezes Catalog `shanxi.changzhi` schema `1.0` content `0.6.0`, uses Catalog relationships instead of route branches, supports owner-protected retry, and recovers interrupted jobs. Startup discovery admits new Runs and only identity-consistent historical complete chains, preventing generation for old incomplete Runs.
- Final gates: offline benchmark 173/173 PASS with Hard FAIL 0; full Python 823 passed plus 18 subtests; frontend 33 passed; compileall PASS; browser smoke PASS; route/city hardcoding 0; secret leakage 0.
- Runtime artifacts under `data/langgraph-checkpoints.db*` changed during the formal E2E and remain unstaged. Next action is review and an independent M8.2 Git checkpoint. M9 requires separate approval.

## 2026-08-23 13:32:09 +08:00 - M8.2 post-Planning product fulfillment complete

- Files added: `app/product/fulfillment_models.py`, `app/product/fulfillment_repository.py`, `app/product/fulfillment.py`, and `tests/test_product_fulfillment.py`.
- Files modified: `app/core/database.py`, `app/product/__init__.py`, `app/runtime/container.py`, `app/api/trip_routes.py`, `frontend/api.js`, `frontend/product-state.js`, `frontend/product-pages.jsx`, `frontend/style.css`, `tests/product-state.test.js`, `tests/test_trip_product_api.py`, `tests/test_product_frontend_contract.py`, and `tests/test_resource_persistence.py`.
- Persistence and orchestration: added unique `(run_id, itinerary_id)` durable jobs; per-stage pending/running/succeeded/failed/blocked/skipped/not-applicable states; process-local execution guard plus SQLite atomic claim; immutable snapshot reuse; frozen Catalog loading; bounded transient retry; explicit owner-protected failed-stage retry; startup reset and reconciliation.
- Recovery audit: the initial broad startup scan exposed old incomplete formal Runs. The generic activation boundary now accepts Runs completed after executor activation or historical Runs with a complete, version- and identity-consistent Story -> Experience -> Resource chain. Seven task-created incomplete historical jobs were removed from runtime test data; no Runs, itineraries, checkpoints, or valid snapshots were deleted. Five succeeded jobs remain and zero are recoverable.
- Formal E2E: the new Jingwei Run passed real `waiting_user`, resumed with `2026-08-25`, persisted Planning at `2026-08-23T05:18:04.202819+00:00`, then automatically persisted Story at `05:19:19.179181+00:00`, Experience at `05:20:59.231484+00:00`, and Resources at `05:21:29.990415+00:00`. The job finished succeeded with `attempt_count=3`, one claim per stage.
- Snapshot identities: Story `story-package.ab5f97c0184fc25569a3ca6f` / `e7b97cf67fbd11a1e97c799d58d083257015004f7b17bebaf2ca310569aa95c9`; Experience `experience-package.fa200e7e502ee534eeaeece7` / `027f10d9ec2fe2463b719890a8a2bc383d4746ef817a31301a75c1a5db1640e0`; Resources `resource-package.3883e62accd44dbfbdeec6ef` / `9bd930a9fdd554da4667e34bbd9e608a67f6a0148faaf72aeaf9333f44df8acf`.
- Product verification: `/my-trips/03b8e2a9-908d-4f24-a606-824ab8a4be88` showed the persisted itinerary, five grounded Story chapters, five safe Experience activities, and five Provider-backed recommendations. Five API reads and five browser reloads retained one job and one snapshot per layer; browser console errors were zero apart from the existing Babel development warning.
- Commands/results: `python -m pytest tests --basetemp=.codex-tmp/m82-final-full -q` passed 823 tests plus 18 subtests with five existing warnings; `node --test tests/*.test.js` passed 33; `python -m compileall -q app tests` passed; `python -m app.evaluation --output .benchmark_reports` passed 173/173 with zero warnings and zero hard failures. Focused fulfillment was 27 passed and expanded integration was 402 passed. Final `git diff --check`, route/city conditional scan, Authorization scan, and actual `.env.local` secret-value scan passed.
- Risks/boundaries: the historical Runtime concurrency issue remains `KNOWN_FLAKY` but did not recur in the final full run. Redis graceful degradation is unchanged. Port 8765 remained untouched; the temporary 8766 server was stopped. Tracked `data/langgraph-checkpoints.db*` changes are runtime artifacts and must not be staged. Recursive cleanup of `.codex-tmp/` was rejected by the local command policy, so the untracked test-only directory remains excluded from staging. No Planning, Catalog, safety-validator, Runtime/SSE, or M9 semantics were changed.

## 2026-08-23 00:59:50 +08:00 - OBSOLETE INTERMEDIATE ASSUMPTION: M8 stopped at Nuwa-Tiantai'an cultural relation gate

This section records an intermediate user correction that temporarily identified Tiantai'an as the intended target. The user later explicitly corrected it: the final Nuwa target remains Shanghao Village Tiantai Mountain in Shangdang District. This section is historical only and defines no current blocker or action.

- Correction and compatibility audit:
  - At this intermediate point, user input temporarily identified `天台庵` in Pingshun County as the intended target instead of `上党区上郝村天台山`. This assumption was later explicitly corrected and is obsolete.
  - Audited the obsolete `changzhi.route.nuwa-tiantaishan` and `changzhi.anchor.tiantaishan` IDs across Catalog, tests, readiness data, Runtime SQLite, and LangGraph checkpoints. Nuwa was never READY and no persisted Run or package snapshot uses those IDs, so the compatibility result is case A.
  - Deleted the uncommitted `docs/rollout/reviews/TIANTAISHAN_SPATIAL_REVIEW.md`; it was produced solely for the corrected-away Tiantaishan rollout and must not participate in formal Nuwa content.
- Spatial and place identity gates:
  - Amap Place Detail v3 returned exactly one live `B01630MK7K` record named `天台庵`, at `113.405178,36.383467`, in Pingshun County (`140425`), type `风景名胜;风景名胜;寺庙道观`; exact identity passed.
  - Shanxi Provincial Government page `探秘山西 中国仅存的四大唐代木结构建筑之三平顺天台庵` (published 2021-08-05) places Tiantai'an at Wangqu Village, Beidanche Township, Pingshun County and identifies it as a temple/cultural relic. Provider and official geography agree.
- Cultural relation HARD GATE:
  - `太行山水线路` (Shanxi Provincial Government, 2018-01-26) mentions Nuwa only in a broad Taihang-mythology paragraph and lists Pingshun Tiantai'an later in a separate route field. This is regional co-occurrence, not a Nuwa-to-Tiantai'an relation.
  - `来长治避暑 享一夏清凉` (Shanxi Provincial Government, source shown as Shanxi Daily, 2025-07-18) likewise discusses Nuwa in a general Changzhi-mythology paragraph and Tiantai'an in the following ancient-architecture paragraph. It does not connect them.
  - `登临太行之巅 品味上党文化` (Shanxi Provincial Government, source shown as Shanxi Daily, 2024-11-22) explicitly states `女娲的故事就发端于今长治市的上党区上郝村天台山上`; it names the distinct, corrected-away Tiantaishan location and does not mention Tiantai'an as the Nuwa site.
  - A focused exact-term search found no government, gazetteer, heritage institution, research institution, or peer-reviewed source directly establishing `女娲 ↔ 天台庵`. The required cultural relation is therefore unverified.
- Commands and results in this M8 master phase:
  - `git diff --check`: passed at the starting and stopping audits.
  - `python -m app.evaluation --offline`: Jingwei benchmark 153/153 passed.
  - Focused Spatial/Catalog/Planning/Knowledge/Story/Experience/Resources/Product/Evaluation regression: 574 passed with four existing FastAPI warnings.
  - Read-only SQLite audits found 4 Runs, 3 itineraries, 49 Runtime events, 423 LangGraph checkpoints, 1714 checkpoint writes, and zero obsolete Nuwa ID matches.
- Stop status and boundary:
  - Historical status at that time: `STOPPED_AT_M8B`; first failed gate was `M8B.5 女娲 ↔ 天台庵文化关联 Gate`. This stop was superseded by the corrected target and completed M8 rollout.
  - No Catalog migration, ExternalPoiBinding, Nuwa Knowledge, Story, Experience, Planning, M8C, M8D, or M8E work was executed.
  - Historical next action at that time was human review of a direct cultural source. It is no longer active because Tiantai'an is not the final route target.

## 2026-08-23 00:16:14 +08:00 - HISTORICAL, SUPERSEDED: M8B-2 Tiantaishan human spatial review packet

This was a pre-fallback review stage. It was later superseded by the approved verified-locality policy and the completed Nuwa rollout; it is not a current blocker.

- Added `docs/rollout/reviews/TIANTAISHAN_SPATIAL_REVIEW.md` as a human-review-only packet. It records the live Amap Shanghao Village Committee POI `B0H1P64PGR`, its exact-detail coordinates and returned entrance, the separate village-level geocode, administrative cross-checks, identity boundaries, ten review questions, and empty Cultural-coordinate/Navigation-access candidate templates.
- Reopened and inspected the Shanxi Provincial Government page `登临太行之巅 品味上党文化` (2024-11-22 16:20, source shown as Shanxi Daily). The exact cited sentence connects the Nuwa story with `长治市的上党区上郝村天台山上` but supplies no coordinate, entrance, access, or safety evidence.
- The reviewed official page does not contain `上郝村西北` or `无影堆`. Focused exact-term searches did not yield a verifiable authoritative page before the government-domain search reached a CAPTCHA, which was not solved or bypassed. Both descriptions remain pending source corroboration and cannot narrow coordinates.
- Files modified in this phase: the new review packet and canonical development tracking only. No Catalog, Planning, Knowledge, Story, Experience, Runtime, or test file changed; no automated tests were required for this documentation-only phase.
- Historical status at that time: Tiantaishan lacked a human-approved exact Cultural coordinate or access point. The later verified-locality policy resolved production readiness without claiming an exact coordinate; Nuwa is now READY with disclosure.

## 2026-08-22 23:17:55 +08:00 - M8 starting sanity gate passed

- Verified clean starting checkpoint `8e34ec3cede9105fb4ceaa2e3ac30694abd6bd54`; required M8B-0 checkpoints `0553e66` and `8e34ec3` are in HEAD history, and the initial `git diff --check` passed.
- Ran `python -m app.evaluation --offline`: Jingwei remained 153/153 PASS. Unified readiness remained data-driven: Jingwei READY; Nuwa, Shennong, and Houyi COMING_SOON with their route-scoped production prerequisites still missing.
- Ran the focused Spatial Identity, Mandatory Spatial, Catalog, Knowledge, Story, Experience, Planning, Product, and Evaluation regression selection: 515 passed with four existing FastAPI lifespan deprecation warnings.
- The first focused pytest attempt was invalidated by `PermissionError: [WinError 5]` at the inaccessible Windows system pytest temp root. Rerunning the unchanged selection with workspace-local `--basetemp=.pytest_tmp_m8_sanity` passed; no business regression or code fix was involved.
- Files modified in this phase: canonical development tracking only. No M8B Catalog content, Knowledge, Story, Experience, Planning, Runtime, Product, spatial record, or production code was changed. M8B/M8C/M8D/M8E were not executed.

## 2026-08-22 22:55:38 +08:00 - HISTORICAL, SUPERSEDED: M8B-0 generic spatial identity hard gate passed

- Added route-neutral Catalog collections for verified Cultural Anchor coordinates and navigation access points. Verified runtime records require controlled status/method, ISO timestamp, source reference, provenance ID, verification note, accuracy, and confidence; manual map review also requires a non-sensitive audit reference. Existing `ExternalPoiBinding` remains unchanged and strict.
- Added `MandatorySpatialResolver` with deterministic priority: unique verified Provider POI, then unique verified Cultural Anchor coordinate, then unique verified navigation access point. It has no name search, nearby-POI substitution, LLM, or route/region branch. Provider candidates retain the original `binding_id`, `provider`, and `external_poi_id` identity.
- Added stable non-POI candidate/checkpoint fields, coordinate-capable Travel Time identity, Story placement by stable spatial identity while retaining Cultural `anchor_ids`, and the neutral frontend label `文化地点定位`. Navigation names/locations remain distinct from Cultural Anchor names/locations.
- Files modified for M8B-0: `app/catalog/{models,loader,repository,validation,__init__}.py`, `app/planning/{mandatory_spatial,schemas,nodes,helpers,prompts,route_feasibility,graph,runtime_worker}.py`, `app/providers/travel_time.py`, `app/story/{models,binding}.py`, `app/main.py`, `frontend/{api,product-pages}.js*`, and focused tests. No Catalog content, Knowledge, Nuwa Story/Experience, or Tiantaishan coordinate was added.
- Commands/results: Catalog spatial tests 17 PASS; focused compatibility 96 PASS and final 92 PASS; broad Catalog/Planning/Story/Runtime/Product regression 442 PASS; complete Python 730 PASS plus 18 subtests; frontend 32 PASS; Jingwei offline benchmark 153/153 PASS; compileall, hardcoding scan, and `git diff --check` PASS.
- Existing Runtime concurrency `KNOWN_FLAKY` remains unchanged. One broad run emitted a single transient failure marker without a retained summary; immediate `--maxfail=1` rerun passed 442/442 and the complete suite passed 730/730.
- Historical status at that time: Tiantaishan was `SPATIAL_VERIFICATION_PENDING`. This was later superseded by verified-locality resolution; the exact Cultural Anchor coordinate remains unknown, but Nuwa is READY with mandatory disclosure.

## 2026-08-22 22:16:31 +08:00 - HISTORICAL, SUPERSEDED: M8 stopped at Nuwa POI identity hard gate

This section records the earlier exact-POI gate. Its `STOPPED_AT_M8B` status and next action were superseded by the later generic verified-locality policy and completed M8 rollout.

- M8A remains passed: generic multi-route golden support, rollout audit/scaffold, six rollout documents, 46 focused tests, and the unchanged Jingwei 153/153 offline baseline.
- Audited Nuwa Catalog IDs without changing content: route `changzhi.route.nuwa-tiantaishan`, mandatory Anchor `changzhi.anchor.tiantaishan`, and Region path Shanxi Province -> Changzhi City -> Shangdang District.
- Ran real Amap Place Search v3 using the configured local provider and Catalog-derived scope. District exact/scenic/qualified queries, no-type variants, and prefecture no-type variants found no Shangdang `天台山` entity. The only target-like result was `天台庵` (`B01630MK7K`) in Pingshun County (`140425`), plus its parking lot; both were excluded.
- Verified an official cultural-place relationship in the Shanxi Provincial Government article `登临太行之巅 品味上党文化` (2024-11-22, source: Shanxi Daily), which names `上党区上郝村天台山`. The article provides no Provider POI ID, coordinate, access point, or unique map identity.
- Historical HARD GATE result at that time: `STOPPED_AT_M8B`, `HUMAN_REVIEW_REQUIRED`. No verified POI binding, Nuwa Knowledge, Story, Experience, benchmark, Planning E2E, or persistence snapshot had yet been created. M8C/M8D/M8E had not yet been executed; all were completed later under the corrected target and verified-locality policy.
- Files modified in this stop phase: canonical development tracking only; M8A framework files remain as previously reported. Commands included bounded real Amap searches, official-site browser verification, repository scans, and Git audit. API credentials were neither printed nor persisted.
- Historical next action at that time required an exact visitable Tiantaishan identity. The later verified-locality policy superseded that requirement without claiming an exact Cultural Anchor coordinate.

## 2026-08-22 - M8A route replication contract passed

- Added backward-compatible multi-route golden fixture loading and route-keyed readiness lookup; existing one-fixture M7 snapshot projection remains unchanged.
- Added generic route rollout layer/status models, `audit_route_readiness`, and a fact-free scaffold that creates only empty content collections and a blank route golden structure.
- Added six rollout documents covering replication, content workflow, POI verification, Knowledge review, golden baselines, and provincial scaling.
- Commands/results: 46 Evaluation/Rollout tests PASS, Jingwei baseline 153/153 PASS, compileall/diff/hardcoding scans PASS. Audit output is Jingwei READY and the other three routes POI_PENDING from data.
- Next: process Nuwa only. Do not write POI binding or cultural content before identity/source review gates pass.

## 2026-08-22 - M8 start gate passed

- Started M8 from clean checkpoint `9dca326c6d999f50a0ecac524c0cbd41f300f99c`; only temporary root planning files were created.
- Commands/results: M7/Jingwei offline benchmark 153/153 PASS, complete Python 692 plus 18 subtests PASS, frontend 32 PASS, compileall and `git diff --check` PASS.
- Existing warnings remain limited to FastAPI lifespan deprecations and the local JWT secret warning. No new production regression was observed.
- Next: M8A generic rollout audit/scaffold and data-driven multi-route golden support; do not create new route cultural content before its sequential route phase.

## 2026-08-22 21:27:29 +08:00 - M7 benchmark and readiness hard gates passed

- Added a deterministic offline benchmark corpus with 91 cases and 153 hard metric results across seven domains, including all required Knowledge, Story, Experience, Resource, Product, and cross-layer attacks.
- Added the unified CLI runner, JSON/Markdown reports, protected global and route-scoped baselines, six-way regression comparator, substantive determinism checks, and explicit exit codes.
- Added generic `RouteReadinessProfile` evaluation: Jingwei is READY; Nuwa, Shennong, and Houyi remain COMING_SOON from missing capabilities and route-scoped prerequisites. Resources are optional and do not block core cultural READY.
- Added six evaluation documents and the M8 route template. No production Planner, Runtime, Catalog, Provider, or frontend behavior was changed.
- Narrowed the existing `.gitignore` `eval*` rule with explicit exceptions for the three formal M7 evaluation directories; legacy `tests/eval/` generated fixture ignores remain unchanged.
- Results: Evaluation 36 passed; Catalog 255; Planning/Knowledge/Story/Experience 230; Resource/Product/Runtime 96; complete Python 692 plus 18 subtests; frontend 32; compileall, hardcoding, fixture-secret, baseline comparison, and diff checks passed.
- Live Smoke: SKIPPED because no local frontend service was running; offline baseline remains authoritative. Existing FastAPI deprecation/JWT warnings and Runtime concurrency `KNOWN_FLAKY` remain unchanged.
- Next: review and establish an M7 Git checkpoint if approved. Do not enter M8 without separate authorization.

## 2026-08-22 21:01:15 +08:00 - M7A evaluation contract hard gate passed

- Added the isolated `app/evaluation/` schemas for suites, cases, metrics, results, reports, benchmark versions, and route-readiness results; no production Planning, Catalog, Runtime, or Product behavior changed.
- Added 95 route-neutral formal metrics across planning, knowledge, story, experience, resources, product, and cross-layer domains. Hard metrics are deterministic by contract and an LLM judge cannot be a hard gate.
- Added global uniqueness, reference-integrity, and hard/soft boundary validation for suite, case, and metric definitions.
- Commands/results: start baseline 655 passed plus one documented Runtime concurrency flaky (passed in isolation), frontend 32 passed, formal four-layer snapshots loaded unchanged, and M7A tests 10 passed; compileall and `git diff --check` passed.
- Next: build the auditable offline corpus and adversarial fixtures under M7B without introducing route-specific framework conditions.

## 2026-08-22 19:53:11 +08:00 - M6C snapshot UI hard gate passed

- Added the ownership-protected `/api/runs/{run_id}/trip` read API, exact Story/Experience/Resource association checks, and Experience `load_for_run` persistence symmetry.
- Added a unified four-layer Trip UI using persisted itinerary, actual coordinates and road metrics, Story chapters/citations/qualifiers, trusted Experience observation and visible safety text, and optional Resource unknown/freshness/detour/disclosure states.
- Formal database read: Run `87e1e50d-e4fa-4817-8e8d-563859f46480` returned itinerary `84f32a03-2323-468f-b7ca-81459719cf1e`, five Story chapters, five Experience Activities, and five Resource recommendations with all three expected hashes unchanged.
- Tests/results: 37 persistence/API/ownership tests and 32 frontend state tests passed; compileall, `git diff --check`, and frontend generation/Provider/hardcoding scans passed.
- Added the five required documents under `docs/product/`. Next: M6D real-browser and complete regression gates.

## 2026-08-22 19:55:00 +08:00 - M6B Runtime journey UX hard gate passed

- Added a route form mapped to the existing Planning request snapshot, including explicit Catalog package/route selection, date range, party, pace, interests, and optional budget preference.
- Added formal Run creation, durable event recovery, latest-sequence SSE subscription/reconnect, `waiting_user` structured input, official resume, failure retry, and stable `/my-trips/{run_id}` recovery. Refresh recovery contains no Run creation path.
- Tests/results: 29 focused Runtime/API/frontend-contract tests and 32 frontend state tests passed; compileall and `git diff --check` passed. Provider/LLM/hardcoded fallback scan had zero findings.
- Next: M6C may expose only ownership-protected persisted itinerary/package reads and must preserve every upstream snapshot association.

## 2026-08-22 19:42:44 +08:00 - M6A Product Contract hard gate passed

- Added a generic, read-only Catalog product projection and public list/detail APIs. Route capability and availability are derived from verified POI bindings, production-eligible Knowledge, and enabled verified Story/Experience data; no route-name condition drives READY.
- Added the Catalog-driven product home, four-route collection, route preview, loading/error/empty/retry states, accessible status labels, and SPA routes under `/myth-journeys`.
- Files changed in this phase: `app/product/`, `app/api/catalog_routes.py`, `app/main.py`, `frontend/{api,index,main,navigation-state,product-state,product-pages,style}.*`, and focused Product/frontend tests.
- Commands/results: complete start baseline 641 passed plus the documented Runtime concurrency flaky; frontend baseline 26 passed; formal Story/Experience/Resource snapshots loaded with unchanged hashes; M6A gate 262 Python and 30 frontend tests passed; compileall, secret/hardcoding scan, and `git diff --check` passed.
- Risk: the existing Runtime concurrency timing test remains `KNOWN_FLAKY`; it was not modified. Proceed to M6B only through the existing Runtime/SSE contracts.

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

## 2026-08-22 19:08:59 +08:00 - M5A and M5B hard gates passed

- Starting gates:
  - Started from clean checkpoint `81b0fb6`. Formal Run `87e1e50d-e4fa-4817-8e8d-563859f46480`, itinerary `84f32a03-2323-468f-b7ca-81459719cf1e`, StoryPackage `story-package.0d7a0337095e6a1e32ccdda8`, and ExperiencePackage `experience-package.abbc847bc8ab2e51de0e0733` loaded and round-tripped with frozen Catalog `1.0 / 0.3.0`.
- M5A files and architecture:
  - Extended `app/catalog/` with provider-neutral LocalResource, ResourceSource, identity, verification, operational, price, availability, editorial, commercial relationship, disclosure, and recommendation-eligibility contracts.
  - Added optional hierarchical `resources/` loading, immutable Repository queries, cross-file provenance/reference/identity validation, and empty long-term Changzhi resource collections without fabricated records.
  - Added `tests/catalog/test_resources.py` with 60 tests. Resource tests: 60 passed; complete Catalog: 255 passed; compileall and `git diff --check`: passed.
- M5B files and real Provider result:
  - Added `app/resources/` runtime candidate/freshness/provenance contracts and a generic discovery service, plus `app/providers/amap/resources.py` reusing Amap Place Around v3.
  - M5A/M5B focused tests: 76 passed. Amap was loaded through `load_local_env()` without exposing the key.
  - Real formal-itinerary discovery succeeded around all three attraction stops: 1 candidate around Fajiushan, 20 around Cuiyunshan Faxing Temple, and 16 around Wufenglou, totaling 37 unique `amap + external_poi_id` identities.
  - All results remain runtime `candidate`; Provider provenance and `retrieved_at` coverage are 100%. Amap `biz_ext.cost` is retained only as Provider-reported per-person data; absent/invalid prices remain unknown. Operational status remains unknown even when Provider hours exist.
- Hard metrics and risks:
  - Fake resource, name-only identity, price hallucination, hidden sponsorship, commercial ranking influence, unverified production resource, and Knowledge/Story/Experience/itinerary mutation: all 0.
  - Soft warning: only one restaurant candidate was found within 5 km of Fajiushan itself; the formal itinerary's later stops have sufficient candidates. No curated product, lodging, heritage-experience, partner, or sponsored resources were added.
  - Repository-local `.pytest_tmp_m5*` directories are untracked test artifacts and must not be staged.
- Next recommended action: implement and gate M5C deterministic, optional-only recommendation. Do not regenerate Planning, Story, or Experience and do not enter M5D until M5C passes.

## 2026-08-22 19:22:34 +08:00 - M5 Local Resource & Commerce Engine complete

- M5C deterministic recommendation:
  - Added a unified read-only recommendation projection for runtime Provider candidates and eligible verified Catalog resources.
  - Reused `TravelTimeMatrix` and `assess_meal_detour`; exact selected meals are recognized only by Provider identity. All results are optional and contextual, never cultural identity or mandatory commerce.
  - Ranking reads route feasibility, detour, Provider distance/rating/review data, real price visibility, freshness, operation, and lexical user preferences. Commercial relationship is excluded from score and retained only for disclosure.
  - Resource/recommendation focused: 93 passed. Catalog, Meal, Route Feasibility, Story, Experience, and M5 combined gate: 352 passed. Production hardcoding scan found no conditionals for Jingwei, Fajiushan, Changzhi, or the formal POI ID.
- M5D formal package and persistence:
  - Loaded the unchanged formal itinerary and persisted M4 Story/Experience snapshots; no Planning, Story, or Experience generation ran.
  - Real Amap discovery selected 7 unique runtime restaurant candidates from bounded queries around the three formal attraction stops. Real Amap driving-time checks produced 5 deterministic optional recommendations.
  - Persisted `resource-package.c0a72c99ca7b3accbe323263` with hash `fd4424b3b4d9c949ea1e7250c1561198a8b7297c351a5151f13b4f8492ee55ca` in the formal Runtime database.
  - Resource package persistence tests: 105 passed, including save/load/round-trip, hash, version and upstream association checks, corruption rejection, and load without Provider calls.
- Formal result:
  - Recommended exact selected lunch `amap / B0FFFZ7ZGA`, three low-detour resources near Wufenglou, and one route-feasible resource context near Fajiushan. All are `restaurant`, runtime `candidate`, `optional=true`, with `commercial_relationship=unknown` and operational status `unknown`.
  - Price amounts appear only where Amap returned `biz_ext.cost`, marked Provider-reported per-person and fresh. Unknown price remains unknown.
  - Fake resource, unverified curated resource, name-only identity, price/availability hallucination, sponsorship influence, hidden sponsorship, mandatory commerce, and Knowledge/Story/Experience/itinerary mutation: all 0.
- Final verification:
  - Resource/Discovery/Recommendation/Persistence focused: 105 passed. Complete Python: 642 passed plus 18 subtests, with 5 existing warnings. Frontend Node: 26 passed. Compileall, `git diff --check`, and production hardcoding audit passed.
  - Runtime concurrency `KNOWN_FLAKY` did not reproduce. Existing FastAPI lifespan and local JWT warnings remain unrelated.
  - Added five documents under `docs/resources/` covering model, provenance, recommendation, commercial policy, and persistence.
- Workspace note:
  - Cleanup of repository-local `.pytest_tmp_m5*` directories was rejected by the environment command policy. They remain untracked test artifacts and must not be staged.
- Next recommended action: review M5 and establish an explicit Git checkpoint. Do not commit/push automatically and do not enter M6 without a separately approved scope.
## 2026-08-22 20:28:22 +08:00 - M6 Product Frontend and User Journey complete

- M6D real-browser validation:
  - Used the formal M5 snapshot database and the existing owner account; no Story, Experience, or Resource regeneration occurred.
  - Catalog homepage, all four route cards, Jingwei READY state, three truthful coming-soon previews, route detail, and the formal trip form passed.
  - Created Runtime Run `a1ee2516-d526-4869-a51a-fa8ff6bfec64`; formal `waiting_user` and `/resume` retained the same Run, then produced itinerary `5c037699-8161-47b8-858f-30f31992663b` with the mandatory Fajiushan identity and road travel times.
  - The new Run truthfully exposed missing Story/Experience/Resource packages. The persisted formal M5 Run `87e1e50d-e4fa-4817-8e8d-563859f46480` displayed itinerary `84f32a03-2323-468f-b7ca-81459719cf1e`, five Story chapters, five Experience activities, and five optional resource recommendations.
  - Refresh preserved Story `story-package.0d7a0337095e6a1e32ccdda8` / `214abccd53bd1b285c33cd2918166b2da38672040e4c0056752065ac170e754b`, Experience `experience-package.abbc847bc8ab2e51de0e0733` / `209fe0b54622eaacb493a74fd54de25cbabbe39c199e75d718047b2861014456`, and Resource `resource-package.c0a72c99ca7b3accbe323263` / `fd4424b3b4d9c949ea1e7250c1561198a8b7297c351a5151f13b4f8492ee55ca` unchanged.
  - `1440x900`, `1024x768`, `768x1024`, and `390x844` had no horizontal overflow, clipped primary controls, or critical map/content overlap. Labels, button names, headings, and visible focus styles passed the accessibility smoke review.
  - Missing route, missing Run, and partial package states remained truthful and recoverable. Browser console had only the existing React/Babel development warnings.
- Security, behavior, and quality gates:
  - Served HTML, scripts, Catalog responses, and configuration were scanned against configured secret values; no Amap Web Service, LLM, JWT, or other server secret leaked. Frontend LLM/cultural generation and route-specific READY conditionals remained zero.
  - The user journey clearly exposes where to go, why the route matters, what to do, optional nearby resources, and unknown operational/commercial data.
  - Observable key-page readiness was approximately 0.7-0.8 seconds locally; no SQLite dump or cross-user package collection was sent to the browser.
- Commands and results:
  - `python -m pytest -q --basetemp .pytest_tmp_m6_final`: 656 passed, 18 subtests passed, 5 existing warnings.
  - `node --test tests/*.test.js`: 32 passed. Focused Product/API/persistence: 41 passed. Ownership: 2 passed. Runtime concurrency known-flaky isolated check: passed.
  - `python -m compileall -q app tests`, `git diff --check`, production hardcoding scan, and served-secret scan: passed.
  - An initial full-suite attempt without `--basetemp` produced 168 fixture setup errors because the Windows default pytest temp root denied access; rerunning with a repository-local basetemp passed completely.
- Current risks and next action:
  - New Runtime Runs currently generate itinerary only; downstream Story/Experience/Resource orchestration remains a truthful separate boundary.
  - In-browser Babel/React development bundles are a production-readiness soft warning. Repository-local `.pytest_tmp_m6*` directories must not be staged.
  - Review the M6 diff and establish a checkpoint only after explicit approval. Do not enter M7 without a separately approved scope.

## 2026-08-23 10:39:09 +08:00 - M8 Spatial Fallback and four-route rollout complete

- Spatial fallback and Nuwa:
  - Added provider-neutral resolution priority: verified Provider POI, Cultural coordinate, navigation access point, locality, township, and administrative area.
  - Kept Cultural Anchor and Navigation identity distinct. Nuwa uses verified Shanghao Village locality and `amap/B0H1P64PGR` only as a navigation reference; Tiantaishan has no claimed exact coordinate.
  - Nuwa is `LOCALITY_PLACED`, degraded, disclosure-required, and READY with safe village-area Experience behavior. The previously supplied Tiantai'an correction was superseded by the user's approved Spatial Fallback policy restoring Tiantaishan.
- Route rollout:
  - Shennong verified the parent Lao Dingshan National Forest Park `amap/B016300684`; child scenic POIs were not substituted for the Cultural Anchor.
  - Houyi verified Tunliu Lao Yeshan Scenic Area `amap/B0FFG79UY3`; Lao Yeshan Ecological Park was excluded as a separate entity.
  - Knowledge, Story, and Experience preserve source qualifiers, `羿` / `十日` wording, and deterministic plant, weapon, projectile, cliff, child, environmental, and restricted-area safety boundaries.
  - Houyi remained truthfully `UNCOVERED` for lunch with self-provision guidance while the route itself was `FEASIBLE` with complete Provider road data. This is an allowed M1D degraded meal result, not fabricated coverage.
- Formal Catalog `0.6.0` snapshots:
  - Jingwei: Run `36eda6d0-6b02-4b06-850a-dc01e0661c62`, itinerary `7299362a-458c-4c1c-b113-604ea920b9f2`, Story hash `5441844965182e97ce6963aaed5a13b3f5307a068842d0a45cd91ca0e2939bc0`, Experience hash `c8864d8fcc07f3a20ebb5320f4eedf62391d4ec3e5cc7690ae833c690075593d`, Resource hash `7f8c28266c633c4e0fcee9f9fa059ae09b4c6493ed528dd303901e6d3adf2750`.
  - Nuwa: Run `e5253813-de9b-44e1-8007-569ebc54f62e`, itinerary `340a9d78-3456-428c-94c8-75d17e2ed69a`, Story hash `abe1b2c120cbe7ece0f86b18e938d40ee738a2cd093fd5bac328e20c173a9905`, Experience hash `0c0fd394fb7ed6980be6192215c40d744f1d1e526124929f58774e0a58454dbb`.
  - Shennong: Run `16c963a2-45fb-4e45-969e-9277a4c79209`, itinerary `d8938c52-6433-4e5d-99b2-c7c2f47bf418`, Story hash `5442c9fad5df22cd8459bc8c2faf0e58a5ee79227a5b96aac517eeb2512d4985`, Experience hash `e577dcb8dd38a88f7f343a6f3c36168c2c4d2f513d939eb0be8286c1fd462446`.
  - Houyi: Run `59bf09e4-965a-4208-a957-41cfb193cb23`, itinerary `6c921972-6df4-4744-ae4f-f314fdf80418`, Story hash `5823c9bf746585c1ac67476d972d243fc1acf8fbe020fdf9abdd207cfdd2e6a8`, Experience hash `655d23f0f2422c29afa405201b1f9bfa2014e59eb49e2680a70b466e902875da`.
- Commands and results:
  - Formal Runtime/API runs used real Amap and OpenAI-compatible Providers. All successful runs observed `waiting_user`, resume, SSE reconnect, mandatory placement, real road feasibility, Story/Experience grounding, persistence, and load without regeneration. One Jingwei attempt received a transient Provider HTTP 503; one fresh retry succeeded.
  - Offline benchmark: 173/173 PASS. Unified readiness: Jingwei, Nuwa, Shennong, Houyi all READY. Resources are available for Jingwei and optional/not generated for the other three routes.
  - Focused stale-contract regression: 99 passed. Complete Python: 772 passed plus 18 subtests, 5 existing warnings. Frontend Node: 32 passed. Compileall passed.
  - Production business-conditional scan, tracked-secret audit, exact snapshot/golden audit, and four-route live HTTP refresh stability passed.
  - Browser smoke passed Catalog 0.6.0, four READY route cards, all route details, Nuwa locality disclosure, and correct exact/locality labels. Console contained only the existing in-browser Babel development warning.
- Files modified in this phase:
  - Generic spatial Catalog/Planning/Story/Experience/Product/Evaluation modules and their tests; Changzhi locality, Knowledge, Story, Experience, POI binding and region data; four route-scoped golden fixtures and benchmark cases; frontend data-driven labels; canonical and root project tracking.
- Current risks:
  - Runtime concurrency `KNOWN_FLAKY` did not reproduce and remains deferred.
  - FastAPI lifespan deprecation, unset persistent local JWT secret, unavailable optional Redis cache, and in-browser Babel remain existing environment/deployment warnings.
  - M8 worktree remains intentionally uncommitted. Do not enter M9, Video, another city, or another route without explicit approval.
- Next recommended action: review the complete M8 diff and evidence, then create a Git checkpoint only after explicit approval.

## 2026-08-23 10:42:57 +08:00 - M8 final handoff validation

- Removed only task-owned `.codex/m8_nuwa_live.py`, `.codex/m8_resource_refresh.py`, `task_plan.md`, `findings.md`, `progress.md`, and `.pytest-tmp/`; retained benchmark reports and pre-existing pytest directories.
- `python -m app.evaluation --output .benchmark_reports`: 173/173 PASS.
- `python -m compileall -q app tests`: PASS. Port 8766 is not listening.
- No business, Catalog, Knowledge, Story, Experience, Planning, or Runtime behavior was changed during this final validation.
