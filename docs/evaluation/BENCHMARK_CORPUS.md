# Benchmark Corpus

Committed fixtures live under `benchmarks/`. `manifest.json` owns the benchmark
version and the seven suite files. Each case records a stable ID, source, expected and
observed contract, tags, and the attack text where applicable.

The corpus covers positive, negative, adversarial, and regression cases. It includes
Planning identity/feasibility failures, unsupported Knowledge questions, Claim-type
promotion, Citation identity attacks, Story grounding attacks, all specified
Experience safety attacks plus a safe visible-object counterexample, Resource truth
and sponsorship attacks, Product ownership/false-READY/secret cases, and cross-layer
version/hash/mutation cases.

`cross_layer/jingwei-golden.json` is a minimal audited projection. It locks route,
mandatory Anchor and Provider identity, Chapter IDs, Activity IDs, approved and
forbidden Claim IDs, snapshot IDs/hashes, and capability expectations. It explicitly
does not lock narration text, meal names, or dynamic POI names.

The loader rejects duplicate or dangling IDs, hard/soft mismatches, path escape, and
secret-shaped fixture values. Fixtures contain no credentials or real user data.
