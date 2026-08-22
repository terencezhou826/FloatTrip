# POI Verification

Curated Anchors and Provider POIs remain separate entities. Discovery must use the
Anchor name, Region hierarchy, nearest prefecture city, administrative constraints,
name variants, nearby structure, POI type, coordinates, and parent/child fields where
the Provider supplies them.

Discovery only returns candidates. Name equality, substring matching, or an LLM
decision cannot create a verified binding. Verification requires exact Provider and
external POI identity plus method, timestamp, and review note.

Stop for human review when multiple plausible candidates remain, administrative data
conflicts, the intended whole-site versus internal-POI boundary is unclear, or an
official source cannot be reconciled with Provider identity. Candidate and rejected
bindings cannot satisfy mandatory Anchor enforcement.
