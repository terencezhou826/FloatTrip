# Next Steps

Updated: 2026-08-22 08:57:19 +08:00

1. Review M1E's Provider-neutral contracts, selected-leg cache, hard/soft policy split, meal corridor filter, live Amap evidence, and formal Runtime/API result; create an M1E Git checkpoint only after explicit approval.
2. Decide whether the product needs explicit meal start/end times before meal legs can be classified as hard schedule `PASS`; current output honestly reports those legs as road-verified only.
3. If stronger live evidence is required, define a deterministic multi-attraction acceptance fixture or controlled real Run. The relaxed Jingwei E2E selected one attraction, so it had no inter-attraction leg.
4. Keep the approximately 800 RMB preference classified as not currently verifiable until reliable attraction and transport cost data exist.
5. Track `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` as `KNOWN_FLAKY`; it did not reproduce in the M1E full regression and must be investigated separately.

Boundary to preserve: verified Binding, mandatory identity, actual road-data provenance, and meal corridor checks passed and must remain hard requirements. Do not add intercity transport, a global route optimizer, pricing assumptions, RAG, Story, Experience, Commerce, Video, frontend, mobile, or M2 behavior without explicit scope.
