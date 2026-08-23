# Next Steps

Updated: 2026-08-23 13:32:09 +08:00

## M8.2 COMPLETE

Catalog content version: `0.6.0`.

Post-Planning product fulfillment is now durable, backgrounded, recoverable, and idempotent. Eligible theme Travel Runs remain `succeeded` as soon as the itinerary is persisted; Story, Experience, and Resources continue independently and are exposed through snapshot-only Product API reads.

Formal M8.2 evidence:

- Run: `03b8e2a9-908d-4f24-a606-824ab8a4be88`.
- Itinerary: `eb414a29-04a9-408e-849f-59f3d56305f4`.
- Fulfillment job: `d3c210eb-1377-5456-b29b-05dfe3274fe3`, succeeded with exactly one attempt per stage.
- Story, Experience, and Resources each have one immutable persisted snapshot; five API reads and five browser reloads preserved all identities without regeneration.

Final route readiness:

- Jingwei: READY.
- Nuwa: READY with location disclosure. Its Cultural Anchor is Shanghao Village Tiantai Mountain in Shangdang District; spatial placement is `VERIFIED_LOCALITY` / `LOCALITY_PLACED` through Shanghao Village. Shanghao Village Committee `amap/B0H1P64PGR` is only a navigation reference, not Tiantai Mountain itself. The exact Cultural Anchor location remains unknown/unavailable.
- Shennong: READY with `amap/B016300684`.
- Houyi: READY with `amap/B0FFG79UY3`.

Final gates:

- Global offline benchmark: 173/173 PASS.
- Full Python: 823 passed plus 18 subtests passed.
- Frontend: 33 passed.
- Browser smoke: PASS.
- Hard failures: 0.
- Cross-route leakage: 0.
- Production business hardcoding: 0.

Next actions:

1. Review the complete M8.2 source diff, formal fulfillment snapshots, recovery boundary, and runtime-artifact classification.
2. Create an independent M8.2 Git checkpoint after review. Do not stage `data/langgraph-checkpoints.db*` or `.codex-tmp/`.
3. Do not enter M9 until the M8.2 checkpoint is complete.
4. Scope M9 separately. Its proposed scope is the AI Video / Short Drama Engine and requires explicit approval.

Preserve these boundaries:

1. Never equate a Cultural Anchor with a coarser navigation locality or reference point.
2. Keep all route behavior Catalog-driven; do not add Changzhi, route, Anchor, or mythology conditionals.
3. Keep Resource capability optional for base READY and preserve honest degraded states.
4. Preserve the four Catalog `0.6.0` snapshot identities and the formal M8.2 Jingwei fulfillment chain.
5. Keep Product GET endpoints snapshot-only; generation belongs to the background fulfillment executor.
6. Keep historical incomplete Runs outside automatic startup generation unless a separately approved migration policy is introduced.
7. Do not commit, push, enter M9, implement Video, add a fifth route, or expand beyond Changzhi without explicit authorization.
