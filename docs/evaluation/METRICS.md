# Metrics

The formal registry contains route-neutral metrics for planning, knowledge, story,
experience, resources, product, and cross-layer integrity. IDs use
`<domain>.<metric_name>` and are globally unique.

Metric types are boolean, count, ratio, duration, score, set equality, and identity
match. Directions are exact, higher-is-better, and lower-is-better. Case contracts
may set a scenario-specific expectation, while the registry threshold records the
normal production target.

Hard examples include mandatory Anchor recall `1.0`, fake POI/resource counts `0`,
evidence coverage `1.0`, citation/qualifier/safety violations `0`, exact snapshot
identity, false READY count `0`, and secret leakage count `0`. Performance and prose
quality may be added as soft metrics; ordinary machine timing variation is not a hard
failure. No registered hard metric uses an LLM judge.
