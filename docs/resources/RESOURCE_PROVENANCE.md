# Resource Provenance

Every verified curated Resource references one or more `ResourceSource` records. A source retains its type, external identity or URL/document reference, retrieval time, verification time, Provider where relevant, and audit metadata.

Runtime Amap candidates retain:

- exact `amap + external_poi_id` identity;
- `amap.place.around.v3` as the Provider source;
- retrieval timestamp;
- normalized administrative, coordinate, type, distance, rating, and review fields when returned;
- only the raw structured fields needed for audit.

Provider discovery returns `candidate`. It never writes Catalog data and never changes status to `verified`.

Price, business-hours, availability, and resource identity have separate freshness. A verified entity does not make an old price or hours record current. Unknown values remain unknown. Amap `biz_ext.cost` is stored only as Provider-reported per-person data with Provider field and retrieval time; it is not an official price.

Marketing descriptions remain Resource metadata. They are not Knowledge Sources and cannot create Knowledge Claims, Story facts, or Experience facts. Cultural product claims require an independently production-eligible Knowledge Claim.
