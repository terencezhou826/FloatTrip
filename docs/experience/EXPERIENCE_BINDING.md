# Experience And Itinerary Binding

## Boundary

Binding runs only after a final itinerary and a validated StoryPackage exist. It is read-only with respect to Planning, Story, Knowledge, and the itinerary.

## Identity

Spatial Activities follow their Story Chapter and Anchor to a verified POI identity. Matching requires the exact pair:

```text
provider + external_poi_id
```

Names, fuzzy matching, LLM judgment, and regional conditions are never identities. Dynamic itinerary POIs receive no forced Experience.

An Activity without a spatial Anchor is `context_only`. Missing exact identity makes a spatial Activity `unplaced` and the package incomplete. Multiple Activities may share one verified itinerary stop.

## Weather

Weather-sensitive Activities may become `weather_adapted` and lose their outdoor stop placement while retaining safe context-only completion. Weather cannot alter cultural facts or create a new POI.

## Persistence

The final `ExperiencePackage` records the exact StoryPackage ID and canonical snapshot hash. `ExperiencePackageSnapshotRepository` writes it to the existing Runtime SQLite database only after validation passes and the referenced Story snapshot has the same Run, itinerary, Catalog version, and hash.

Loads verify the stored hash and all association columns. Corruption, version mismatch, itinerary mismatch, and Story mismatch fail explicitly. Loading never calls an LLM.
