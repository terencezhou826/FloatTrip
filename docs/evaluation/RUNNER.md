# Runner

Run the deterministic suite with:

```powershell
python -m app.evaluation --offline --output .benchmark_reports
```

Filters are `--suite`, `--domain`, and `--case`. `--offline` is the default and never
requires Amap, Sub2API, an LLM, weather, Browser, or internet access. `--live` only
permits cases explicitly marked as requiring network or LLM; live results do not
replace the offline baseline.

Every run writes JSON and Markdown. Markdown includes status, failures, warnings,
domain summary, metrics, regressions, readiness, environment, commit, and benchmark
version. Exit code `0` means no hard failure (soft warnings are allowed); exit code
`2` means at least one hard failure. Argument or unexpected execution errors use the
normal nonzero Python/argparse exit behavior.

Report ID, creation time, and measured durations may vary. Case IDs, metric status,
actual/expected values, hard flags, fixture version, and snapshot identities are the
substantive determinism contract.
