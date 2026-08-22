# LocalResourcePackage Persistence

`LocalResourcePackage` freezes:

- Catalog package, schema, and content versions;
- Run and itinerary IDs;
- StoryPackage and ExperiencePackage IDs and snapshot hashes;
- exact Provider Resource identities and provenance snapshots;
- deterministic recommendations, contextual bindings, disclosures, warnings, and hard metrics;
- creation time and canonical SHA-256 snapshot hash.

`LocalResourcePackageSnapshotRepository` uses the existing Runtime SQLite database. Save succeeds only when the Run is successful, the itinerary matches, and both upstream package rows have the same Run, itinerary, Catalog version, IDs, and hashes. Existing rows are immutable.

Load validates JSON, canonical hash, database metadata, and optional expected associations. Loading performs no LLM, Amap, routing, Story, or Experience call.

The formal M5 Jingwei snapshot is associated with Run `87e1e50d-e4fa-4817-8e8d-563859f46480` and itinerary `84f32a03-2323-468f-b7ca-81459719cf1e`. It reuses the persisted M4 Story and Experience snapshots without regeneration.
