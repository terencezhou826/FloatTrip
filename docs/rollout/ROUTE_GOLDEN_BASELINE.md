# Route Golden Baseline

The benchmark manifest supports a collection of route golden fixtures. Each fixture
is selected by `route_id`; the runner and readiness evaluator contain no route-name
conditions.

A route fixture locks stable route and mandatory Provider identity, approved and
forbidden Claim IDs, Chapter IDs, Activity IDs, snapshot identities and hashes,
safety outcomes, and capability expectations. It does not lock complete LLM prose,
dynamic meal names, or live Provider display names.

Adding a route fixture must not change hard metric definitions, thresholds, or
existing adversarial cases. A route baseline may be written only after all current
hard results pass. Existing baselines are never overwritten implicitly and cannot be
updated to conceal a regression.
