# Frontend Data Contract

Public Catalog reads return stable package, route, theme, Region, Anchor, capability, availability, and Catalog version identities. Cultural preview includes only production-eligible Claim text and verified Source/Evidence projections.

Authenticated Runtime calls use the existing Run API. The form maps to `destination`, `days`, `start_date`, `end_date`, `attraction_preference`, `food_preference`, `habit_preference`, optional `trip_budget`, `package_id`, and `route_id`.

`GET /api/runs/{run_id}/trip` first checks Run ownership, then fixes the exact result itinerary. It returns:

- persisted itinerary ID and plan;
- StoryPackage plus snapshot hash, or `not_generated`;
- ExperiencePackage plus snapshot hash, or `not_generated`;
- LocalResourcePackage plus snapshot hash, or `not_generated`.

The API validates exact Run, itinerary, Catalog version, Story, Experience, and Resource associations. A mismatch or corrupted snapshot is explicit and is never replaced with mock data.
