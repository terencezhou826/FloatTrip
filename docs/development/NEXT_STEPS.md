# Next Steps

Updated: 2026-08-23 11:01:21 +08:00

## M8 COMPLETE

Catalog content version: `0.6.0`.

Final route readiness:

- Jingwei: READY.
- Nuwa: READY with location disclosure. Its Cultural Anchor is Shanghao Village Tiantai Mountain in Shangdang District; spatial placement is `VERIFIED_LOCALITY` / `LOCALITY_PLACED` through Shanghao Village. Shanghao Village Committee `amap/B0H1P64PGR` is only a navigation reference, not Tiantai Mountain itself. The exact Cultural Anchor location remains unknown/unavailable.
- Shennong: READY with `amap/B016300684`.
- Houyi: READY with `amap/B0FFG79UY3`.

Final gates:

- Global offline benchmark: 173/173 PASS.
- Full Python: 772 passed plus 18 subtests passed.
- Frontend: 32 passed.
- Browser smoke: PASS.
- Hard failures: 0.
- Cross-route leakage: 0.
- Production business hardcoding: 0.

Next actions:

1. Review the complete M8 diff, Catalog content, formal snapshots, goldens, and documented degraded behavior.
2. Create an independent M8 Git checkpoint after review.
3. Do not enter M9 until the M8 checkpoint is complete.
4. Scope M9 separately. Its proposed scope is the AI Video / Short Drama Engine and requires explicit approval.

Preserve these boundaries:

1. Never equate a Cultural Anchor with a coarser navigation locality or reference point.
2. Keep all route behavior Catalog-driven; do not add Changzhi, route, Anchor, or mythology conditionals.
3. Keep Resource capability optional for base READY and preserve honest degraded states.
4. Preserve the four Catalog `0.6.0` snapshot identities.
5. Do not commit, push, enter M9, implement Video, add a fifth route, or expand beyond Changzhi without explicit authorization.
