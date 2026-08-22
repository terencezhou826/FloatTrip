# Baseline And Regression Policy

Baselines are explicit, versioned JSON files under `benchmarks/baselines/`. They store
scope, optional route ID, benchmark version, Git commit, suite results, metric values,
snapshot versions, and readiness. They never store credentials, tokens, or full user
logs.

Default runs never update a baseline. Updating requires `--update-baseline [path]`.
The save boundary independently scans every result and refuses to write when any hard
metric is FAIL or ERROR, even if the report summary is malformed.

Comparison classifications are `IMPROVED`, `UNCHANGED`, `SOFT_REGRESSION`,
`HARD_REGRESSION`, `NEW_CASE`, and `REMOVED_CASE`. PASS to hard FAIL/ERROR is always a
hard regression. Numeric score/ratio/duration changes also honor metric direction; a
hard recall change from `1.0` to `0.9` is a hard regression. Soft regressions do not
change the CLI success exit code unless accompanied by a hard failure.
