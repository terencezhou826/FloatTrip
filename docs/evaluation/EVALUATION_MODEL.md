# Evaluation Model

M7 is an isolated, production-neutral evaluation layer under `app/evaluation/`.
It reads committed fixtures, local Catalog data, and minimal frozen snapshot identity;
it does not add benchmark branches to Planning, Runtime, Catalog, or Product behavior.

`EvalSuite` groups one domain's cases. `EvalCase` records severity, fixture identity,
expected contract, metrics, route scope, and live dependencies. `EvalMetric` defines
type, direction, threshold, unit, evaluator kind, and whether it is a hard gate.
`EvalResult`, `SuiteResult`, and `BenchmarkReport` preserve observed values, evidence,
warnings, environment, snapshot versions, regressions, and readiness outcomes.

Hard correctness is deterministic. Model validation rejects any metric combining
`evaluator_kind=llm_judge` with `hard_gate=true`. Soft quality may use a future LLM
judge, but it can neither clear a hard failure nor create a production truth.

Benchmark version is independent of Catalog version. M7 starts with benchmark schema
`1.0` and content `1.0.0`; the Jingwei Catalog snapshot remains `1.0 / 0.3.0`.
