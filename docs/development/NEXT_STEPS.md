# Next Steps

Updated: 2026-08-21 22:35:25 +08:00

1. Review the M1B-2 verified Binding, exact identity adapter, mandatory candidate injection, prompt constraints, and deterministic validator.
2. Create an M1B-2 Git checkpoint only after explicit approval; no automatic commit was made.
3. Define M1C as a separate milestone before implementation, keeping its scope independent from this identity-enforcement foundation.
4. Track `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` as `KNOWN_FLAKY`; investigate it separately from Catalog work.
5. Plan multi-version Catalog history separately if revisions must resolve mandatory POIs after the frozen content version is no longer installed.

Boundary to preserve: runtime POIs may come only from verified Bindings and exact Provider IDs. Candidate/rejected Bindings, name search, string similarity, and LLM identity decisions are not runtime fallbacks. RAG, Story, Experience, Commerce, Video, frontend, and mobile remain out of scope.
