# Experience Domain Model

## Purpose

The Experience domain turns a reviewed Story and Catalog Blueprint into safe visitor activities after Planning. It does not change the itinerary and does not create cultural or present-day facts.

```text
ExperienceBlueprint
  -> ExperienceActivity
  -> StoryChapter
  -> KnowledgeClaim
  -> Anchor
  -> verified ExternalPoiBinding
```

The models are Region-, Theme-, and Provider-neutral. Changzhi and mythology are Catalog data, not production branches.

## Curated Contract

`ExperienceBlueprint` owns audience, goal, ordered Activity IDs, version, and reserved media slots. `ExperienceActivity` owns interaction intent, Story/Anchor/POI/Claim references, duration, risk, guardian and weather requirements, prohibited actions, and a structured `ExperienceObservationTarget`.

The four observation modes are:

- `none`: reflection or question without an external target.
- `verified_entity`: a stable Catalog or Provider identity already verified by the system.
- `visitor_selected_visible_object`: the visitor chooses an object that is already visible, with observe-only and no-touch/no-move/no-collect/no-remove constraints.
- `specific_current_observable`: a specific present-day object supported by verified current-presence Evidence.

Ancient narrative or mythology cannot prove current visibility.

## Generated And Rendered Layers

`GeneratedExperienceActivity` is the raw structured LLM result. It contains facilitation prose, grounded factual items, Citations, qualifiers, the copied structured target, and an auditable raw safety notice.

`RenderedExperienceActivity` is the final user-visible contract. It retains `raw_generation` and deterministically adds the reviewed observation target and hard safety wording. `ExperiencePackageDraft` and `ExperiencePackage` store rendered Activities, so audit can distinguish model output from system-owned content.

## Formal Package

`ExperiencePackage` records Run, itinerary, Catalog and Experience versions, StoryPackage ID and snapshot hash, Activities, bindings, safety summary, Knowledge snapshot, warnings, reserved slots, and validation status. It is immutable once persisted.
