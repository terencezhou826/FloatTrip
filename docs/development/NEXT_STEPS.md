# Next Steps

Updated: 2026-08-22 00:04:28 +08:00

1. Review the real M1C Run and the exact mandatory/candidate provenance evidence, then create an M1C Git checkpoint only after explicit approval; no automatic commit was made.
2. Decide whether a concrete lunch recommendation is required before M2. The current generic 1 km restaurant search returned no lunch candidates around Fajiushan and correctly persisted a no-restaurant placeholder.
3. Keep the approximately 800 RMB preference classified as not currently verifiable until reliable attraction and transport cost data exist.
4. Keep travel-time feasibility separate from the existing opening-time LLM check unless a deterministic route-time validator is explicitly scoped.
5. Track `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` as `KNOWN_FLAKY`; investigate it separately.

Boundary to preserve: the verified Binding and candidate provenance checks passed and must remain hard requirements. Do not broaden meal search, add pricing assumptions, or enter RAG, Story, Experience, Commerce, Video, frontend, mobile, or M2 without explicit scope.
