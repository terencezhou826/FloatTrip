# Next Steps

Updated: 2026-08-22 08:08:11 +08:00

1. Review M1D's bounded 1/3/5 km policy, Provider-identity provenance, real discovery evidence, and formal Runtime/API result; create an M1D Git checkpoint only after explicit approval.
2. Decide whether the 39.82 km straight-line distance from Fajiushan to the selected lunch should block M2. M1D found a real candidate truthfully but does not provide corridor-aware or route-optimal meal search.
3. If that detour is unacceptable, define a separate bounded corridor/route-feasibility task with deterministic acceptance criteria; do not fold it silently into M2.
4. Keep the approximately 800 RMB preference classified as not currently verifiable until reliable attraction and transport cost data exist.
5. Track `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` as `KNOWN_FLAKY`; it did not reproduce in the M1D full regression and must be investigated separately.

Boundary to preserve: verified Binding, mandatory identity, and meal candidate provenance checks passed and must remain hard requirements. Do not add corridor routing, pricing assumptions, RAG, Story, Experience, Commerce, Video, frontend, mobile, or M2 behavior without explicit scope.
