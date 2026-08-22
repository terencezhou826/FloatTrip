# Snapshot UI

The unified Trip page has four deliberately separate layers:

- Itinerary answers where to go using persisted stops, exact coordinates, road metrics, mandatory metadata, weather, and Spot Tips.
- Story answers why the visitor is there using persisted chapters, qualifiers, citations, and source excerpts.
- Experience explains what to do using persisted rendered Activity text, trusted observation text, duration, completion mode, and visible safety requirements.
- Resources shows optional persisted recommendations with road distance, extra detour, price state, operational state, freshness, identity status, and commercial disclosure.

Unknown price, availability, or commercial relationship remains unknown. Partner or sponsored resources require visible disclosure. No resource is mandatory and no commercial action gates Story or Experience.

Package IDs and hashes are retained in the page DOM for snapshot-stability verification. Browser storage may keep authentication and a Run event cursor, but never becomes the source of Story, Experience, or Resource content.
