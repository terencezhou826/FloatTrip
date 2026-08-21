# Next Steps

Updated: 2026-08-21 20:39:00 +08:00

1. Review the accepted M1B-1 Binding/Discovery foundation together with the M1B-1.5 verification provenance contract.
2. Configure `AMAP_API_KEY`, run real candidate discovery for `changzhi.anchor.fajiushan`, and have a human decide whether any candidate is the same real-world entity.
3. Author a `verified` Binding only after that review; never promote a search result automatically.
4. Stage and commit M1B-1 and M1B-1.5 only after user approval; no automatic commit was made.
5. Define M1B-2 separately. Its future runtime path must use only verified Bindings and must fail explicitly or require review when none exists.
6. Track `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` as `KNOWN_FLAKY`; investigate it separately from Catalog work.

Boundary to preserve: verification provenance records evidence but does not verify any current POI, affect Planning behavior, enforce mandatory Anchors, or change candidate pools, prompts, scoring, or generated routes. RAG, Story, Experience, Commerce, Video, frontend, and mobile remain out of scope.
