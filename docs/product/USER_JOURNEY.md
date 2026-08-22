# User Journey

1. `/` introduces the Changzhi theme journey and links to `/myth-journeys`.
2. The collection page loads all routes from the Product Catalog API and shows truthful capability states.
3. A route detail page shows Catalog identity, anchors, production-safe cultural preview, sources, and capabilities.
4. Only a backend-READY route displays the formal trip form. Submission calls `POST /api/runs` with the existing Planning fields plus explicit `package_id` and `route_id`.
5. `/my-trips/{run_id}` restores the owned Run, replays durable events, and reconnects SSE from the latest sequence.
6. `waiting_user` is presented as a request for confirmation. The structured answer is sent to the existing `/resume` API.
7. A succeeded Run loads the persisted Trip hierarchy and presents itinerary, Story, Experience, and optional Resources.

Refreshing never creates a replacement Run or regenerates package content. Missing packages remain visibly unavailable.
