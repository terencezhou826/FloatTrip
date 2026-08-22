# Story Domain Model

## Purpose

The Story domain turns reviewed Catalog knowledge into a curated narrative structure. It does not create cultural facts and is not part of Planning.

The dependency direction is:

```text
StoryBlueprint
  -> StoryChapter
  -> KnowledgeClaim
  -> KnowledgeEvidence
  -> KnowledgeSource

StoryChapter
  -> Anchor
  -> verified ExternalPoiBinding (optional)
```

## StoryBlueprint

`StoryBlueprint` is a versioned Catalog record. It identifies the package, region, theme, and route; defines target audiences, narrative intent, and ordered Chapter IDs; and declares the complete Claim set available to the Story. It never stores a Run or itinerary ID.

An enabled Blueprint must be verified. The controlled Story type reuses `ThemeType`, so the model remains applicable to mythology, history, architecture, red culture, folk custom, food, nature, heritage, and custom themes.

## StoryChapter

`StoryChapter` defines sequence, Chapter type, curatorial intent, Anchor and optional POI Binding references, required and optional Claims, duration, audience tags, and reserved media/experience slots.

`opening_hook`, `transition_goal`, and `visitor_takeaway` are curated presentation text. They are not new Knowledge Claims. Multiple Chapters may share one Anchor or verified POI. Context and reflection Chapters may have no spatial identity.

## Knowledge Boundary

Every Claim used by an enabled Story must pass the Catalog's current production-eligibility policy. Draft, review-required, rejected, internal-only, forbidden, and otherwise ineligible Claims are rejected by Catalog validation. Story records retain Claim IDs, not copied promotion-policy truth, so generation hydrates the current approved wording and required qualifier from Knowledge.

Story loading is backward compatible: a package without `stories/` loads with empty Story collections. Once Story files exist, all Claim, Anchor, POI Binding, route, theme, region, Story, and Chapter references must form a closed dependency set.

## Reserved Boundaries

`media_slot_ids` and `experience_slot_ids` are identifiers only. M3 does not implement media generation, Video Providers, Experience tasks, Commerce, GPS triggers, or frontend presentation.
