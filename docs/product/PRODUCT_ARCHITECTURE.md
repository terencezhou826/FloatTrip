# Product Architecture

M6 keeps one FloatTrip application. The validated Catalog is projected through read-only product APIs; the browser never imports Catalog files or infers route capability.

```text
Catalog -> CatalogProductService -> /api/catalog/* -> Product pages
User form -> POST /api/runs -> Runtime + durable events -> /my-trips/{run_id}
Owned Run -> persisted itinerary -> StoryPackage -> ExperiencePackage -> LocalResourcePackage
```

Route availability is derived from verified data. A complete `ready` route requires Catalog data, verified mandatory POI identity, production-eligible Knowledge, enabled verified Story and Experience, and the generic Resource capability. Incomplete routes remain preview or coming-soon and cannot create a full Run.

The frontend displays validated data. It does not call an LLM, generate cultural facts, decide POI identity, rank resources, or alter Planner/Reviewer behavior.
