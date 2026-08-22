# Next Steps

Updated: 2026-08-22 18:05:52 +08:00

1. Review the complete M4 working tree and create an explicit Git checkpoint only after approval. Do not stage repository-local pytest temporary directories.
2. Preserve the four-mode ObservationTarget contract and deterministic renderer. Trusted targets and hard safety remain system-owned; raw LLM prose remains separately auditable and fully validated.
3. Preserve immutable StoryPackage and ExperiencePackage SQLite snapshots, their canonical hashes, and Run/itinerary/Catalog association checks. Downstream retries must load snapshots without another LLM call.
4. Preserve exact `provider + external_poi_id` placement and all evidence, qualifier, current-presence, child-safety, environmental, cultural-property, and mutation gates.
5. Scope M5 separately. Do not implicitly add Video, Commerce, GPS/AR, frontend/mobile presentation, completion tracking, additional routes, or new cultural facts.

Boundary to preserve: M4 is complete. Formal StoryPackage and ExperiencePackage snapshots are persisted for Run `87e1e50d-e4fa-4817-8e8d-563859f46480` and itinerary `84f32a03-2323-468f-b7ca-81459719cf1e`; all M4 hard metrics are zero and final regressions pass. Establish the M4 checkpoint before any separately authorized M5 work.
