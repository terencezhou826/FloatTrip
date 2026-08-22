# Next Steps

Updated: 2026-08-22 14:14:56 +08:00

1. Review the complete M3 diff and create an independent Git checkpoint only after explicit approval.
2. Keep `changzhi.claim.fajiushan-yandi-residence` in `review_required` and `internal_only`; its Story reference and leakage counts remain zero.
3. Preserve exact `provider + external_poi_id` Story placement and the deterministic Citation/qualifier/production-eligibility gates.
4. Continue tracking `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` as `KNOWN_FLAKY`; it did not reproduce in the M3 final suite.
5. Scope M4 separately before implementing any Planning/Chat Story integration, Story UI, Experience, Commerce, Video, additional routes, or provincial rollout.

Boundary to preserve: M3 is complete as a standalone post-Planning Story Engine. M4 and all frontend/mobile, Experience, Commerce, Video, GPS-trigger, Embedding, and vector-database work remain unstarted.
