# Story and Itinerary Binding

## Boundary

Story binding happens after Planning has produced and persisted a final itinerary. The binder receives that itinerary as a read-only dictionary; Story never alters Planner, Reviewer, candidate pools, mandatory enforcement, Time Check, meal selection, route feasibility, or Finalize.

## Identity Rule

Spatial placement uses only the exact pair:

```text
provider + external_poi_id
```

The binder resolves each Chapter's Anchor through runtime-eligible verified `ExternalPoiBinding` records and compares those identities with attraction stops in the final itinerary. It never uses names, fuzzy matching, LLM judgment, or city/route-specific conditions.

If a required spatial identity is absent, the Chapter is `unplaced` and the package is `incomplete`; the binder does not guess or mutate the itinerary. Chapters without Anchors are `context_only`.

## Placement

`ChapterBinding` records Anchor IDs, resolved Provider identities, itinerary stop IDs, placement type, trigger hint, duration, and reason. When several Chapters share one stop, deterministic hints distribute them across arrival, early visit, mid visit, late visit, and departure. These are presentation hints rather than GPS triggers.

Attraction stops without a Story identity, including dynamic POIs, remain unchanged and receive no forced Story. Missing stop IDs receive stable local projection IDs such as `day.1.timeline.0` without being written back to the itinerary.

## StoryPackage

`StoryPackage` combines the generated Story, Chapter bindings, frozen Knowledge/Catalog provenance, itinerary and Run references, warnings, reserved media/experience slots, validation status, and binding metrics. Its ID is deterministically derived from Story ID and itinerary ID.

Weather may add a presentation hint only. It cannot change Chapter facts. Video and Experience slots remain empty/unconfigured in M3.
