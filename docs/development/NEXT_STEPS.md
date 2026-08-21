# Next Steps

Updated: 2026-08-21 20:01:43 +08:00

1. Review the M1A CatalogContext, resolver, explicit Run input, and snapshot preservation contract.
2. Stage and commit M1A only after user approval; no automatic commit was made.
3. Define M1B explicitly before mandatory anchors influence POI candidates, prompts, scoring, or generated routes.
4. Track `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` as `KNOWN_FLAKY`; investigate it separately from Catalog work.

Boundary to preserve: M1A may carry CatalogContext but must remain behavior-neutral. RAG, Story, Experience, Commerce, Video, frontend, and mobile remain out of scope.
