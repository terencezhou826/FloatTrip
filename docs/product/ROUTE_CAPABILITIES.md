# Route Capabilities

Each route exposes six booleans:

- `catalog_available`: the route is in an enabled package.
- `planning_available`: every mandatory Anchor has a verified ExternalPoiBinding.
- `knowledge_available`: route-scoped production-eligible Claims exist.
- `story_available`: an enabled verified Story exists for the route.
- `experience_available`: an enabled verified Experience exists and references an available Story.
- `resources_available`: the route can reach the generic Resource layer after Planning and Experience.

`ready` requires all six. Partial capabilities produce `preview`; Catalog-only routes produce `coming_soon`. These decisions are made in the backend projection without city, route, Anchor name, or Provider POI ID branches.

Coming-soon routes can show Catalog preview. They do not render a trip form and cannot invoke full planning.
