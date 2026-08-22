# Evidence-Safe Experience Generation

## Flow

```text
Persisted StoryPackage snapshot
  -> ExperienceActivityContext
  -> strict structured LLM facilitation
  -> raw fact/Citation/qualifier/safety validation
  -> deterministic Experience renderer
  -> rendered observation/safety validation
  -> ExperiencePackageDraft
```

The service can read `GeneratedStory` during an initial generation flow or a persisted `StoryPackage` during retry and recovery. Loading a Story snapshot does not call an LLM.

## Trusted Structured Content

The renderer may use only reviewed structure already present in Catalog or validated Context:

- `ObservationTarget.target_text` and mode.
- Activity and target safety constraints.
- guardian requirements.
- exact Knowledge-approved wording, Citations, and qualifiers already validated in raw output.

It cannot add a cultural fact, place fact, current entity, mythology statement, Claim, Evidence, or Source.

## LLM Facilitation Content

The LLM controls title-preserving facilitation fields: instruction, prompt, optional hint, completion message, tone, and optional supplementary safety wording. Cultural factual content must exactly use approved Claim wording. The model does not decide whether the observation target or hard safety requirements are visible.

One structured repair is allowed with the same Context. There is no free-text fallback.

## Deterministic Renderer

For `target_mode != none`, `observation_text` is copied exactly from the curated target. For `none`, it remains empty. Hard no-touch, no-move, no-collect, no-remove, normal-area, barrier, guardian, and skippable constraints are rendered from controlled structure.

This removes the fragile requirement that a Provider must remember to repeat reviewed `target_text`. `observation_target_not_visible` remains a hard validator on the rendered layer.
