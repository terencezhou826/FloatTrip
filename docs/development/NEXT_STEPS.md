# Next Steps

Updated: 2026-08-22 12:43:06 +08:00

1. Review the M2B production gate, lexical weights, A-F results, and `insufficient_direct_match` behavior; create an M2B Git checkpoint only after explicit approval.
2. Enter M2C only under a separate explicit instruction. Preserve frozen Catalog versions, Source/Claim/Evidence traceability, and promotion qualification when connecting `KnowledgeContext` to any consumer.
3. Define source archival/versioning policy before relying on public URLs for long-term production citations.
4. Keep `changzhi.claim.fajiushan-yandi-residence` in `review_required` and `internal_only` unless independent historical evidence is supplied.
5. Track `RuntimeEndToEndTests.test_two_plans_execute_concurrently_without_merging` as `KNOWN_FLAKY`; it did not reproduce and Runtime was not modified.

Boundary to preserve: M2B performs local, deterministic, evidence-aware retrieval only. It contains no Embedding, vector database, LLM query rewrite/reranking/answer generation, Planning prompt, Runtime, SSE, Story, Experience, Commerce, Video, frontend, or mobile integration.
